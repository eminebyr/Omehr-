"""FATURALAMA İSKELETİ (Madde 2 — SaaS boşluğunun en büyüğü).

Bu modül, ÖDEME SAĞLAYICISINDAN (Stripe/iyzico) BAĞIMSIZ, saf iş
mantığını içerir: hangi plan hangi kotaya karşılık gelir, bir ödeme
olayı (abonelik oluşturuldu/güncellendi/iptal edildi/ödeme başarısız
oldu) geldiğinde tenant_registry.py'nin NASIL güncelleneceği.

Webhook TRANSPORT katmanı (imza doğrulama, HTTP alma) AYRI bir
modülde (webhook_server.py) — bu, iş mantığını GERÇEK ödeme sağlayıcı
hesabı OLMADAN test edilebilir kılar (Stripe/iyzico simüle edilmiş
olaylarla).

ÇIKIŞ (outbound) YÖNÜ — Checkout/Portal session oluşturma: bu fonksiyonlar
GERÇEKTEN Stripe'a HTTP isteği atar (webhook'un aksine, saf değildir).
Yalnız burada, tek bir yerde tutulur ki sağlayıcı değişirse (iyzico)
yalnız bu iki fonksiyon (create_checkout_session/create_portal_session)
yeniden yazılsın, çağıran kod (onboarding/web/app.py) değişmesin.
"""
from __future__ import annotations

import os

from services.multitenant import tenant_registry
from services.observability import get_logger

LOGGER = get_logger("omehr.billing")

# Plan -> (şube kotası, kullanıcı kotası) eşlemesi. Fiyatlandırma
# BURADA DEĞİL — bu yalnız KOTA sınırlarını belirler; fiyat, ödeme
# sağlayıcısının KENDİ ürün/fiyat kaydında tutulur (Stripe Price ID
# gibi), tekrar burada kodlanmaz (tek doğru kaynak ilkesi).
PLAN_KOTALARI = {
    "deneme": {"sube_kotasi": 3, "kullanici_kotasi": 5},
    "temel": {"sube_kotasi": 10, "kullanici_kotasi": 15},
    "standart": {"sube_kotasi": 50, "kullanici_kotasi": 100},
    "kurumsal": {"sube_kotasi": 10_000, "kullanici_kotasi": 10_000},
}

# Ödeme sağlayıcısının (Stripe) OLAY türlerinden, bizim iç durum
# modelimize (aktif/askida/iptal) eşleme. iyzico kullanılırsa, iyzico'nun
# KENDİ olay isimleri farklıdır — webhook_server.py'de sağlayıcıya özel
# çeviri yapılıp, BU modüle her zaman AYNI iç isimlerle (bkz.
# process_billing_event) ulaşılmalıdır; böylece bu iş mantığı sağlayıcı
# değişse bile aynı kalır.
_OLAY_DURUM_ESLEMESI = {
    "subscription_created": "aktif",
    "subscription_renewed": "aktif",
    "subscription_payment_failed": "askida",
    "subscription_canceled": "iptal",
}

# Plan -> Stripe Price ID'sinin okunacağı ortam değişkeni. Fiyat/Price ID
# BURADA SABİTLENMEZ (yukarıdaki tek-doğru-kaynak notuna bkz.) — operatör
# Stripe Dashboard'da ürünleri oluşturunca gerçek Price ID'yi bu ortam
# değişkenlerine yazar. 'deneme' kartsız/ücretsizdir, bu yüzden burada yok.
_PLAN_FIYAT_ENV = {
    "temel": "OMEHR_STRIPE_PRICE_TEMEL",
    "standart": "OMEHR_STRIPE_PRICE_STANDART",
    "kurumsal": "OMEHR_STRIPE_PRICE_KURUMSAL",
}


def plan_for_price_id(price_id: str) -> str | None:
    """price_id_for_plan()'ın tersi — bir Stripe Price ID'sinden bizim
    plan adımıza döner. webhook_server.py'nin customer.subscription.updated
    olayında (Portal üzerinden kendi kendine yükseltme/düşürme) hangi
    plana geçildiğini bulmak için kullanılır. Eşleşme yoksa None döner
    (ör. Stripe Dashboard'dan elle, bilinmeyen bir price ile oluşturulmuş
    abonelik) — çağıran bu durumda plan alanını DEĞİŞTİRMEMELİDİR."""
    for plan, env_adi in _PLAN_FIYAT_ENV.items():
        if os.getenv(env_adi, "").strip() == price_id:
            return plan
    return None


def price_id_for_plan(plan: str) -> str:
    """Bir ücretli planın Stripe Price ID'sini ortam değişkeninden okur.
    'deneme' (ücretsiz) veya ortam değişkeni HENÜZ ayarlanmamış bir plan
    için net bir ValueError fırlatır — sessizce None/boş Price ID ile
    Stripe'a istek atıp anlaşılmaz bir sağlayıcı hatası almak yerine."""
    if plan not in _PLAN_FIYAT_ENV:
        raise ValueError(
            f"'{plan}' planı ücretsizdir veya Stripe Checkout'a uygun değil "
            f"(yalnız {sorted(_PLAN_FIYAT_ENV)} için Checkout gerekir)."
        )
    env_adi = _PLAN_FIYAT_ENV[plan]
    price_id = os.getenv(env_adi, "").strip()
    if not price_id:
        raise ValueError(
            f"'{plan}' planı için Stripe Price ID ayarlanmamış — "
            f"{env_adi} ortam değişkenini Stripe Dashboard'daki gerçek "
            f"Price ID ile ayarlayın."
        )
    return price_id


def _stripe_api_key() -> str:
    # OMEHR kanonik isimdir; ürün adı geçişi sırasında eski BASDAS adını
    # geçici bir uyumluluk yedeği olarak koru (bkz. webhook_server.py'deki
    # aynı desen — OMEHR_STRIPE_WEBHOOK_SECRET / BASDAS_STRIPE_WEBHOOK_SECRET).
    sir = os.getenv("OMEHR_STRIPE_SECRET_KEY", "").strip() or os.getenv(
        "BASDAS_STRIPE_SECRET_KEY", ""
    ).strip()
    if not sir:
        raise ValueError(
            "OMEHR_STRIPE_SECRET_KEY ayarlanmamış — Stripe Checkout/Portal "
            "session'ı oluşturulamaz."
        )
    return sir


def create_checkout_session(tenant_id: str, plan: str, *, success_url: str,
                             cancel_url: str, customer_email: str | None = None) -> str:
    """Yeni bir ücretli abonelik için Stripe Checkout Session URL'i üretir.

    Çağıran (onboarding akışı), tenant kaydını 'beklemede' durumuyla
    ÖNCE oluşturmalı (bkz. tenant_registry.create_tenant(durum='beklemede'))
    — ödeme webhook'u (process_billing_event, olay_turu='subscription_created')
    geldiğinde bu kayıt 'aktif'e çevrilir. metadata'ya YAZILAN tenant_id,
    webhook_server.py'nin gelen olayı doğru kiracıyla eşleştirmesinin TEK
    yoludur (bkz. webhook_server._stripe_olay_cevir)."""
    import stripe

    price_id = price_id_for_plan(plan)
    stripe.api_key = _stripe_api_key()
    tenant_id = tenant_id.strip().upper()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=tenant_id,
        customer_email=customer_email or None,
        metadata={"tenant_id": tenant_id, "plan": plan},
        subscription_data={"metadata": {"tenant_id": tenant_id, "plan": plan}},
    )
    LOGGER.info(f"Stripe Checkout Session oluşturuldu: {tenant_id} -> plan={plan}")
    return session.url


def create_portal_session(tenant_id: str, *, return_url: str) -> str:
    """Var olan bir kiracı için Stripe Customer Portal URL'i üretir —
    kiracı yöneticisi buradan fatura geçmişini görür, kartını günceller
    veya aboneliğini iptal eder (hepsi Stripe tarafında; bu kod hiçbir
    kart verisi görmez/saklamaz).

    Yalnız DAHA ÖNCE bir Checkout'tan geçmiş (stripe_customer_id kaydı
    olan) kiracılar için çalışır — 'deneme' planındaki bir kiracının
    henüz Stripe'ta bir Customer kaydı yoktur."""
    import stripe

    kayit = tenant_registry.get_tenant(tenant_id)
    if kayit is None:
        raise ValueError(f"'{tenant_id}' kodlu bir kiracı kaydı bulunamadı.")
    customer_id = kayit.get("stripe_customer_id")
    if not customer_id:
        raise ValueError(
            f"'{tenant_id}' için henüz bir Stripe Customer kaydı yok — "
            "önce bir ücretli plana Checkout ile geçilmeli."
        )
    stripe.api_key = _stripe_api_key()
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url


def process_billing_event(tenant_id: str, olay_turu: str, plan: str | None = None, *,
                           stripe_customer_id: str | None = None,
                           stripe_subscription_id: str | None = None) -> dict:
    """Sağlayıcıdan BAĞIMSIZ, iç bir fatura olayını işler.

    tenant_id: hangi kiracıya ait olay (webhook payload'ından tenant_id
    ÇÖZÜLMÜŞ olarak buraya gelmelidir — genelde Stripe/iyzico
    müşteri/abonelik kaydının 'metadata' alanına tenant_id'yi
    YAZARAK eşleştirme yapılır).
    olay_turu: _OLAY_DURUM_ESLEMESI anahtarlarından biri.
    plan: yalnız 'subscription_created'/'subscription_renewed' için,
    hangi plana geçildiğini belirtir (yükseltme/düşürme durumunda).
    stripe_customer_id/stripe_subscription_id: webhook olayının
    taşıdığı Stripe kimlikleri — sonraki Customer Portal session'ları
    (bkz. create_portal_session) bunlara ihtiyaç duyar.
    """
    if olay_turu not in _OLAY_DURUM_ESLEMESI:
        raise ValueError(f"Bilinmeyen fatura olay türü: {olay_turu!r}")

    kayit = tenant_registry.get_tenant(tenant_id)
    if kayit is None:
        LOGGER.warning(f"billing olayı bilinmeyen kiracı için geldi: {tenant_id} ({olay_turu})")
        return {"islendi": False, "sebep": "kiracı kaydı bulunamadı"}

    yeni_durum = _OLAY_DURUM_ESLEMESI[olay_turu]

    if plan is not None and olay_turu in ("subscription_created", "subscription_renewed"):
        if plan not in PLAN_KOTALARI:
            raise ValueError(f"Bilinmeyen plan: {plan!r}")
        _plan_guncelle(tenant_id, plan)

    if stripe_customer_id or stripe_subscription_id:
        tenant_registry.set_stripe_ids(
            tenant_id, stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

    tenant_registry.set_status(tenant_id, yeni_durum)
    LOGGER.info(f"billing olayı işlendi: {tenant_id} -> {olay_turu} -> durum={yeni_durum}")
    return {"islendi": True, "tenant_id": tenant_id, "yeni_durum": yeni_durum, "plan": plan}


def _plan_guncelle(tenant_id: str, plan: str) -> None:
    """tenant_registry.py'de doğrudan 'plan günceller' bir fonksiyon
    YOK (yalnız create_tenant sırasında set ediliyor) — bu, mevcut
    şemayı KULLANARAK (UPDATE ile) plan + o plana karşılık gelen
    kotaları GÜNCELLER. tenant_registry.py'ye yeni bir fonksiyon EKLEMEK
    yerine, doğrudan aynı bağlantı/tablo üzerinden çalışır — tek doğru
    kaynak (tenants tablosu) korunur."""
    from services.db_backend import connect
    from services.runtime_paths import runtime_root

    kotalar = PLAN_KOTALARI[plan]
    con = connect(runtime_root() / "data" / "input_data.db")
    try:
        con.execute(
            "UPDATE tenants SET plan=?, sube_kotasi=?, kullanici_kotasi=? WHERE tenant_id=?",
            (plan, kotalar["sube_kotasi"], kotalar["kullanici_kotasi"], tenant_id.strip().upper()),
        )
        con.commit()
    finally:
        con.close()

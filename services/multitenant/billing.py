"""FATURALAMA İSKELETİ (Madde 2 — SaaS boşluğunun en büyüğü).

Bu modül, ÖDEME SAĞLAYICISINDAN (Stripe/iyzico) BAĞIMSIZ, saf iş
mantığını içerir: hangi plan hangi kotaya karşılık gelir, bir ödeme
olayı (abonelik oluşturuldu/güncellendi/iptal edildi/ödeme başarısız
oldu) geldiğinde tenant_registry.py'nin NASIL güncelleneceği.

Webhook TRANSPORT katmanı (imza doğrulama, HTTP alma) AYRI bir
modülde (webhook_server.py) — bu, iş mantığını GERÇEK ödeme sağlayıcı
hesabı OLMADAN test edilebilir kılar (Stripe/iyzico simüle edilmiş
olaylarla).
"""
from __future__ import annotations

from services.multitenant import tenant_registry
from services.observability import get_logger

LOGGER = get_logger("basdas.billing")

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


def process_billing_event(tenant_id: str, olay_turu: str, plan: str | None = None) -> dict:
    """Sağlayıcıdan BAĞIMSIZ, iç bir fatura olayını işler.

    tenant_id: hangi kiracıya ait olay (webhook payload'ından tenant_id
    ÇÖZÜLMÜŞ olarak buraya gelmelidir — genelde Stripe/iyzico
    müşteri/abonelik kaydının 'metadata' alanına tenant_id'yi
    YAZARAK eşleştirme yapılır).
    olay_turu: _OLAY_DURUM_ESLEMESI anahtarlarından biri.
    plan: yalnız 'subscription_created'/'subscription_renewed' için,
    hangi plana geçildiğini belirtir (yükseltme/düşürme durumunda).
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

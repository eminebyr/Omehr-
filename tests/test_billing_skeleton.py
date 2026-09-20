from __future__ import annotations

"""Faturalama İskeleti (Madde 2) — regresyon testleri.

services/billing.py (sağlayıcıdan bağımsız iş mantığı) ve
webhook_server.py (Stripe transport katmanı) için, GERÇEK imzalı
Stripe payload'larıyla uçtan uca doğrulama.
"""

import json
import time

import pytest


def test_payment_success_then_failure_updates_tenant_and_blocks_login(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant, get_tenant
    from services.billing import process_billing_event
    from services.security import set_password, authenticate

    create_tenant("FATURATEST", "Fatura Test Firması", plan="deneme")
    set_password("kullanici1", "GucluSifre123", tenant_id="FATURATEST")

    process_billing_event("FATURATEST", "subscription_created", plan="standart")
    kayit = get_tenant("FATURATEST")
    assert kayit["plan"] == "standart"
    assert kayit["durum"] == "aktif"

    sonuc = authenticate("kullanici1", "GucluSifre123", tenant_id="FATURATEST")
    assert sonuc[0] is True, "REGRESYON: ödeme başarılıyken giriş engellendi."

    process_billing_event("FATURATEST", "subscription_payment_failed")
    assert get_tenant("FATURATEST")["durum"] == "askida"

    sonuc2 = authenticate("kullanici1", "GucluSifre123", tenant_id="FATURATEST")
    assert sonuc2[0] is False, (
        "REGRESYON: ödeme başarısız olduğunda kullanıcı hâlâ giriş yapabiliyor "
        "— faturalama sistemi sonuçsuz kalıyor."
    )


def test_unknown_tenant_billing_event_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "data").mkdir()

    from services.billing import process_billing_event
    sonuc = process_billing_event("YOKTUR", "subscription_created", plan="temel")
    assert sonuc["islendi"] is False


def _imzali_stripe_istegi(payload: str, sir: str) -> dict:
    import stripe
    zaman = int(time.time())
    imzali_header = stripe.WebhookSignature._compute_signature(f"{zaman}.{payload}", sir)
    return {"Stripe-Signature": f"t={zaman},v1={imzali_header}", "Content-Type": "application/json"}


def test_real_signed_stripe_webhook_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_STRIPE_WEBHOOK_SECRET", "whsec_test_gizli")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant, get_tenant
    create_tenant("WHTEST", "Webhook Test", plan="deneme")

    import importlib
    import webhook_server
    importlib.reload(webhook_server)

    payload = json.dumps({
        "type": "customer.subscription.created",
        "data": {"object": {"metadata": {"tenant_id": "WHTEST", "plan": "standart"}}},
    })
    basliklar = _imzali_stripe_istegi(payload, "whsec_test_gizli")

    with webhook_server.app.test_client() as client:
        yanit = client.post("/webhook/stripe", data=payload, headers=basliklar)

    assert yanit.status_code == 200
    kayit = get_tenant("WHTEST")
    assert kayit["plan"] == "standart"
    assert kayit["durum"] == "aktif"


def test_forged_stripe_signature_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_STRIPE_WEBHOOK_SECRET", "whsec_test_gizli")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant, get_tenant
    create_tenant("SAHTE", "Sahte İstek Test", plan="deneme")

    import importlib
    import webhook_server
    importlib.reload(webhook_server)

    payload = json.dumps({
        "type": "customer.subscription.created",
        "data": {"object": {"metadata": {"tenant_id": "SAHTE", "plan": "kurumsal"}}},
    })

    with webhook_server.app.test_client() as client:
        yanit = client.post(
            "/webhook/stripe", data=payload,
            headers={"Stripe-Signature": "t=1,v1=gecersiz", "Content-Type": "application/json"},
        )

    assert yanit.status_code == 400, "REGRESYON: sahte imza kabul edildi!"
    assert get_tenant("SAHTE")["plan"] == "deneme", "REGRESYON: sahte istek veri değiştirdi!"


def test_price_id_for_plan_rejects_free_plan():
    from services.multitenant.billing import price_id_for_plan

    with pytest.raises(ValueError, match="ücretsizdir"):
        price_id_for_plan("deneme")


def test_price_id_for_plan_requires_env_var(monkeypatch):
    from services.multitenant.billing import price_id_for_plan

    monkeypatch.delenv("OMEHR_STRIPE_PRICE_TEMEL", raising=False)
    with pytest.raises(ValueError, match="Price ID ayarlanmamış"):
        price_id_for_plan("temel")


def test_plan_for_price_id_round_trip(monkeypatch):
    from services.multitenant.billing import plan_for_price_id

    monkeypatch.setenv("OMEHR_STRIPE_PRICE_STANDART", "price_abc123")
    assert plan_for_price_id("price_abc123") == "standart"
    assert plan_for_price_id("price_bilinmeyen_bir_id") is None


def test_create_checkout_session_sends_correct_metadata_to_stripe(tmp_path, monkeypatch):
    """Checkout Session'a yazılan tenant_id/plan metadata'sı, webhook'un
    (customer.subscription.created) doğru kiracıyı bulabilmesinin TEK
    yoludur — bu test o sözleşmenin bozulmadığını doğrular."""
    import stripe

    from services.multitenant import billing
    from services.tenant_registry import create_tenant

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_STRIPE_SECRET_KEY", "sk_test_gizli")
    monkeypatch.setenv("OMEHR_STRIPE_PRICE_STANDART", "price_standart123")
    (tmp_path / "data").mkdir()
    create_tenant("CHECKOUTTEST", "Checkout Test", plan="standart", durum="beklemede")

    yakalanan = {}

    class _SahteSession:
        url = "https://checkout.stripe.com/test-session"

    def _sahte_create(**kwargs):
        yakalanan.update(kwargs)
        return _SahteSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", _sahte_create)

    url = billing.create_checkout_session(
        "checkouttest", "standart",
        success_url="https://app.example.com/basarili",
        cancel_url="https://app.example.com/iptal",
        customer_email="test@example.com",
    )

    assert url == "https://checkout.stripe.com/test-session"
    assert stripe.api_key == "sk_test_gizli"
    assert yakalanan["line_items"] == [{"price": "price_standart123", "quantity": 1}]
    assert yakalanan["client_reference_id"] == "CHECKOUTTEST"
    assert yakalanan["metadata"] == {"tenant_id": "CHECKOUTTEST", "plan": "standart"}
    assert yakalanan["subscription_data"]["metadata"] == {"tenant_id": "CHECKOUTTEST", "plan": "standart"}


def test_create_portal_session_requires_prior_stripe_customer(tmp_path, monkeypatch):
    from services.multitenant import billing
    from services.tenant_registry import create_tenant

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "data").mkdir()
    create_tenant("PORTALSIZ", "Portal Test", plan="deneme")

    with pytest.raises(ValueError, match="Stripe Customer kaydı yok"):
        billing.create_portal_session("PORTALSIZ", return_url="https://app.example.com/")


def test_create_portal_session_returns_url_for_known_customer(tmp_path, monkeypatch):
    import stripe

    from services.multitenant import billing
    from services.tenant_registry import create_tenant, set_stripe_ids

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("OMEHR_STRIPE_SECRET_KEY", "sk_test_gizli")
    (tmp_path / "data").mkdir()
    create_tenant("PORTALLI", "Portal Test 2", plan="standart")
    set_stripe_ids("PORTALLI", stripe_customer_id="cus_abc123")

    yakalanan = {}

    class _SahteSession:
        url = "https://billing.stripe.com/session/test"

    def _sahte_create(**kwargs):
        yakalanan.update(kwargs)
        return _SahteSession()

    monkeypatch.setattr(stripe.billing_portal.Session, "create", _sahte_create)

    url = billing.create_portal_session("PORTALLI", return_url="https://app.example.com/")
    assert url == "https://billing.stripe.com/session/test"
    assert yakalanan == {"customer": "cus_abc123", "return_url": "https://app.example.com/"}


def test_set_stripe_ids_partial_update_preserves_existing(tmp_path, monkeypatch):
    from services.tenant_registry import create_tenant, get_tenant, set_stripe_ids

    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "data").mkdir()
    create_tenant("STRIPEID", "Stripe ID Test", plan="temel")

    set_stripe_ids("STRIPEID", stripe_customer_id="cus_1")
    assert get_tenant("STRIPEID")["stripe_customer_id"] == "cus_1"
    assert get_tenant("STRIPEID")["stripe_subscription_id"] is None

    set_stripe_ids("STRIPEID", stripe_subscription_id="sub_1")
    kayit = get_tenant("STRIPEID")
    assert kayit["stripe_customer_id"] == "cus_1", "REGRESYON: partial update önceki customer_id'yi sildi"
    assert kayit["stripe_subscription_id"] == "sub_1"


def test_pending_tenant_activated_by_real_signed_checkout_webhook(tmp_path, monkeypatch):
    """Tam akış: 'beklemede' kiracı -> gerçek imzalı Stripe webhook'u
    (customer.subscription.created, customer/id alanları dolu) -> 'aktif'
    + stripe_customer_id/stripe_subscription_id kaydedilmiş olmalı."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_STRIPE_WEBHOOK_SECRET", "whsec_test_gizli")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant, get_tenant
    create_tenant("BEKLEYENFIRMA", "Bekleyen Firma", plan="standart", durum="beklemede")

    import importlib
    import webhook_server
    importlib.reload(webhook_server)

    payload = json.dumps({
        "type": "customer.subscription.created",
        "data": {"object": {
            "id": "sub_gercek123", "customer": "cus_gercek123",
            "metadata": {"tenant_id": "BEKLEYENFIRMA", "plan": "standart"},
        }},
    })
    basliklar = _imzali_stripe_istegi(payload, "whsec_test_gizli")

    with webhook_server.app.test_client() as client:
        yanit = client.post("/webhook/stripe", data=payload, headers=basliklar)

    assert yanit.status_code == 200
    kayit = get_tenant("BEKLEYENFIRMA")
    assert kayit["durum"] == "aktif"
    assert kayit["stripe_customer_id"] == "cus_gercek123"
    assert kayit["stripe_subscription_id"] == "sub_gercek123"


def test_portal_self_service_upgrade_webhook_updates_plan_and_quota(tmp_path, monkeypatch):
    """Kiracı, Stripe Customer Portal'dan KENDİ KENDİNE 'standart'tan
    'kurumsal'a yükseltirse Stripe customer.subscription.updated olayını
    gönderir — bu, plan_for_price_id ile bizim plan adımıza çevrilip
    kota/plan güncellenmelidir (webhook_server._stripe_olay_cevir)."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_STRIPE_WEBHOOK_SECRET", "whsec_test_gizli")
    monkeypatch.setenv("OMEHR_STRIPE_PRICE_KURUMSAL", "price_kurumsal_gercek")
    (tmp_path / "data").mkdir()

    from services.tenant_registry import create_tenant, get_tenant, set_stripe_ids
    create_tenant("YUKSELEN", "Yükselen Firma", plan="standart")
    set_stripe_ids("YUKSELEN", stripe_customer_id="cus_yukselen", stripe_subscription_id="sub_yukselen")

    import importlib
    import webhook_server
    importlib.reload(webhook_server)

    payload = json.dumps({
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_yukselen", "customer": "cus_yukselen",
            "metadata": {"tenant_id": "YUKSELEN"},
            "items": {"data": [{"price": {"id": "price_kurumsal_gercek"}}]},
        }},
    })
    basliklar = _imzali_stripe_istegi(payload, "whsec_test_gizli")

    with webhook_server.app.test_client() as client:
        yanit = client.post("/webhook/stripe", data=payload, headers=basliklar)

    assert yanit.status_code == 200
    kayit = get_tenant("YUKSELEN")
    assert kayit["durum"] == "aktif"
    assert kayit["plan"] == "kurumsal"
    assert kayit["sube_kotasi"] == 10_000


def test_webhook_without_secret_configured_refuses_safely(tmp_path, monkeypatch):
    """BASDAS_STRIPE_WEBHOOK_SECRET hiç ayarlanmamışsa, sunucu (imza
    kontrolünü ATLAYIP güvenilir kabul etmek yerine) GÜVENLİ şekilde
    reddetmeli."""
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("BASDAS_STRIPE_WEBHOOK_SECRET", raising=False)
    (tmp_path / "data").mkdir()

    import importlib
    import webhook_server
    importlib.reload(webhook_server)

    with webhook_server.app.test_client() as client:
        yanit = client.post(
            "/webhook/stripe", data="{}",
            headers={"Stripe-Signature": "t=1,v1=x", "Content-Type": "application/json"},
        )
    assert yanit.status_code == 500

from __future__ import annotations

"""Faturalama İskeleti (Madde 2) — regresyon testleri.

services/billing.py (sağlayıcıdan bağımsız iş mantığı) ve
webhook_server.py (Stripe transport katmanı) için, GERÇEK imzalı
Stripe payload'larıyla uçtan uca doğrulama.
"""

import json
import time


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

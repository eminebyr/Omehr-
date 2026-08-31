"""WEBHOOK SUNUCUSU — Stripe ödeme olaylarını alır (Madde 2).

Streamlit'in KENDİSİ dışarıdan gelen HTTP POST isteklerini (webhook)
alamaz — yalnız kendi sayfa render protokolünü sunar. Bu YÜZDEN,
ödeme sağlayıcısının (Stripe) webhook'larını almak için AYRI, küçük
bir Flask süreci gerekir. Bu süreç web/app.py'den TAMAMEN bağımsız
çalışır (docker-compose.yml'de ayrı bir servis olarak, farklı bir
portta).

iyzico kullanmak isterseniz: bu dosyadaki `_stripe_olay_cevir()`
fonksiyonunun yerine iyzico'nun kendi webhook payload formatını (ve
imza doğrulama yöntemini) kullanan bir eşdeğerini yazmanız yeterli —
services/billing.py (iş mantığı) hiç değişmeden kalır, çünkü o
sağlayıcıdan tamamen bağımsız, iç isimlerle (subscription_created
vb.) çalışır.

Çalıştırma: python3 webhook_server.py (varsayılan port 8502)
Ortam değişkenleri:
  BASDAS_STRIPE_WEBHOOK_SECRET — Stripe Dashboard'dan alınan imza sırrı
  BASDAS_WEBHOOK_PORT — varsayılan 8502
"""
from __future__ import annotations

import os

from flask import Flask, request, jsonify

from services.billing import process_billing_event
from services.observability import get_logger

LOGGER = get_logger("basdas.webhook")
app = Flask(__name__)


def _stripe_olay_cevir(stripe_olay) -> tuple[str, str, str | None] | None:
    """Stripe'ın KENDİ olay isimlerini (customer.subscription.created
    gibi) bizim iç modelimize (subscription_created gibi) çevirir.
    (tenant_id, olay_turu, plan) döner — tenant_id, Stripe abonelik/
    müşteri kaydının 'metadata' alanına YAZILMIŞ olmalıdır (Stripe
    Dashboard'da müşteri oluştururken ya da Checkout Session'da
    metadata={'tenant_id': '...'} ile ayarlanır).

    StripeObject ve düz test sözlükleri Mapping arayüzünü (.get) destekler.
    Eski ``to_dict()`` çağrısı Stripe 14'te deprecated olduğu için doğrudan
    bu ortak arayüz kullanılır."""
    tur = stripe_olay.get("type", "")
    veri = stripe_olay.get("data", {}).get("object", {})
    metadata = dict(veri.get("metadata") or {})
    tenant_id = metadata.get("tenant_id")
    if not tenant_id:
        LOGGER.warning(f"Stripe olayında tenant_id metadata'sı yok: {tur}")
        return None

    if tur == "customer.subscription.created":
        plan = metadata.get("plan", "temel")
        return tenant_id, "subscription_created", plan
    if tur == "invoice.paid":
        return tenant_id, "subscription_renewed", None
    if tur == "invoice.payment_failed":
        return tenant_id, "subscription_payment_failed", None
    if tur == "customer.subscription.deleted":
        return tenant_id, "subscription_canceled", None
    return None


@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    imza = request.headers.get("Stripe-Signature", "")
    sir = os.getenv("BASDAS_STRIPE_WEBHOOK_SECRET", "")

    if not sir:
        LOGGER.error("BASDAS_STRIPE_WEBHOOK_SECRET ayarlanmamış — webhook reddediliyor.")
        return jsonify({"hata": "sunucu yapılandırması eksik"}), 500

    try:
        import stripe
        olay = stripe.Webhook.construct_event(payload, imza, sir)
    except Exception as exc:
        LOGGER.warning(f"Stripe webhook imza doğrulama başarısız: {exc}")
        return jsonify({"hata": "geçersiz imza"}), 400

    cevrilen = _stripe_olay_cevir(olay)
    if cevrilen is None:
        return jsonify({"islendi": False, "sebep": "ilgisiz/eşleşmeyen olay türü"}), 200

    tenant_id, olay_turu, plan = cevrilen
    try:
        sonuc = process_billing_event(tenant_id, olay_turu, plan=plan)
        return jsonify(sonuc), 200
    except Exception as exc:
        LOGGER.error(f"billing olayı işlenemedi: {tenant_id}/{olay_turu}: {exc}")
        return jsonify({"hata": str(exc)}), 500


@app.route("/webhook/health", methods=["GET"])
def health():
    return jsonify({"durum": "calisiyor"}), 200


# ============================================================================
# BULUT MOTORU KÖPRÜSÜ (Vercel entegrasyonu — 2026-08-16 eklendi)
# ----------------------------------------------------------------------------
# Vercel'deki hafif arayüz (Next.js), motoru KENDİ İÇİNDE çalıştıramaz —
# Vercel'in serverless Python fonksiyonları kalıcı dosya sistemine sahip
# değildir, oysa bu motor (src/engine_core.py) input Excel'i VE referans
# kontrol dosyalarını (reference/*.xlsx) DİSKTEN okur. Bu ikisi temelden
# uyumsuzdur (bkz. ilgili konuşma notu).
#
# Çözüm: motoru zaten kalıcı dosya sistemine sahip OLAN bu sunucuda (Railway)
# çalıştırıp SONUCU JSON olarak döndürmek. Vercel yalnızca bu endpoint'e bir
# HTTP isteği atar — kendi içinde hiçbir Python/pandas kodu ÇALIŞTIRMAZ.
#
# GÜVENLİK: bu endpoint dışarıya (internete) açık bir Railway domain'i
# üzerinden erişilebilir olacağı için, paylaşılan bir gizli anahtar
# (BASDAS_ENGINE_API_SECRET) ile korunur — yalnız bu anahtarı bilen (Vercel
# tarafındaki sunucu kodu) motoru tetikleyebilir.
# ============================================================================
@app.route("/api/run-engine", methods=["POST"])
def run_engine_for_cloud():
    beklenen_sir = os.getenv("BASDAS_ENGINE_API_SECRET", "")
    gelen_sir = request.headers.get("X-Engine-Secret", "")
    if not beklenen_sir:
        LOGGER.error("BASDAS_ENGINE_API_SECRET ayarlanmamış — /api/run-engine reddediliyor.")
        return jsonify({"error": "sunucu yapılandırması eksik"}), 500
    if not gelen_sir or gelen_sir != beklenen_sir:
        LOGGER.warning("/api/run-engine: geçersiz veya eksik X-Engine-Secret.")
        return jsonify({"error": "yetkisiz"}), 401

    import time
    from services.cloud_engine_bridge import run_official_engine_summary

    started = time.perf_counter()
    try:
        summary = run_official_engine_summary()
    except Exception as exc:
        LOGGER.error(f"/api/run-engine: motor çalıştırılamadı: {exc}")
        return jsonify({"error": "Motor çalıştırılamadı.", "detail": str(exc)[:500]}), 500

    summary["duration_ms"] = int((time.perf_counter() - started) * 1000)
    summary["status"] = "COMPLETED"
    return jsonify({"ok": True, "run": summary}), 200


if __name__ == "__main__":
    port = int(os.getenv("BASDAS_WEBHOOK_PORT", "8502"))
    app.run(host="0.0.0.0", port=port)

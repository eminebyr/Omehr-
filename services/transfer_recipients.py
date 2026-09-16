"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/transfer/transfer_recipients.py

services/transfer/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Transfer / Atama / Rotasyon" alanı). Şu an bu
modülün dışarıdan (bu bounded-context dışından) hiç çağıranı yok
(bizzat doğrulandı) — yine de tutarlılık için diğerleriyle aynı
şekilde shim'lendi.
"""
from services.transfer.transfer_recipients import *  # noqa: F401,F403
from services.transfer.transfer_recipients import transfer_recipients

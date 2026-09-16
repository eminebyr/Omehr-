"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/transfer/transfer_lifecycle.py

services/transfer/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Transfer / Atama / Rotasyon" alanı).
"""
from services.transfer.transfer_lifecycle import *  # noqa: F401,F403
from services.transfer.transfer_lifecycle import cancel_transfer, redirect_transfer

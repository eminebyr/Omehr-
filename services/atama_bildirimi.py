"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/transfer/atama_bildirimi.py

services/transfer/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Transfer / Atama / Rotasyon" alanı).
"""
from services.transfer.atama_bildirimi import *  # noqa: F401,F403
from services.transfer.atama_bildirimi import create_assignment_notice

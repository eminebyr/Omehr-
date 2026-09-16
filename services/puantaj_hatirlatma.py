"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/puantaj_hatirlatma.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı).
"""
from services.reporting.puantaj_hatirlatma import *  # noqa: F401,F403
from services.reporting.puantaj_hatirlatma import gunluk_puantaj_hatirlatma_gonder

"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/reporting/executive_advisor.py

services/reporting/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Raporlama / Dağıtım" alanı). Şu an bu modülün
dışarıdan hiç çağıranı yok (bizzat doğrulandı) — yine de tutarlılık
için diğerleriyle aynı şekilde shim'lendi.
"""
from services.reporting.executive_advisor import *  # noqa: F401,F403
from services.reporting.executive_advisor import advise

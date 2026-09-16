"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/download_audit.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı).
"""
from services.ops.download_audit import *  # noqa: F401,F403
from services.ops.download_audit import kaydet, son_kayitlar

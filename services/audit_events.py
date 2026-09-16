"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/audit_events.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı).
"""
from services.ops.audit_events import *  # noqa: F401,F403
from services.ops.audit_events import _connect, record, recent

"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/performance_log.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı).
"""
from services.ops.performance_log import *  # noqa: F401,F403
from services.ops.performance_log import cache_hit_rate, log_performance, track_page_render

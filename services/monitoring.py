"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/monitoring.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı). Şu an bu modülün dışarıdan hiç
çağıranı yok (bizzat doğrulandı — monitoring_server.py bile kendi
doğrudan uygulamasını kullanıyor, bu modülü ÇAĞIRMIYOR) — yine de
tutarlılık için diğerleriyle aynı şekilde shim'lendi.
"""
from services.ops.monitoring import *  # noqa: F401,F403
from services.ops.monitoring import prometheus_text, snapshot

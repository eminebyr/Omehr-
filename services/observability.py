"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/observability.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı). Alt paket BİLEREK "ops" adını
taşır, "observability" veya "monitoring" değil — aksi halde bu düz
shim dosyaları, aynı ada sahip bir alt paket tarafından Python'un
import çözümlemesinde SESSİZCE GÖLGELENİRDİ (bkz. services/security_auth/
taşımasındaki aynı bulgu).
"""
from services.ops.observability import *  # noqa: F401,F403
from services.ops.observability import get_logger, write_runtime_status

"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/safe_exec.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı). `_LOGGER`,
tests/test_safe_exec.py tarafından doğrudan içe aktarılır — bu yüzden
açıkça yeniden dışa aktarılır.
"""
from services.ops.safe_exec import *  # noqa: F401,F403
from services.ops.safe_exec import _LOGGER, log_swallowed, recent_swallowed_errors, swallow

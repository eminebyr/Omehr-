"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/ops/run_lineage.py

services/ops/ bounded-context'ine taşındı (bkz. SERVICE_BOUNDARIES.md
"Operasyon / İzleme / Denetim" alanı).
"""
from services.ops.run_lineage import *  # noqa: F401,F403
from services.ops.run_lineage import (
    APPLICATION_VERSION,
    baslat,
    bitir,
    model_bilgisini_ekle,
    sayfa_ozetini_ekle,
    son_calistirmalar,
    yeni_run_id,
)

"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/ai_feedback.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı). `_connect`
(private), tests/test_ai_feedback.py tarafından doğrudan içe aktarılır
— bu yüzden açıkça yeniden dışa aktarılır.
"""
from services.system_config.ai_feedback import *  # noqa: F401,F403
from services.system_config.ai_feedback import (
    VALID_DECISIONS,
    _connect,
    acceptance_summary,
    history,
    record_decision,
    update_outcome,
)

"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/system_config/veri_toplama.py

services/system_config/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Sistem / Yapılandırma" alanı).
"""
from services.system_config.veri_toplama import *  # noqa: F401,F403
from services.system_config.veri_toplama import (
    ik_finans_uygula,
    ik_finans_uygula_ve_serialize,
    saha_olcumu_uygula,
    saha_olcumu_uygula_ve_serialize,
    vardiya_pik_turet,
    vardiya_pik_turet_ve_serialize,
)

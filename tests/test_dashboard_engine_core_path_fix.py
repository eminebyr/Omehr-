from __future__ import annotations

"""Genel Özet KPI'ları — engine_core yol hatası regresyon testi.

Önceden _build_model_from_sheets(), engine_core.py'yi _root()/"src"
(kiracının ÇALIŞMA ZAMANI veri dizini) altında ARIYORDU — ama
engine_core.py KOD DEPOSUNUN (CODE_ROOT) src/ klasöründe yaşar.
Bu, HER GERÇEK dağıtımda (runtime_root ve code_root farklı yollar
olduğu için) sessizce ModuleNotFoundError'a yol açıyordu — hata
yutulduğu için kullanıcı hiçbir uyarı görmüyordu, yalnız KPI kartları
main.py'nin resmi rakamları YERİNE eski, kalibre edilmemiş bir
hesabı (GERÇEKTEN YANLIŞ sayılar) gösteriyordu. Bizzat gerçek bir
Streamlit sunucusu + ekran görüntüsü testiyle bulundu ve doğrulandı.
"""


def test_dashboard_uses_shared_model_from_code_root_not_runtime_root():
    """Panel, kod deposundan import edilen ortak dashboard modelini kullanır;
    çalışma verisi dizininde dinamik Python modülü aramaz."""
    kaynak = open("web/app.py", encoding="utf-8").read()
    assert "from services.dashboard_model import build_dashboard_model" in kaynak
    assert "return build_dashboard_model(" in kaynak
    assert '_root() / "src"' not in kaynak, (
        "REGRESYON: panel çalışma verisi dizininde Python modülü arıyor."
    )
    assert "_ec.load()" not in kaynak, (
        "REGRESYON: panel, read_input ile yüklenmiş sayfalar varken kaynağı "
        "engine_core.load() üzerinden ikinci kez okuyor."
    )


def test_engine_core_module_actually_importable_from_code_root():
    """engine_core.py'nin GERÇEKTEN CODE_ROOT/src altında bulunduğunu
    ve doğru yoldan import edilebildiğini doğrular."""
    import sys
    from pathlib import Path

    code_root = Path(__file__).resolve().parents[1]
    src_yolu = str(code_root / "src")
    if src_yolu not in sys.path:
        sys.path.insert(0, src_yolu)
    import engine_core  # noqa: F401 — yalnız import edilebildiğini doğrula
    assert hasattr(engine_core, "load")
    assert hasattr(engine_core, "state")
    assert hasattr(engine_core, "kpis")

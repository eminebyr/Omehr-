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


def test_engine_core_import_uses_code_root_not_runtime_root():
    """web/app.py'nin engine_core.py'yi ARTIK CODE_ROOT/src altında
    aradığını (runtime_root/src DEĞİL) kod incelemesiyle doğrular."""
    kaynak = open("web/app.py", encoding="utf-8").read()
    assert 'CODE_ROOT / "src"' in kaynak, (
        "REGRESYON: engine_core importu artık CODE_ROOT/src kullanmıyor "
        "olabilir — bu, gerçek dağıtımda sessizce yanlış KPI gösterimine "
        "yol açar (runtime_root ve code_root farklı yollar olduğunda)."
    )
    assert '_root() / "src"' not in kaynak, (
        "REGRESYON: engine_core hâlâ (yanlış) _root()/src altında aranıyor."
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

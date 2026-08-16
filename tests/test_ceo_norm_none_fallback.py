from pathlib import Path


def test_ceo_scorecard_has_python_norm_fallback():
    source = (Path(__file__).parents[1] / "web" / "tab_modules" / "ceo_ozet.py").read_text(encoding="utf-8")
    assert '"_Norm Kadro": ("Norm", "sum")' in source
    assert '"_Norm Eksiği": ("Eksik", "sum")' in source
    assert '"_Norm Fazlası": ("Fazla", "sum")' in source
    assert '_hesaplanan_uyum' in source
    assert '.fillna(_hesaplanan_uyum)' in source

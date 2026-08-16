"""Gerçek bir .xlsx dosyası üretip okuyan uçtan uca (mini) test.

Diğer testlerin çoğu DataFrame'lerle çalışıyor (hızlı, dosya sistemine
dokunmuyor). Bu dosya ise conftest.sample_input_workbook fixture'ının
GERÇEKTEN pandas ile okunabilir, services.schema_validation'ın zorunlu
gördüğü sütunları karşılayan bir input dosyası ürettiğini doğrular —
"gerçek inputa dokunmadan, ama gerçek bir Excel dosyasıyla" test etmenin
küçük bir örneği.
"""
from __future__ import annotations

import pandas as pd

from services.schema_validation import validate


def test_synthetic_workbook_is_readable_and_has_expected_sheets(sample_input_workbook):
    assert sample_input_workbook.is_file()
    sheets = pd.read_excel(sample_input_workbook, sheet_name=None)
    for beklenen in ("Fact_Norm", "Fact_Mevcut", "Dim_Magaza", "Dim_Unvan"):
        assert beklenen in sheets, f"'{beklenen}' sayfası üretilen dosyada yok"


def test_synthetic_workbook_passes_schema_validation(sample_input_workbook):
    sheets = pd.read_excel(sample_input_workbook, sheet_name=None)
    sonuc = validate(sheets)  # zorunlu sütun eksikse SchemaValidationError fırlatırdı
    assert sonuc.kritik_hatalar == []


def test_synthetic_workbook_lives_at_the_centrally_configured_path(sample_input_workbook):
    from services.settings import input_file_name

    assert sample_input_workbook.name == input_file_name()
    assert sample_input_workbook.parent.name == "input"

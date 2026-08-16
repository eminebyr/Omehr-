"""services.settings testleri — merkezi input dosya adı ayarı."""
from __future__ import annotations

from pathlib import Path

from services.settings import DEFAULT_INPUT_FILE_NAME, input_file_name, input_path


def test_default_input_file_name_is_the_expected_workbook():
    assert input_file_name() == DEFAULT_INPUT_FILE_NAME
    assert input_file_name().endswith(".xlsx")


def test_input_path_joins_root_input_and_filename(tmp_path):
    result = input_path(tmp_path)
    assert result == tmp_path / "input" / DEFAULT_INPUT_FILE_NAME


def test_env_var_overrides_default_filename(monkeypatch):
    monkeypatch.setenv("BASDAS_INPUT_FILE", "OZEL_INPUT.xlsx")
    assert input_file_name() == "OZEL_INPUT.xlsx"


def test_blank_env_var_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("BASDAS_INPUT_FILE", "   ")
    assert input_file_name() == DEFAULT_INPUT_FILE_NAME


def test_input_path_accepts_string_root(tmp_path):
    result = input_path(str(tmp_path))
    assert isinstance(result, Path)
    assert result.name == DEFAULT_INPUT_FILE_NAME

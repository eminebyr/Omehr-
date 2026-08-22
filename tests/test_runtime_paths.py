"""services.runtime_paths testleri — izole çalışma zamanı kökü ve tenant kodu."""
from __future__ import annotations

import pytest


def test_runtime_root_creates_expected_subfolders(isolated_root):
    from services import runtime_paths

    root = runtime_paths.runtime_root()
    assert root == isolated_root
    for name in ("input", "output", "data", "logs", "archive", "backup", "reference", "assets"):
        assert (root / name).is_dir(), f"'{name}' klasörü oluşturulmadı"


def test_runtime_root_uses_env_override(isolated_root):
    from services import runtime_paths

    assert runtime_paths.runtime_root() == isolated_root


def test_tenant_code_default_is_basdas(monkeypatch):
    from services import runtime_paths

    monkeypatch.delenv("OMEHR_TENANT", raising=False)
    assert runtime_paths.tenant_code() == "BASDAS"


def test_tenant_code_accepts_valid_custom_code(monkeypatch):
    from services import runtime_paths

    monkeypatch.setenv("OMEHR_TENANT", "MUSTERI_2")
    assert runtime_paths.tenant_code() == "MUSTERI_2"


def test_tenant_code_rejects_lowercase_or_invalid_chars(monkeypatch):
    from services import runtime_paths

    # küçük harfle yazılmış bir kod, büyük harfe çevrildiğinde orijinaliyle
    # eşleşmiyor -> ValueError (kod, sadece zaten-normalize edilmiş girdileri kabul eder)
    monkeypatch.setenv("OMEHR_TENANT", "gecersiz kod!")
    with pytest.raises(ValueError):
        runtime_paths.tenant_code()


def test_code_root_points_to_project_root():
    from services import runtime_paths

    root = runtime_paths.code_root()
    assert (root / "services").is_dir()
    assert (root / "web").is_dir()

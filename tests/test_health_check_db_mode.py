from __future__ import annotations

"""system_health_check.py — DB modunda eksik input dosyası artık
kritik hata SAYILMAMALI (bizzat kanıtlandı: gerçek bir Windows
kurulumunda, DB moduna geçilip henüz Excel yüklenmemişken sağlık
kontrolü kurulumu tamamen durduruyordu)."""

import subprocess
import sys


def test_missing_input_not_critical_in_db_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_INPUT_SOURCE", "db")
    monkeypatch.delenv("BASDAS_MAIL_DRY_RUN", raising=False)

    sonuc = subprocess.run(
        [sys.executable, "system_health_check.py"],
        capture_output=True, text=True, cwd=".",
        env={**__import__("os").environ, "BASDAS_RUNTIME_ROOT": str(tmp_path), "BASDAS_INPUT_SOURCE": "db"},
    )
    assert sonuc.returncode == 0, (
        f"REGRESYON: DB modunda eksik input dosyası hâlâ kurulumu durduruyor.\n{sonuc.stdout}"
    )


def test_missing_input_still_critical_in_excel_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("BASDAS_INPUT_SOURCE", raising=False)

    import os
    env = dict(os.environ)
    env["BASDAS_RUNTIME_ROOT"] = str(tmp_path)
    env.pop("BASDAS_INPUT_SOURCE", None)

    sonuc = subprocess.run(
        [sys.executable, "system_health_check.py"],
        capture_output=True, text=True, cwd=".", env=env,
    )
    assert sonuc.returncode != 0, (
        "REGRESYON: normal Excel modunda eksik input dosyası artık kritik "
        "sayılmıyor — bu, GERÇEK bir eksik dosya sorununu gizleyebilir."
    )

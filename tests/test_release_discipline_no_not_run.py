from __future__ import annotations

"""Release disiplini — 'NOT_RUN' bir daha asla olmasın.

Önceden bir paket, --verify bayrağı UNUTULARAK üretilirse manifest
sessizce "NOT_RUN" yazardı (OMEHR_SON_HALI.zip'te tam olarak bu oldu).
Artık doğrulama VARSAYILAN, ve atlanırsa bile durum AÇIKÇA
"SKIPPED_BY_USER" yazar — asla belirsiz "NOT_RUN" olmaz.
"""

import json
import zipfile


def test_build_clean_zip_without_verification_param_is_explicit_not_ambiguous(tmp_path):
    from tools.build_clean_package import build_clean_zip

    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    (kaynak / "a.py").write_text("# test", encoding="utf-8")
    hedef = tmp_path / "paket.zip"
    build_clean_zip(kaynak, hedef)

    with zipfile.ZipFile(hedef) as z:
        manifest = json.loads(z.read("RELEASE_MANIFEST.json"))

    durum = manifest["verification"]["status"]
    assert durum != "NOT_RUN", "REGRESYON: belirsiz 'NOT_RUN' durumu geri geldi."
    assert durum == "UNKNOWN_UNVERIFIED"
    assert "warning" in manifest["verification"]


def test_cli_skip_verify_flag_produces_explicit_skipped_status(tmp_path):
    import subprocess
    import sys

    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    (kaynak / "a.py").write_text("# test", encoding="utf-8")
    hedef = tmp_path / "paket.zip"

    sonuc = subprocess.run(
        [sys.executable, "tools/build_clean_package.py", str(kaynak), str(hedef), "--skip-verify"],
        capture_output=True, text=True, cwd=".",
    )
    assert sonuc.returncode == 0
    assert "TESLİM EDİLMEMELİDİR" in sonuc.stdout

    with zipfile.ZipFile(hedef) as z:
        manifest = json.loads(z.read("RELEASE_MANIFEST.json"))
    assert manifest["verification"]["status"] == "SKIPPED_BY_USER"

from __future__ import annotations

"""config_norm_rules.json (proje kök dizininde, pakete dahil edilen
dosya) — regresyon testi.

Bu dosyada bir kez, kendi belgelediği kuralla ("aynı aile içindeki
toplam aktif personel toplam normu karşılıyorsa dengelenir") ÇELİŞEN
bir 'separate_roles' listesi ve 'minimum_main_current: 0' bulundu —
bu, family reconciliation'ı fiilen devre dışı bırakıyordu VE pakete
dahil edildiği için GERÇEK ÜRETİMDE (BASDAS_RUNTIME_ROOT set
edilmeden çalıştırıldığında) etkili olabilirdi.
"""

import json
from pathlib import Path


def test_shipped_norm_rules_config_does_not_disable_family_reconciliation():
    yol = Path(__file__).resolve().parents[1] / "config_norm_rules.json"
    if not yol.is_file():
        return  # dosya yoksa varsayılanlar zaten güvenli
    veri = json.loads(yol.read_text(encoding="utf-8"))
    ayrik_roller = veri.get("separate_roles") or []
    assert not any("YARDIMCI" in str(r).upper() for r in ayrik_roller), (
        "REGRESYON: config_norm_rules.json'daki separate_roles, yardımcı "
        "unvanları aile dengelemesinden hariç tutuyor — bu, dosyanın "
        "kendi belgelediği kuralla çelişir ve pakete dahil edildiği için "
        "gerçek üretimi etkileyebilir."
    )
    min_main = (veri.get("assistant_balance") or {}).get("minimum_main_current")
    assert min_main is None or min_main >= 1, (
        f"REGRESYON: minimum_main_current={min_main} — bu, '0 ana personelle "
        "norm asla kapanmaz' güvenlik kuralını etkisiz kılar."
    )


def test_main_py_produces_correct_kpis_with_default_root(tmp_path, monkeypatch):
    """Gerçek kullanıcı deneyimini simüle eder: BASDAS_RUNTIME_ROOT hiç
    set edilmeden (varsayılan = proje kök dizini), main.py'nin
    yayınlanan config_norm_rules.json ile bile doğru KPI ürettiğini
    doğrular.

    DÜZELTME (test izolasyonu): runtime_root()'un varsayılan davranışı
    her zaman CODE_ROOT'u (kodun fiziksel konumu, subprocess cwd'sinden
    BAĞIMSIZ) kullanır — bu yüzden bu test GERÇEKTEN paylaşılan proje
    input/ klasörüne yazar. Dosya artık çalıştırma ÖNCESİ yedeklenip
    SONRASINDA (başarılı/başarısız fark etmeksizin) geri yükleniyor."""
    import subprocess
    import sys
    import os
    import shutil

    proje_kok = Path(__file__).resolve().parents[1]
    input_dosyasi = proje_kok / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    yedek = tmp_path / "input_yedek.xlsx"
    if input_dosyasi.exists():
        shutil.copyfile(input_dosyasi, yedek)

    env = dict(os.environ)
    env.pop("BASDAS_RUNTIME_ROOT", None)
    env["BASDAS_MAIL_DRY_RUN"] = "1"

    try:
        sonuc = subprocess.run(
            [sys.executable, "main.py"], cwd=proje_kok, env=env,
            capture_output=True, text=True, timeout=280,
        )
        assert sonuc.returncode == 0, f"main.py başarısız: {sonuc.stderr[-2000:]}"
        assert '"Aktif Mevcut": 596' in sonuc.stdout
        assert '"Norm Eksiği": 49' in sonuc.stdout
        assert '"Norm Fazlası": 23' in sonuc.stdout
    finally:
        if yedek.exists():
            shutil.copyfile(yedek, input_dosyasi)

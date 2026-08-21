"""Merkezi uygulama ayarları.

Amaç: kod tabanında tekrar eden "sihirli sabitleri" tek yerde tutmak.
Ana input Excel dosyasının adı önceden ~15 dosyada elle yazılıydı; artık
tek kaynak burasıdır. Dosya adını değiştirmeniz gerekirse:

  1) DEFAULT_INPUT_FILE_NAME sabitini burada güncelleyin, VEYA
  2) Kod değiştirmeden OMEHR_INPUT_FILE ortam değişkenini tanımlayın.

Diğer tüm modüller (main.py, web paneli, rapor motorları, testler) bu
isme services.settings.input_file_name() / input_path() üzerinden erişir.
"""
from __future__ import annotations

import os
from pathlib import Path

# Ana input Excel dosyasının varsayılan adı.
DEFAULT_INPUT_FILE_NAME = "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"


def input_file_name() -> str:
    """Ana input Excel dosyasının adı.

    OMEHR_INPUT_FILE ortam değişkeni tanımlıysa onu kullanır; aksi halde
    DEFAULT_INPUT_FILE_NAME döner. Böylece dosya adı kod değiştirmeden de
    (örn. .env üzerinden) geçersiz kılınabilir.
    """
    value = os.getenv("OMEHR_INPUT_FILE", "").strip()
    return value or DEFAULT_INPUT_FILE_NAME


def input_path(root: Path) -> Path:
    """Ana input Excel yolu.

    Çoklu-PC kullanımında OMEHR_INPUT_PATH tam UNC/ağ yolunu gösterebilir
    (örn. şirket sunucusundaki ortak Excel dosyası — bkz.
    ORTAK_EXCEL_YOLU_AYARLA.bat). Tanımlı değilse mevcut tek-PC davranışı
    aynen korunur.
    """
    full = os.getenv("OMEHR_INPUT_PATH", "").strip()
    if full:
        return Path(full)
    return Path(root) / "input" / input_file_name()

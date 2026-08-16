from __future__ import annotations

"""
GUNLUK_PUANTAJ_HATIRLATMA.py
================================
Her sabah saat 09:00'de zamanlayıcı tarafından tetiklenir. Tüm aktif
mağazalara (Sube_Mail_Listesi, Aktif=Evet + Günlük Gönderim=Evet) puantaj
hatırlatma e-postası gönderir ve sonucu logs/ klasörüne yazar.

Manuel test için: python GUNLUK_PUANTAJ_HATIRLATMA.py
Gerçek gönderim yapmadan denemek için: BASDAS_MAIL_DRY_RUN=1 önceden ayarlanmalı.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from services.puantaj_hatirlatma import gunluk_puantaj_hatirlatma_gonder

    print("Günlük puantaj hatırlatma e-postaları gönderiliyor...", flush=True)
    ozet = gunluk_puantaj_hatirlatma_gonder()

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_dosya = logs_dir / f"puantaj_hatirlatma_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(log_dosya, "w", encoding="utf-8") as f:
        json.dump(ozet, f, ensure_ascii=False, indent=2)

    print(f"Toplam: {ozet['toplam_magaza']} | Başarılı: {ozet['basarili']} | Başarısız: {ozet['basarisiz']}")
    print(f"Log: {log_dosya}")
    return 0 if ozet["basarisiz"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

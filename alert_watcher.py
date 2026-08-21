#!/usr/bin/env python3
"""ALERT WATCHER — arka planda periyodik olarak input verisini okur,
kritik norm açığı eşiğini (Ayarlar ekranındaki critical_deficit_threshold)
aşan mağazalar için services.management_center.scan_alerts() ile uyarı
oluşturur ve varsa Teams webhook'una gönderir.

OMEHR_CURRENT_BASLAT.bat/.sh tarafından arka plan süreci olarak başlatılır.
OMEHR_ALERT_INTERVAL_SECONDS ortam değişkeniyle kontrol periyodu
ayarlanabilir (varsayılan: 900 sn / 15 dk).

Kapsam BİLEREK hafif tutuldu: dosyayı `prepare=False` ile okur (yedekleme/
koordinat yenileme/formül yeniden hesaplama TETİKLEMEZ) — bu adımlar zaten
web paneli ve main.py tarafından uygun zamanlarda yapılıyor; watcher'ın
görevi yalnız GÖZLEMLEMEK, dosyayı değiştirmek değil.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _bir_tur() -> int:
    """Tek bir kontrol turu çalıştırır; oluşturulan yeni uyarı sayısını döner."""
    from src.data_loading import load
    from src.state_engine import state
    from services.management_center import scan_alerts, send_teams

    try:
        _p, sheets, norm, staff, _h = load(prepare=False)
    except Exception as exc:
        from services.safe_exec import log_swallowed
        log_swallowed("alert_watcher._bir_tur: input okunamadı", exc, level="WARNING")
        return 0

    try:
        st, tt = state(norm, staff, sheets)
        yeni = scan_alerts(st, tt)
    except Exception as exc:
        from services.safe_exec import log_swallowed
        log_swallowed("alert_watcher._bir_tur: uyarı taraması başarısız", exc, level="ERROR")
        return 0

    if yeni is not None and not yeni.empty:
        for _, uyari in yeni.iterrows():
            gonderildi, _detay = send_teams(str(uyari.get("message", "")))
            _ = gonderildi  # Teams tanımlı değilse sessizce atlanır (send_teams zaten güvenli)
        return len(yeni)
    return 0


def main() -> int:
    aralik = int(os.getenv("OMEHR_ALERT_INTERVAL_SECONDS", "900"))
    print(f"Alert watcher başladı — her {aralik} saniyede bir kritik norm açığı taranacak.")
    try:
        while True:
            sayi = _bir_tur()
            if sayi:
                print(f"{sayi} yeni kritik uyarı oluşturuldu.")
            time.sleep(aralik)
    except KeyboardInterrupt:
        print("Alert watcher durduruldu.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

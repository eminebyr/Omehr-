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
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_STARTED_LOCK = threading.Lock()
_STARTED = False


def start_background() -> None:
    """Süreç başına yalnızca BİR KEZ, arka planda çalışan bir alert-watcher
    thread'i başlatır.

    DÜZELTME (30 Ağustos 2026 — Teams uyarıları hiç çalışmıyordu): Bu script
    önceden yalnızca `python alert_watcher.py` olarak, AYRI bir süreç/servis
    içinden çalıştırılmak üzere tasarlanmıştı (bkz. OMEHR_CURRENT_BASLAT.bat/
    .sh, docker-compose.production.yml). Railway'in kullandığı Dockerfile /
    container_entrypoint.py bu ayrı süreci HİÇ başlatmıyordu — yani Teams
    webhook'u tanımlansa bile hiçbir uyarı gönderilmiyordu (script hiç
    çalışmıyordu).

    Çözüm: services/scheduler.py::start_daily_report_scheduler() ile AYNI
    desen — mevcut Streamlit sürecinin (zaten container açık olduğu sürece
    canlı kalan TEK kalıcı süreç) İÇİNDE bir daemon thread olarak çalışır.
    Ayrı bir Railway servisi/worker gerekmez, ekstra maliyet çıkarmaz.
    web/app.py, bu fonksiyonu @st.cache_resource ile süreç başına bir kez
    çağırır."""
    global _STARTED
    with _STARTED_LOCK:
        if _STARTED:
            return
        thread = threading.Thread(target=_arka_plan_dongusu, name="omehr-alert-watcher", daemon=True)
        thread.start()
        _STARTED = True


def _arka_plan_dongusu() -> None:
    from services.observability import get_logger
    from services.safe_exec import log_swallowed

    try:
        aralik = max(30, int(os.getenv("OMEHR_ALERT_INTERVAL_SECONDS", "900")))
    except ValueError:
        aralik = 900
    logger = get_logger("omehr.alert_watcher")
    logger.info("Alert watcher (arka plan thread) başladı — her %s saniyede bir kritik norm açığı taranacak.", aralik)
    while True:
        try:
            sayi = _bir_tur()
            if sayi:
                logger.info("%s yeni kritik uyarı oluşturuldu (Teams'e gönderildi).", sayi)
        except Exception as exc:
            log_swallowed("alert_watcher._arka_plan_dongusu: beklenmeyen hata — devam ediliyor", exc, level="ERROR")
        time.sleep(aralik)


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
    try:
        aralik = max(30, int(os.getenv("OMEHR_ALERT_INTERVAL_SECONDS", "900")))
    except ValueError:
        aralik = 900
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

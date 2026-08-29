from __future__ import annotations

"""GÜNLÜK OTOMATİK RAPOR ZAMANLAYICI.

DÜZELTME (yeni özellik): Bu uygulamanın mimarisinde SÜREKLİ ÇALIŞAN ayrı bir
worker.py süreci YOK — işler yalnızca bir web isteği geldiğinde ancak olarak
`worker.py --once` alt-süreciyle işleniyor (bkz. web/app.py::
_enqueue_and_process, refresh_all). Bu, "kimse panele girmese bile günde 2
kez otomatik rapor üret" isteğini karşılamaz, çünkü tetikleyecek bir istek
hiç gelmeyebilir.

Çözüm: Streamlit sürecinin kendisi zaten container açık olduğu sürece canlı
kalıyor (bkz. container_entrypoint.py — Streamlit `os.execvp` ile başlatılan
TEK ve KALICI süreç). Bu modül, o sürecin İÇİNDE arka planda dönen, günde 2 kez
(varsayılan 10:00 ve 17:15) `RUN_REPORTS` görevini otomatik tetikleyen bir
daemon thread başlatır. web/app.py bunu `st.cache_resource` ile SADECE BİR
KEZ (süreç başına, tüm kullanıcı oturumları arasında paylaşılan) başlatır —
Streamlit'in her sayfa yenilemesinde yeniden thread açmaz.

Saatler `OMEHR_REPORT_SCHEDULE_TIMES` ortam değişkeniyle özelleştirilebilir
(virgülle ayrılmış "SS:DD" listesi, örn. "10:00,17:15"); tanımsızsa bu iki
saat varsayılan olarak kullanılır.

EKLENTİ: Her tetiklemeden önce, archive/backups/backup klasörlerindeki eski
rapor ve yedek dosyaları otomatik temizlenir (en yeni N tanesi saklanır),
böylece Railway Volume'u zamanla dolup taşmaz. output_last_complete/
klasörüne dokunulmaz — o, son sağlam durumun güvenlik yedeğidir.
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

from services.job_queue import enqueue_scheduled_once
from services.observability import get_logger
from services.runtime_paths import code_root, runtime_root
from services.safe_exec import log_swallowed
from services.tenant_context import current_tenant_id

LOGGER = get_logger("omehr.scheduler")

_DEFAULT_TIMES = ["10:00", "17:15"]
_STARTED_LOCK = threading.Lock()
_STARTED = False

# Temizlik varsayılanları — env değişkeniyle override edilebilir
_CLEANUP_DEFAULTS = {
    "OMEHR_ARCHIVE_KEEP_PDF": 10,
    "OMEHR_ARCHIVE_KEEP_XLSX": 15,
    "OMEHR_BACKUPS_KEEP": 10,
    "OMEHR_BACKUP_KEEP": 5,
}


def _parse_times(raw: str | None) -> list[tuple[int, int]]:
    values = [v.strip() for v in (raw or "").split(",") if v.strip()] or _DEFAULT_TIMES
    parsed: list[tuple[int, int]] = []
    for value in values:
        try:
            hh, mm = value.split(":")
            parsed.append((int(hh), int(mm)))
        except Exception:
            log_swallowed(f"scheduler: geçersiz saat biçimi atlandı: {value!r}", ValueError(value), level="WARNING")
    return parsed or [(int(h), int(m)) for h, m in (tuple(t.split(":")) for t in _DEFAULT_TIMES)]


def _next_run(now: datetime, times: list[tuple[int, int]]) -> datetime:
    candidates = []
    for hh, mm in times:
        candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def _keep_newest(folder, pattern: str, keep: int) -> int:
    """folder içinde pattern'e uyan dosyalardan en yeni `keep` tanesini
    saklar, gerisini siler. Silinen dosya sayısını döner. Klasör yoksa
    veya erişilemezse sessizce 0 döner (hata fırlatmaz)."""
    if not folder.exists():
        return 0
    try:
        files = sorted(
            (f for f in folder.glob(pattern) if f.is_file()),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
    except Exception as exc:
        log_swallowed(f"scheduler: temizlik için {folder} okunamadı", exc, level="WARNING")
        return 0

    removed = 0
    for old_file in files[keep:]:
        try:
            old_file.unlink()
            removed += 1
        except Exception as exc:
            log_swallowed(f"scheduler: {old_file} silinemedi", exc, level="WARNING")
    return removed


def _cleanup_old_reports() -> None:
    """archive/backups/backup klasörlerindeki eski dosyaları temizler.
    output_last_complete/ klasörüne KESİNLİKLE dokunulmaz."""
    try:
        keep_pdf = int(os.getenv("OMEHR_ARCHIVE_KEEP_PDF", _CLEANUP_DEFAULTS["OMEHR_ARCHIVE_KEEP_PDF"]))
        keep_xlsx = int(os.getenv("OMEHR_ARCHIVE_KEEP_XLSX", _CLEANUP_DEFAULTS["OMEHR_ARCHIVE_KEEP_XLSX"]))
        keep_backups = int(os.getenv("OMEHR_BACKUPS_KEEP", _CLEANUP_DEFAULTS["OMEHR_BACKUPS_KEEP"]))
        keep_backup = int(os.getenv("OMEHR_BACKUP_KEEP", _CLEANUP_DEFAULTS["OMEHR_BACKUP_KEEP"]))

        data_root = runtime_root()
        total_removed = 0
        total_removed += _keep_newest(data_root / "archive", "*.pdf", keep_pdf)
        total_removed += _keep_newest(data_root / "archive", "*.xlsx", keep_xlsx)
        total_removed += _keep_newest(data_root / "backups", "*.xlsx", keep_backups)
        total_removed += _keep_newest(data_root / "backup", "*.xlsx", keep_backup)

        if total_removed:
            LOGGER.info("Otomatik temizlik: %s eski dosya silindi (archive/backups/backup)", total_removed)
    except Exception as exc:
        log_swallowed("scheduler: otomatik temizlik sırasında beklenmeyen hata", exc, level="ERROR")


def _active_tenants() -> list[str]:
    try:
        from services.tenant_registry import list_tenants
        active = [str(t["tenant_id"]).strip().upper() for t in list_tenants() if t.get("durum") == "aktif"]
        if active:
            return sorted(set(active))
    except Exception as exc:
        log_swallowed("scheduler: aktif kiracı listesi okunamadı", exc, level="WARNING")
    return [current_tenant_id()]


def _trigger_report_run(scheduled_for: datetime | None = None) -> None:
    _cleanup_old_reports()
    try:
        slot = (scheduled_for or datetime.now()).strftime("%Y-%m-%dT%H:%M")
        enqueued = []
        for tenant in _active_tenants():
            job_id = enqueue_scheduled_once("RUN_REPORTS", {}, tenant, slot)
            if job_id is not None:
                enqueued.append((tenant, job_id))
        if enqueued:
            py = code_root() / ".venv" / "Scripts" / "python.exe"
            executable = str(py) if py.exists() else sys.executable
            subprocess.Popen([executable, str(code_root() / "worker.py"), "--drain"], cwd=code_root())
        LOGGER.info("Zamanlanmış rapor üretimi tetiklendi: %s", enqueued)
    except Exception as exc:
        log_swallowed("scheduler: zamanlanmış rapor üretimi tetiklenemedi", exc, level="ERROR")


def _loop(times: list[tuple[int, int]]) -> None:
    LOGGER.info("Günlük rapor zamanlayıcı başlatıldı — saatler: %s", times)
    while True:
        try:
            now = datetime.now()
            target = _next_run(now, times)
            wait_seconds = max(1.0, (target - now).total_seconds())
            # Uzun uykular tek seferde değil, en fazla 5 dakikalık parçalar
            # halinde beklenir — böylece süreç yeniden başlarsa (deploy,
            # container yeniden başlatma) takılı kalmadan hızlı çıkabilir.
            while wait_seconds > 0:
                time.sleep(min(300, wait_seconds))
                wait_seconds -= 300
            _trigger_report_run(target)
            time.sleep(60)  # aynı dakika içinde tekrar tetiklenmeyi önle
        except Exception as exc:
            log_swallowed("scheduler: döngüde beklenmeyen hata — devam ediliyor", exc, level="ERROR")
            time.sleep(60)


def start_daily_report_scheduler() -> None:
    """Süreç başına yalnızca BİR kez arka plan zamanlayıcı thread'i başlatır."""
    global _STARTED
    with _STARTED_LOCK:
        if _STARTED:
            return
        times = _parse_times(os.getenv("OMEHR_REPORT_SCHEDULE_TIMES"))
        thread = threading.Thread(target=_loop, args=(times,), name="omehr-report-scheduler", daemon=True)
        thread.start()
        _STARTED = True

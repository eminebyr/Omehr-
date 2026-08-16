"""RUNTIME RESILIENCE — src/engine_core.py::run_all()'ın etrafına saran
dayanıklılık katmanı: tek-örnek kilidi, ön/son doğrulama, dayanıklı JSON
yazma ve çalışma zamanı meta verisi.

KRİTİK BULGU: Bu dosya, main.py'nin TÜM rapor üretimini (run_all()
üzerinden) çalıştırabilmesi için ZORUNLUYDU ama pakette hiç yoktu —
src/engine_core.py'nin ikinci (aktif) run_all() tanımı bunu import
ediyordu ve her çağrıldığında ModuleNotFoundError ile çöküyordu. Bu,
gerçek kullanıcı testinde (bkz. ekran görüntüsü — eksik .bat dosyaları
sorgusu) fark edilip izlenerek bulundu; bu sandbox'ta main.py hiç uçtan
uca çalıştırılamadığı için önceki turlarda kaçmıştı.

Var olan altyapıyı YENİDEN İCAT ETMEK yerine kullanır:
  - services/file_lock.py -> single_instance_lock
  - services/schema_validation.py -> preflight_validate
  - services/observability.py -> configure_logging
"""
from __future__ import annotations

import json
import os
import platform
from contextlib import contextmanager
from pathlib import Path

from services.version import APP_VERSION

VERSION = APP_VERSION


def configure_logging(root: Path):
    """services/observability.py'deki merkezi logger'ı döner — ayrı bir
    logging altyapısı KURMAZ, var olanı kullanır."""
    from services.observability import get_logger

    return get_logger("basdas.runtime")


def runtime_metadata() -> dict:
    """Audit kaydına eklenecek, çalışma zamanını tanımlayan temel bilgiler."""
    return {
        "app_version": APP_VERSION,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "pid": os.getpid(),
    }


@contextmanager
def single_instance_lock(root: Path):
    """Aynı input dosyası üzerinde İKİ run_all() çağrısının AYNI ANDA
    çalışmasını önler (ör. zamanlanmış görev ile elle çalıştırma
    çakışması) — services/file_lock.py'deki genel kilit mekanizmasını,
    run_all()'a özel bir sentinel dosya üzerinde kullanır."""
    from services.file_lock import file_lock

    lock_path = Path(root) / "data" / ".main_run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(lock_path, timeout=300) as alindi:
        if not alindi:
            raise RuntimeError(
                "Başka bir main.py/run_all() çalıştırması hâlâ sürüyor gibi görünüyor "
                f"(kilit: {lock_path}). Eğer bu yanlışsa ve önceki çalıştırma gerçekten "
                "bitmişse, bu dosyayı elle silip tekrar deneyin."
            )
        yield


def preflight_validate(source: Path) -> dict:
    """run_all() başlamadan ÖNCE input dosyasını okuyup şema sözleşmesini
    (services.schema_validation) doğrular. Zorunlu bir sütun/sayfa
    eksikse SchemaValidationError fırlatır — bu BİLEREK burada
    YAKALANMAZ; run_all() bunu audit'e 'FAILED' olarak yazıp yeniden
    fırlatır (fail-fast, bkz. modül docstring'i)."""
    from common_veri_okuma import read_all
    from services.schema_validation import validate

    sheets = read_all(source)
    sonuc = validate(sheets)
    return {
        "sheet_count": len(sheets),
        "warning_count": len(sonuc.uyarilar),
        "warnings": sonuc.uyarilar[:20],  # audit dosyasını şişirmemek için ilk 20
    }


def postflight_validate(result: dict) -> dict:
    """run_all() TAMAMLANDIKTAN sonra üretilen sonucun temel bütünlüğünü
    kontrol eder — bu bir tekrar hesaplama DEĞİLDİR, yalnız 'sonuç
    nesnesi beklenen şekle sahip mi' türünde hızlı bir sağlık kontrolü."""
    kontroller: dict[str, bool] = {}
    kpis = result.get("kpis") if isinstance(result, dict) else None
    kontroller["kpis_present"] = kpis is not None
    if isinstance(kpis, dict):
        for alan in ("Aktif Mevcut", "Toplam Norm", "Norm Eksiği", "Norm Fazlası", "Net İhtiyaç"):
            kontroller[f"kpi_{alan}_present"] = alan in kpis
        kontroller["kpi_no_negative_headcount"] = kpis.get("Aktif Mevcut", 0) >= 0
    dosyalar = result.get("files") if isinstance(result, dict) else None
    kontroller["files_present"] = bool(dosyalar)
    basarisiz = [k for k, v in kontroller.items() if not v]
    return {"checks": kontroller, "all_passed": not basarisiz, "failed_checks": basarisiz}


def atomic_write_json(path: Path, data: dict) -> None:
    """Yarım yazılmış/bozuk bir audit dosyası bırakmamak için: önce
    geçici bir dosyaya yaz, sonra ATOMIK olarak hedef ada taşı (aynı
    desen services/observability.py::write_runtime_status'ta da
    kullanılıyor)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, path)

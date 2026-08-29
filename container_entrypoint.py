from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from services.security import credential_exists, set_password
from services.runtime_paths import code_root, runtime_root

ROOT = code_root()
RUNTIME = runtime_root()

_REPORT_SUFFIXES = {".pdf", ".xlsx", ".xlsm"}


def _report_count(base: Path | None = None) -> int:
    output = base or (RUNTIME / "output")
    if not output.exists():
        return 0
    return sum(1 for p in output.rglob("*") if p.is_file() and p.suffix.lower() in _REPORT_SUFFIXES)


def _expected_report_count() -> int:
    try:
        return max(1, int(os.getenv("OMEHR_EXPECTED_REPORT_COUNT", "32")))
    except ValueError:
        return 32


def _snapshot_complete_reports() -> None:
    """Son TAM rapor setini ayrı klasörde korur.

    Rapor motoru yeni seti üretirken output/ kısa süreyle kısmi görünebilir.
    Web paneli bu anda 9/32 gibi ara bir sayı göstermesin diye son tamamlanmış
    set output_last_complete/ altında tutulur. Yalnız 32/32 (veya ayarlanan
    hedef) mevcutsa snapshot yenilenir.
    """
    source = RUNTIME / "output"
    expected = _expected_report_count()
    from services.report_contract import validate_current_report_set
    contract = validate_current_report_set(source)
    current = contract["present"]
    if contract["status"] != "SUCCESS" or contract["expected"] < expected:
        return

    target = RUNTIME / "output_last_complete"
    temp = RUNTIME / "output_last_complete_new"
    shutil.rmtree(temp, ignore_errors=True)
    shutil.copytree(source, temp)
    copied_contract = validate_current_report_set(temp)
    if copied_contract["status"] != "SUCCESS" or copied_contract["expected"] < expected:
        shutil.rmtree(temp, ignore_errors=True)
        return
    shutil.rmtree(target, ignore_errors=True)
    temp.replace(target)
    print(f"Tam rapor snapshot'ı hazır: {_report_count(target)}/{expected}.", flush=True)


def _run_report_engine_once() -> int:
    print(f"Başlangıç rapor kontrolü: {_report_count()} hazır rapor bulundu.", flush=True)
    result = subprocess.run([sys.executable, str(ROOT / "main.py")], cwd=ROOT)
    print(f"Başlangıç rapor motoru çıkış kodu: {result.returncode}; hazır rapor: {_report_count()}", flush=True)
    return result.returncode


def _ensure_startup_reports() -> bool:
    """Streamlit açılmadan önce beklenen rapor setinin Volume'da hazır olmasını sağlar.

    Railway Volume kalıcı olduğu için daha önce üretilmiş tam set varsa motoru gereksiz
    yere tekrar çalıştırmaz. Set eksikse main.py çalıştırılır ve kısa bir kontrollü
    retry yapılır. Varsayılan hedef 32 rapordur; OMEHR_EXPECTED_REPORT_COUNT ile
    değiştirilebilir. OMEHR_ENSURE_REPORTS_ON_START=0 ile tamamen kapatılabilir.
    """
    if os.getenv("OMEHR_ENSURE_REPORTS_ON_START", "1").strip().lower() in {"0", "false", "hayir", "no"}:
        return True

    expected = _expected_report_count()
    try:
        retries = max(0, int(os.getenv("OMEHR_STARTUP_REPORT_RETRIES", "2")))
    except ValueError:
        retries = 2

    from services.report_contract import validate_current_report_set
    contract = validate_current_report_set(RUNTIME / "output")
    current = contract["present"]
    if contract["status"] == "SUCCESS" and contract["expected"] >= expected:
        print(f"Başlangıç rapor seti hazır: {current}/{expected}. Motor tekrar çalıştırılmadı.", flush=True)
        return True

    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        print(f"Başlangıç rapor seti eksik: {current}/{expected}. Üretim denemesi {attempt}/{attempts}.", flush=True)
        rc = _run_report_engine_once()
        contract = validate_current_report_set(RUNTIME / "output")
        current = contract["present"]
        if rc == 0 and contract["status"] == "SUCCESS" and contract["expected"] >= expected:
            print(f"Başlangıç rapor seti tamamlandı: {current}/{expected}.", flush=True)
            return True
        if attempt < attempts:
            print(f"Rapor seti henüz tamamlanmadı ({current}/{expected}); 3 saniye sonra tekrar deneniyor.", flush=True)
            time.sleep(3)

    print(
        f"HATA: Başlangıçta beklenen rapor seti oluşturulamadı: {current}/{expected}. "
        "Streamlit eksik raporlarla açılmayacak.",
        flush=True,
    )
    return False


def main() -> int:
    admin_password = os.getenv("OMEHR_ADMIN_PASSWORD", "")
    if not credential_exists("admin"):
        if not admin_password:
            print("HATA: İlk container açılışında OMEHR_ADMIN_PASSWORD tanımlanmalıdır.", flush=True)
            return 2
        set_password("admin", admin_password, must_change=True)
        print("Admin geçici parolası güvenli kasada oluşturuldu; ilk girişte değiştirilmelidir.", flush=True)

    if os.getenv("OMEHR_RUN_ENGINE_ON_START", "0") == "1":
        if _run_report_engine_once() != 0:
            return 1

    if not _ensure_startup_reports():
        return 1

    # Streamlit açılmadan hemen önce 32/32 setin güvenli görüntüleme kopyasını al.
    _snapshot_complete_reports()

    os.execvp(
        sys.executable,
        [
            sys.executable, "-m", "streamlit", "run", str(ROOT / "web" / "app.py"),
            "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

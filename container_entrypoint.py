from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from services.security import credential_exists, set_password
from services.runtime_paths import code_root, runtime_root

ROOT = code_root()
RUNTIME = runtime_root()

_REPORT_SUFFIXES = {".pdf", ".xlsx", ".xlsm"}


def _report_count() -> int:
    output = RUNTIME / "output"
    if not output.exists():
        return 0
    return sum(1 for p in output.rglob("*") if p.is_file() and p.suffix.lower() in _REPORT_SUFFIXES)


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

    try:
        expected = max(1, int(os.getenv("OMEHR_EXPECTED_REPORT_COUNT", "32")))
    except ValueError:
        expected = 32
    try:
        retries = max(0, int(os.getenv("OMEHR_STARTUP_REPORT_RETRIES", "2")))
    except ValueError:
        retries = 2

    current = _report_count()
    if current >= expected:
        print(f"Başlangıç rapor seti hazır: {current}/{expected}. Motor tekrar çalıştırılmadı.", flush=True)
        return True

    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        print(f"Başlangıç rapor seti eksik: {current}/{expected}. Üretim denemesi {attempt}/{attempts}.", flush=True)
        rc = _run_report_engine_once()
        current = _report_count()
        if rc == 0 and current >= expected:
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

    # Eski davranış korunur: açıkça istenirse motor her açılışta bir kez çalışır.
    # Ancak asıl güvence aşağıdaki rapor-seti doğrulamasıdır; Volume'da 32 rapor
    # yoksa OMEHR_RUN_ENGINE_ON_START=0 olsa bile eksik set tamamlanır.
    if os.getenv("OMEHR_RUN_ENGINE_ON_START", "0") == "1":
        if _run_report_engine_once() != 0:
            return 1

    if not _ensure_startup_reports():
        return 1

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

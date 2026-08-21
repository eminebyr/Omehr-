from __future__ import annotations

import os
import subprocess
import sys

from services.security import credential_exists, set_password
from services.runtime_paths import code_root, runtime_root

ROOT = code_root()
RUNTIME = runtime_root()


def main() -> int:
    admin_password = os.getenv("OMEHR_ADMIN_PASSWORD", "")
    if not credential_exists("admin"):
        if not admin_password:
            print("HATA: İlk container açılışında OMEHR_ADMIN_PASSWORD tanımlanmalıdır.", flush=True)
            return 2
        set_password("admin", admin_password, must_change=True)
        print("Admin geçici parolası güvenli kasada oluşturuldu; ilk girişte değiştirilmelidir.", flush=True)
    if os.getenv("OMEHR_RUN_ENGINE_ON_START", "1") == "1":
        result = subprocess.run([sys.executable, str(ROOT / "main.py")], cwd=ROOT)
        if result.returncode:
            return result.returncode
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

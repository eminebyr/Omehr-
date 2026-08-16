from __future__ import annotations

import os
import subprocess
import sys

from services.security import credential_exists, set_password
from services.runtime_paths import code_root, runtime_root


def main() -> int:
    runtime_root()
    password = os.getenv("BASDAS_ADMIN_PASSWORD", "")
    if not credential_exists("admin"):
        if not password:
            print("HATA: BASDAS_ADMIN_PASSWORD zorunludur.")
            return 2
        set_password("admin", password, must_change=True)
    return subprocess.run([sys.executable, str(code_root() / "main.py")], cwd=code_root()).returncode


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import subprocess
import sys

from services.security import credential_exists, set_password
from services.runtime_paths import code_root, runtime_root

ROOT = code_root()
RUNTIME = runtime_root()


def main() -> int:
    admin_password = os.getenv("BASDAS_ADMIN_PASSWORD", "")
    if not credential_exists("admin"):
        if not admin_password:
            print("HATA: İlk container açılışında BASDAS_ADMIN_PASSWORD tanımlanmalıdır.", flush=True)
            return 2
        set_password("admin", admin_password, must_change=True)
        print("Admin geçici parolası güvenli kasada oluşturuldu; ilk girişte değiştirilmelidir.", flush=True)
    if os.getenv("BASDAS_RUN_ENGINE_ON_START", "1") == "1":
        result = subprocess.run([sys.executable, str(ROOT / "main.py")], cwd=ROOT)
        if result.returncode:
            return result.returncode

    # BULUT MOTORU KÖPRÜSÜ (2026-08-16 eklendi): Streamlit dışarıdan gelen
    # ham HTTP POST isteklerini alamadığı için (yalnız kendi sayfa render
    # protokolünü sunar), Vercel'deki hafif arayüzün "Canlı motoru çalıştır"
    # butonunun ulaşabileceği AYRI, küçük bir Flask süreci (webhook_server.py)
    # arka planda başlatılır. Bu, Streamlit'i (aşağıdaki execvp) HİÇ
    # ETKİLEMEZ — tamamen bağımsız bir alt süreçtir, ayrı bir portta
    # (BASDAS_WEBHOOK_PORT, varsayılan 8502) dinler. Yalnız
    # BASDAS_ENGINE_API_SECRET tanımlıysa başlatılır — tanımlı değilse
    # (örn. bu özelliği kullanmayan kurulumlarda) gereksiz bir süreç açıp
    # kaynak tüketmez.
    if os.getenv("BASDAS_ENGINE_API_SECRET", "").strip():
        subprocess.Popen(
            [sys.executable, str(ROOT / "webhook_server.py")],
            cwd=ROOT,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        print("Bulut motoru köprüsü (webhook_server.py) arka planda başlatıldı.", flush=True)

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

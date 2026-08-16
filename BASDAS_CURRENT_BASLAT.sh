#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export BASDAS_SEND_EMAIL=1

fail() {
  echo "HATA: Sistem başlatılamadı. Ekrandaki son HATA satırını paylaşın." >&2
  exit 1
}
trap fail ERR

if [[ -x ".venv/bin/python" ]]; then
  PY="$PWD/.venv/bin/python"
else
  BASEPY=""
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      BASEPY="$(command -v "$candidate")"
      break
    fi
  done
  [[ -n "$BASEPY" ]] || { echo "HATA: Python 3.11 veya 3.12 bulunamadı."; exit 1; }
  echo "[1/6] Güvenli sanal ortam hazırlanıyor..."
  "$BASEPY" -m venv .venv
  PY="$PWD/.venv/bin/python"
fi

echo "[2/6] Kütüphaneler kontrol ediliyor..."
"$PY" -m pip install -r requirements.txt

echo "[3/6] Inputtaki geçici kullanıcı şifreleri hazırlanıyor..."
"$PY" INITIAL_PASSWORD_IMPORT.py

echo "[4/6] Sistem ve raporlar kontrol ediliyor..."
"$PY" system_health_check.py
"$PY" main.py

mkdir -p logs
if "$PY" -c "import socket; s=socket.socket(); s.settimeout(.5); r=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if r==0 else 1)"; then
  echo "[5/6] Web paneli zaten çalışıyor."
else
  echo "[5/6] Web paneli ve servisler açılıyor..."
  nohup "$PY" worker.py >logs/CURRENT_Worker_Console.log 2>&1 &
  echo $! >logs/CURRENT_Worker.pid
  nohup "$PY" -m uvicorn monitoring_server:app --host 127.0.0.1 --port 9108 >logs/CURRENT_Monitoring_Console.log 2>&1 &
  echo $! >logs/CURRENT_Monitoring.pid
  nohup "$PY" alert_watcher.py >logs/CURRENT_Alerts_Console.log 2>&1 &
  echo $! >logs/CURRENT_Alerts.pid
  nohup "$PY" -m streamlit run web/app.py --server.port 8501 --server.headless true >logs/CURRENT_Web_Console.log 2>&1 &
  echo $! >logs/CURRENT_Web.pid
fi

echo "[6/6] Web bekleniyor..."
for _ in $(seq 1 60); do
  if "$PY" -c "import socket; s=socket.socket(); s.settimeout(.5); r=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if r==0 else 1)"; then
    URL="http://localhost:8501"
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
      open "$URL" >/dev/null 2>&1 || true
    fi
    echo "BAŞARILI: $URL"
    trap - ERR
    exit 0
  fi
  sleep 1
done
exit 1

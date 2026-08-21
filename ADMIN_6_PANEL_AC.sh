#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"

URL="http://localhost:8501"
PY="${PWD}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3 || true)"
[[ -n "$PY" ]] || { echo "HATA: Python 3 bulunamadı."; exit 1; }

"$PY" -c "import socket; s=socket.socket(); s.settimeout(.5); r=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if r==0 else 1)" || {
  echo "HATA: Web sistemi çalışmıyor."
  echo "Önce OMEHR_CURRENT_BASLAT.sh dosyasını çalıştırın."
  exit 1
}

if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ -d "/Applications/Google Chrome.app" ]]; then
    for _ in $(seq 1 6); do open -na "Google Chrome" --args --new-window "$URL"; done
  else
    for _ in $(seq 1 6); do open "$URL"; done
  fi
else
  BROWSER=""
  for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
    if command -v "$candidate" >/dev/null 2>&1; then BROWSER="$candidate"; break; fi
  done
  if [[ -n "$BROWSER" ]]; then
    for _ in $(seq 1 6); do "$BROWSER" --new-window "$URL" >/dev/null 2>&1 & done
  elif command -v xdg-open >/dev/null 2>&1; then
    for _ in $(seq 1 6); do xdg-open "$URL" >/dev/null 2>&1 & done
  else
    echo "Tarayıcı otomatik açılamadı. Altı pencerede şu adresi açın: $URL"
    exit 1
  fi
fi
echo "BAŞARILI: 6 admin paneli açıldı."

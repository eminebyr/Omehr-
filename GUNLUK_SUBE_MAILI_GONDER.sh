#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"
PY="$PWD/.venv/bin/python"
TEMPLATE="GUNLUK_SUBE_MAIL_METNI.txt"
PREVIEW="logs/CURRENT_Gunluk_Sube_Mail_Onizleme.txt"

[[ -x "$PY" ]] || {
  echo "HATA: Önce OMEHR_CURRENT_BASLAT.sh dosyasını bir kez çalıştırın."
  exit 1
}
[[ -f "$TEMPLATE" ]] || {
  echo "HATA: $TEMPLATE bulunamadı."
  exit 1
}

echo "[1/3] Günlük mail metni açılıyor."
echo "Metni düzenleyin, kaydedin ve düzenleyiciyi kapatın."
if [[ -n "${EDITOR:-}" ]]; then
  "$EDITOR" "$TEMPLATE"
elif command -v nano >/dev/null 2>&1; then
  nano "$TEMPLATE"
elif command -v vi >/dev/null 2>&1; then
  vi "$TEMPLATE"
elif command -v open >/dev/null 2>&1; then
  open -W "$TEMPLATE"
else
  echo "Metni başka bir düzenleyicide açın: $PWD/$TEMPLATE"
  read -r -p "Düzenlemeyi tamamladığınızda Enter'a basın..."
fi

echo "[2/3] Alıcılar ve mesajlar kontrol ediliyor..."
"$PY" daily_branch_mail.py --dry-run
echo
echo "Önizleme: $PREVIEW"
if command -v less >/dev/null 2>&1; then
  less "$PREVIEW"
else
  cat "$PREVIEW"
fi

echo
read -r -p "Listedeki şubelere bu e-postayı göndermek için EVET yazın: " ONAY
ONAY_NORMALIZED="$(printf '%s' "$ONAY" | tr '[:lower:]' '[:upper:]')"
if [[ "$ONAY_NORMALIZED" != "EVET" ]]; then
  echo "İPTAL: Hiçbir e-posta gönderilmedi."
  exit 0
fi

echo "[3/3] E-postalar gönderiliyor..."
"$PY" daily_branch_mail.py
echo "BAŞARILI: Günlük şube e-postaları gönderildi."
echo "Kayıt: logs/CURRENT_Gunluk_Sube_Mail_Log.json"

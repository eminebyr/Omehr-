#!/usr/bin/env bash
# Başlangıç test iskeletini çalıştırır (tests/README.md'deki kapsamla sınırlı).
# Bu, eski "YESIL_PAKET_TESTI.bat"ın tam yerine geçmez (bkz. tests/README.md
# "Kapsam DIŞI" bölümü) — yalnız bu turda eklenen testleri çalıştırır.
set -euo pipefail
cd "$(dirname "$0")"

echo "OMEHR — başlangıç test iskeleti çalıştırılıyor..."
python3 -m pytest tests/ "$@"
sonuc=$?

if [ $sonuc -eq 0 ]; then
    echo ""
    echo "SONUÇ: YEŞİL — tüm testler geçti."
else
    echo ""
    echo "SONUÇ: KIRMIZI — en az bir test başarısız oldu, yukarıyı kontrol edin."
fi
exit $sonuc

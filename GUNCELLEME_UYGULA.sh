#!/usr/bin/env bash
# GUNCELLEME_UYGULA.sh - indirilen bir güncelleme paketini uygular.
# Kullanım: ./GUNCELLEME_UYGULA.sh <paket_klasoru> <yeni_surum>
set -euo pipefail
cd "$(dirname "$0")"
if [ $# -ne 2 ]; then
    echo "Kullanım: ./GUNCELLEME_UYGULA.sh <paket_klasoru> <yeni_surum>"
    echo "Örnek:    ./GUNCELLEME_UYGULA.sh ./guncelleme_paketi 19.21.3"
    exit 2
fi
python3 GUNCELLEME_UYGULA.py "$1" "$2"

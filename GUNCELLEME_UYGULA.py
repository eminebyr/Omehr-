#!/usr/bin/env python3
"""GUNCELLEME_UYGULA — komut satırından güncelleme uygulama betiği.

Kullanım:
    python GUNCELLEME_UYGULA.py <guncelleme_paketi_klasoru> <yeni_surum>

Örnek:
    python GUNCELLEME_UYGULA.py C:\\indirilenler\\basdas_v19_21_3_paket 19.21.3

Bu betik services/updater.py'yi çağırır (bkz. o modülün docstring'i için
kapsam ve sınırlar). BASDAS_CURRENT_BASLAT.bat/.sh ile AYNI desende,
KURULUM.bat'ın yanına GUNCELLEME_UYGULA.bat/.sh eklenerek çağrılabilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    if len(sys.argv) != 3:
        print("Kullanım: python GUNCELLEME_UYGULA.py <paket_klasoru> <yeni_surum>")
        print("Örnek:    python GUNCELLEME_UYGULA.py ./guncelleme_paketi 19.21.3")
        return 2

    paket_yolu = Path(sys.argv[1])
    yeni_surum = sys.argv[2]

    from services.runtime_paths import runtime_root
    from services.updater import apply_update, current_version, compare_versions

    root = runtime_root()
    su_anki = current_version()

    print(f"Mevcut sürüm : {su_anki}")
    print(f"Yeni sürüm   : {yeni_surum}")
    print(f"Paket klasörü: {paket_yolu}")

    try:
        if compare_versions(yeni_surum, su_anki) <= 0:
            print(f"\nUYARI: {yeni_surum}, mevcut sürüm {su_anki}'den daha eski veya aynı.")
            onay = input("Yine de devam etmek istiyor musunuz? (evet/hayır): ").strip().lower()
            if onay != "evet":
                print("İptal edildi.")
                return 1
    except Exception as exc:
        print(f"Sürüm karşılaştırması yapılamadı: {exc}")
        return 2

    print("\nGüncelleme öncesi otomatik yedek alınıyor ve dosyalar kopyalanıyor...")
    sonuc = apply_update(paket_yolu, root, new_version=yeni_surum)

    if sonuc.basarili:
        print(f"\n✅ Güncelleme BAŞARILI: {sonuc.onceki_surum} -> {sonuc.yeni_surum}")
        print(f"Yedek konumu: {sonuc.yedek_yolu}")
        print(f"Güncellenen ögeler: {', '.join(sonuc.kopyalanan_ogeler)}")
        print("\nDevam etmeden önce BASDAS_CURRENT_BASLAT.bat/.sh ile sistemi yeniden başlatın ve YESIL_PAKET_TESTI/TESTLERI_CALISTIR ile doğrulayın.")
        return 0
    else:
        print(f"\n❌ Güncelleme BAŞARISIZ: {sonuc.hata}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

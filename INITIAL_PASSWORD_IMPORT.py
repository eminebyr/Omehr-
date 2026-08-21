#!/usr/bin/env python3
"""INITIAL_PASSWORD_IMPORT — input Excel'deki (Mail_Listesi sayfası) geçici
ilk giriş şifrelerini, güvenli parola kasasına (data/security.db,
PBKDF2-HMAC-SHA256) bir kez taşır.

OMEHR_CURRENT_BASLAT.bat/.sh tarafından her başlatmada çağrılır — ama
services.security.migrate_legacy_input() zaten bir "marker" dosyasıyla
(data/.legacy_passwords_migrated) yalnız BİR KEZ gerçek taşıma yapar;
sonraki çalıştırmalarda hızlıca no-op döner. Bu yüzden her başlatmada
çağrılması güvenlidir ve gereklidir (yeni kullanıcı satırları için).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    from services.runtime_paths import runtime_root
    from services.security import migrate_legacy_input
    from services.settings import input_path

    root = runtime_root()
    path = input_path(root)

    if not path.is_file():
        print(f"UYARI: Input dosyası bulunamadı ({path}) — şifre taşıma atlandı.")
        return 0

    try:
        adet = migrate_legacy_input(path)
    except Exception as exc:
        # DÜZELTME: önceden bu istisna return 1 (KRİTİK HATA) döndürüyordu
        # ve OMEHR_CURRENT_BASLAT.bat bunu görünce TÜM kurulum/başlatma
        # sürecini "HATA: Kullanici guvenlik aktarimi basarisiz oldu"
        # mesajıyla DURDURUYORDU. Şifre taşıma yalnız bir KOLAYLIKTIR
        # (Mail_Listesi'ndeki geçici şifreleri önceden yükler) — sistemin
        # ÇALIŞMASI için ZORUNLU değildir; admin her zaman .env'deki
        # varsayılan şifreyle giriş yapabilir. Artık yalnız UYARI verilir,
        # kurulum/başlatma DURMADAN devam eder.
        print(f"UYARI: Şifre taşıma sırasında sorun oluştu (kurulum devam ediyor): {type(exc).__name__}: {exc}")
        return 0

    if adet:
        print(f"OK: {adet} kullanıcının geçici şifresi güvenli kasaya taşındı.")
    else:
        print("OK: Taşınacak yeni geçici şifre yok (zaten taşınmış veya Mail_Listesi'nde uygun sütun yok).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

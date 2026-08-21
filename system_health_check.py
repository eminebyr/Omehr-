#!/usr/bin/env python3
"""SYSTEM HEALTH CHECK — sistemi başlatmadan önce kritik ön koşulları
kontrol eder: Python sürümü, gerekli klasörler, input dosyası,
config dosyalarının okunabilirliği, kritik kütüphanelerin kurulu olması.

OMEHR_CURRENT_BASLAT.bat/.sh tarafından her başlatmada çağrılır.
Kritik bir sorun varsa (input dosyası yok, config bozuk, kütüphane
eksik) sıfırdan farklı bir çıkış koduyla döner ve başlatmayı durdurur —
üretimde yarım/bozuk bir sistemin sessizce açılmasındansa, açık bir
hata mesajıyla durmak tercih edilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_PYTHON = (3, 11)


def _check(label: str, ok: bool, detail: str = "") -> bool:
    sembol = "✅" if ok else "❌"
    print(f"{sembol} {label}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    kritik_hata = False

    # 1) Python sürümü
    surum_ok = sys.version_info[:2] >= MIN_PYTHON
    kritik_hata |= not _check(
        f"Python sürümü ({sys.version_info.major}.{sys.version_info.minor})",
        surum_ok,
        f"en az {MIN_PYTHON[0]}.{MIN_PYTHON[1]} gerekir" if not surum_ok else "",
    )

    # 2) Kritik kütüphaneler
    for paket in ("pandas", "openpyxl", "numpy"):
        try:
            __import__(paket)
            _check(f"Kütüphane: {paket}", True)
        except ImportError:
            _check(f"Kütüphane: {paket}", False, "kurulu değil — pip install -r requirements.txt")
            kritik_hata = True

    # 3) Çalışma zamanı klasörleri (runtime_root() zaten oluşturur, burada yalnız doğrularız)
    try:
        from services.runtime_paths import runtime_root
        root = runtime_root()
        for klasor in ("input", "output", "data", "logs"):
            var = (root / klasor).is_dir()
            _check(f"Klasör: {klasor}/", var)
    except Exception as exc:
        _check("Çalışma zamanı klasörleri", False, f"{type(exc).__name__}: {exc}")
        kritik_hata = True
        root = None

    # 4) Input dosyası
    # DÜZELTME: OMEHR_INPUT_SOURCE=db modunda (ör. kalıcı dosya sistemi
    # olmayan ücretsiz bulut dağıtımları, ya da Ayarlar > "Excel Verisi
    # Yükle" ekranından veri girecek yeni bir kiracı) input dosyasının
    # henüz VAR OLMAMASI beklenen, normal bir durumdur — bu KRİTİK bir
    # hata SAYILMAMALI. Bizzat kanıtlandı: kurulum, veri henüz web
    # panelinden yüklenmeden ÖNCE "KRİTİK sorun var" diyip duruyordu.
    import os
    _db_modu = os.getenv("OMEHR_INPUT_SOURCE", "excel").strip().lower() == "db"
    if root is not None:
        try:
            from services.settings import input_path
            ipath = input_path(root)
            var = ipath.is_file()
            if not var and _db_modu:
                _check(f"Input dosyası ({ipath.name})", True, "veritabanı modu — Ayarlar > 'Excel Verisi Yükle' ekranından yükleyin")
            else:
                _check(f"Input dosyası ({ipath.name})", var, "" if var else f"bekleniyor: {ipath}")
                if not var:
                    kritik_hata = True
            if var:
                # Dosya VAR ama GERÇEKTEN AÇILABİLİYOR MU? Bir OneDrive/bulut
                # yer tutucusu veya yarım kopyalanmış dosya, .is_file() testini
                # geçer ama açılamaz — bu yüzden ayrıca gerçekten okumayı deniyoruz.
                import zipfile
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(ipath, read_only=True)
                    wb.close()
                    _check("Input dosyası açılabilir/okunabilir", True)
                except (zipfile.BadZipFile, EOFError) as exc:
                    _check(
                        "Input dosyası açılabilir/okunabilir", False,
                        "dosya bozuk/eksik görünüyor (OneDrive 'yalnız çevrimiçi' "
                        "yer tutucusu olabilir — sağ tık > 'Bu cihazda her zaman "
                        f"tut'; veya kopyalama yarım kalmış olabilir): {type(exc).__name__}",
                    )
                    kritik_hata = True
        except Exception as exc:
            _check("Input dosyası kontrolü", False, f"{type(exc).__name__}: {exc}")
            kritik_hata = True

    # 5) config_features.json / config_web.json okunabilirliği (bozuksa KRİTİK değil —
    #    src/feature_flags.py zaten güvenli varsayılanlara düşer, bkz. Bölüm 16)
    try:
        from src.feature_flags import all_features
        all_features()
        _check("config_features.json okunabilir/güvenli varsayılan", True)
    except Exception as exc:
        _check("config_features.json kontrolü", False, f"{type(exc).__name__}: {exc}")

    print()
    if kritik_hata:
        print("SONUÇ: KRİTİK sorun(lar) var — sistemin başlatılması önerilmez.")
        return 1
    print("SONUÇ: Sağlık kontrolü geçti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

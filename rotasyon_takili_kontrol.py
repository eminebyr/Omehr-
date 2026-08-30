"""
ROTASYON TAKILI KAYIT KONTROL / DÜZELTME SCRIPTİ
==================================================

NE İŞE YARAR?
-------------
"İK Onayladı" durumuna geçmiş ama Fact_Mevcut'a (personel/mağaza tablosuna)
hiç yansımamış transfer taleplerini bulur ve isterseniz elle tetikleyerek
uygular. Bu, panelde her yeni İK onayında otomatik çalışan
`reconcile_transfer_requests` fonksiyonunun AYNISINI, panel dışından,
komut satırından tetiklemenizi sağlar. web/app.py (Streamlit arayüzü) HİÇ
import edilmez — yalnızca aynı fonksiyonların dayandığı alt seviye
servisler (common_veri_okuma, services.dashboard_model,
services.management_center) kullanılır.

NASIL ÇALIŞTIRILIR? (CANLI SUNUCUDA / RAILWAY'DE)
--------------------------------------------------
Bu dosyayı proje kök dizinine (main.py, worker.py ile aynı klasöre) koyun,
sonra:

    python rotasyon_takili_kontrol.py            # sadece LİSTELER, hiçbir şey değiştirmez
    python rotasyon_takili_kontrol.py --uygula    # bulunanları GERÇEKTEN uygular (Fact_Mevcut günceller)

Railway'de: ilgili servise girip "Shell" özelliğinden aynı komutu
çalıştırabilir, ya da yerel CLI ile `railway run python rotasyon_takili_kontrol.py`
diyebilirsiniz.

ÖNEMLİ
------
- Bu script MEVCUT KOD (services/management_center.py) içindeki
  reconcile_transfer_requests fonksiyonunu ÇAĞIRIR — yeni bir mantık
  eklemez. Sunucunuzdaki kod hâlâ eski/buglı sürümdeyse (27 Ağustos
  düzeltmesinden önceki), bu script de aynı şekilde hiçbir şey
  bulamaz/uygulayamaz. Önce kodun güncel olduğundan emin olun
  (services/version.py -> APP_VERSION en az "19.21.29" olmalı).
- --uygula bayrağı olmadan çalıştırıldığında SADECE OKUR, veritabanında
  hiçbir değişiklik yapmaz.
- Fact_Mevcut'ta OTOMATİK uygulama, ilgili personelin adı staff
  tablosunda TAM OLARAK 1 KEZ geçiyorsa yapılır. Aynı isimde birden
  fazla kişi varsa (veya hiç yoksa) otomatik uygulama BİLEREK atlanır
  ve "mismatch"/"failed" sayaçlarına yansır — bu durumlar elle kontrol
  edilmelidir.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))


def _load_fm():
    """web/app.py'yi (Streamlit'i) import etmeden aynı fm/detail/stores/kpis
    modelini üretir: common_veri_okuma.read_all -> build_dashboard_model."""
    from services.runtime_paths import runtime_root
    from services.settings import input_path
    from services.dashboard_model import build_dashboard_model, CONTROL_FILENAME
    from common_veri_okuma import read_all

    root = runtime_root()
    sheets = read_all(input_path(root))
    fm, detail, stores, kpis = build_dashboard_model(sheets, root / "reference" / CONTROL_FILENAME)
    return fm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--uygula", action="store_true",
        help="Bulunan takılı kayıtları gerçekten uygula (Fact_Mevcut'u günceller).",
    )
    args = parser.parse_args()

    from services.management_center import _input_path
    from services.web_runtime import connect_web_db, db_path

    current_db_path = db_path()
    print(f"Veritabanı: {current_db_path}")
    print(f"Girdi (Fact_Mevcut) dosyası: {_input_path()}")
    print()

    # Temiz/ilk kurulumda transfers tablosu henüz oluşmamış olabilir.
    # Panelin kullandığı ortak başlangıç yolu tabloyu ve migrations'ı güvenle
    # hazırlar; mevcut kayıtları değiştirmez.
    con = connect_web_db()
    con.row_factory = sqlite3.Row
    stuck = con.execute(
        "SELECT id, created_at, person_name, source_store, target_store, "
        "target_title, status, fact_status, updated_at "
        "FROM transfers WHERE status='İK Onayladı' "
        "AND (fact_status='Fact_Mevcut Güncellemesi Bekleniyor' OR fact_status IS NULL) "
        "ORDER BY id"
    ).fetchall()
    con.close()

    if not stuck:
        print("Takılı kayıt bulunamadı — tüm İK onaylı transferler Fact_Mevcut ile senkron görünüyor.")
        return

    print(f"{len(stuck)} adet TAKILI kayıt bulundu (İK Onayladı ama Fact_Mevcut güncellenmemiş):\n")
    for r in stuck:
        print(
            f"  #{r['id']:>4}  {r['created_at']}  {r['person_name']!r:30}  "
            f"{r['source_store']} -> {r['target_store']} ({r['target_title']})  "
            f"fact_status={r['fact_status']!r}"
        )
    print()

    if not args.uygula:
        print("Hiçbir şey UYGULANMADI (salt-okunur mod). Gerçekten uygulamak için:")
        print("    python rotasyon_takili_kontrol.py --uygula")
        return

    print("Uygulanıyor (reconcile_transfer_requests çağrılıyor)...\n")
    from services.management_center import reconcile_transfer_requests

    fm = _load_fm()
    result = reconcile_transfer_requests(fm)

    print("Sonuç:", result)
    print()
    print(
        f"Kontrol edilen: {result.get('checked', 0)}  |  "
        f"Tamamlanan: {result.get('completed', 0)}  |  "
        f"Otomatik uygulanan: {result.get('applied', 0)}  |  "
        f"Uyumsuz (elle bakılmalı): {result.get('mismatch', 0)}  |  "
        f"Hâlâ bekleyen/başarısız: {result.get('failed', 0)}"
    )
    if result.get("applied", 0):
        print(
            "\nEn az bir kayıt otomatik uygulandı. Excel raporunun (mağaza "
            "sekmeleri) da güncellenmesi için main.py'yi çalıştırmanız ya da "
            "panelden bir yenileme tetiklemeniz gerekir (RUN_REPORTS job'ı "
            "worker.py tarafından işlenmeli): \n"
            "    python main.py"
        )
    if result.get("mismatch", 0):
        print(
            "\nUYARI: 'Uyumsuz' işaretlenen kayıtlar var — bu personelin "
            "Fact_Mevcut'ta ne kaynak ne de hedef mağazada göründüğü anlamına "
            "gelir (örn. isim farklı yazılmış olabilir). Bunlar elle kontrol "
            "edilmeli, otomatik uygulanmaz."
        )


if __name__ == "__main__":
    main()

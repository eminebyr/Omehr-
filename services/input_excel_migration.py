"""GERİYE DÖNÜK UYUMLULUK SHIM'İ — bkz. services/data_access/input_excel_migration.py

services/data_access/ bounded-context'ine taşındı (bkz.
SERVICE_BOUNDARIES.md "Veri Erişimi / Excel Katmanı" alanı).

DİKKAT: bu dosya VERITABANI_GECIS_MIMARISI.md'de belgelenen
`python3 services/input_excel_migration.py <excel_yolu>` komut satırı
kullanımını da destekler — bu yüzden yalnız `import *` DEĞİL, orijinal
`__main__` giriş noktası da burada AYNEN korunur.
"""
import sys

from services.data_access.input_excel_migration import *  # noqa: F401,F403
from services.data_access.input_excel_migration import migrate_excel_to_db

if __name__ == "__main__":
    yol = sys.argv[1] if len(sys.argv) > 1 else "input/OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    kiraci = sys.argv[2] if len(sys.argv) > 2 else None
    sonuc = migrate_excel_to_db(yol, tenant_id=kiraci)
    toplam = sum(v["satir"] for v in sonuc.values())
    basarisiz = [k for k, v in sonuc.items() if v["durum"] != "OK"]
    print(f"Göç tamamlandı: {len(sonuc)} sayfa, {toplam} satır.")
    if basarisiz:
        print("EXCEL'DE BULUNAMAYAN SAYFALAR:", basarisiz)

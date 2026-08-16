from __future__ import annotations

"""KRİTİK GÜVENLİK REGRESYON TESTİ.

input/ ve ORNEK_TEST_VERISI/ klasörleri, gerçek görünen düz metin
şifreler ("Admin1", "Ertan1" vb.), gerçek bir şirket domaini
(@basdasmarket.com) ve gerçek görünen kişi isimleri içeren bir örnek
Excel dosyası taşıyordu — kaynağı KESİN olarak doğrulanamadı. Bu iki
klasör artık paketten HARİÇ TUTULUYOR; bu test bunun bir daha
sessizce geri gelmemesini sağlar.
"""

import zipfile


def test_input_and_ornek_test_verisi_excluded_from_package(tmp_path):
    from tools.build_clean_package import build_clean_zip
    from pathlib import Path

    kaynak = Path(__file__).resolve().parents[1]
    hedef = tmp_path / "test_paket.zip"
    build_clean_zip(kaynak, hedef)

    with zipfile.ZipFile(hedef) as z:
        isimler = z.namelist()

    hassas_dosyalar = [n for n in isimler if n.startswith("input/") or n.startswith("ORNEK_TEST_VERISI/")]
    assert hassas_dosyalar == [], (
        f"REGRESYON (KRİTİK GÜVENLİK): input/ veya ORNEK_TEST_VERISI/ "
        f"içindeki dosyalar pakete sızmış: {hassas_dosyalar}"
    )

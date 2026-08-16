"""services/management_center.py::_users_from_input() — çok kiracılı
düzeltme doğrulaması.

DÜZELTME ÖNCESİ: CEO rolündeki (Bölge veya Sorumlu alanı "CEO" olan)
HER kullanıcının görünen adı, gerçek verisi ne olursa olsun SABİT
"M. Feyzi Başdaş" metnine zorlanıyordu — çok kiracılı bir SaaS'ta bu,
her firmanın kendi CEO'sunu yanlış bir isimle gösterirdi.
"""
from __future__ import annotations

import importlib

import pandas as pd
import pytest


def test_ceo_role_shows_tenants_own_name_not_hardcoded_person(isolated_root):
    from services.settings import input_path

    (isolated_root / "input").mkdir(parents=True, exist_ok=True)
    hedef = input_path(isolated_root)
    mail_listesi = pd.DataFrame([
        {"Web Kullanıcı": "ceo1", "Aktif": "Evet", "Bölge": "CEO", "Rol": "",
         "Sorumlu": "Ayşe Yılmaz", "E-posta": "ayse@ornekfirma.com", "Onay Seviyesi": 3},
    ])
    with pd.ExcelWriter(hedef, engine="openpyxl") as writer:
        mail_listesi.to_excel(writer, sheet_name="Mail_Listesi", index=False)

    import services.management_center as mc
    importlib.reload(mc)

    kullanicilar = mc._users_from_input()
    assert len(kullanicilar) == 1
    assert kullanicilar[0]["name"] == "Ayşe Yılmaz", (
        "CEO rolündeki kullanıcının GERÇEK adı gösterilmeli — hardcoded "
        "'M. Feyzi Başdaş' değeri artık dönmemeli."
    )
    assert kullanicilar[0]["role"] == "GM"
    assert kullanicilar[0]["scope"] == "ALL"

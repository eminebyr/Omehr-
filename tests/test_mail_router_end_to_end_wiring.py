from __future__ import annotations

"""mail_router.py'nin GERÇEK gönderim akışına bağlı olduğunu doğrulayan
uçtan uca regresyon testi (report_mail_engine.py::send_reports_via_outlook).

Bu, yalnız mail_router.py'nin fonksiyonlarını izole test etmekten
FARKLI — burada GERÇEK bir Mail_Listesi + gerçek bir gönderim
çağrısıyla, abonelikten çıkan bir kişinin GERÇEKTEN işlem listesine
hiç girmediği kanıtlanır.
"""

import shutil
import pandas as pd


def test_subscription_filter_actually_excludes_opted_out_recipient(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_MAIL_DRY_RUN", "1")
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()

    mail_listesi = pd.DataFrame([
        {"Web Kullanıcı": "abone_kisi", "E-posta": "abone@test.com", "Aktif": "evet", "Bölge": "TÜMÜ", "Norm_Genel": "Evet"},
        {"Web Kullanıcı": "abone_degil_kisi", "E-posta": "abone_degil@test.com", "Aktif": "evet", "Bölge": "TÜMÜ", "Norm_Genel": "Hayır"},
    ])
    hedef = tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    with pd.ExcelWriter(hedef) as w:
        mail_listesi.to_excel(w, sheet_name="Mail_Listesi", index=False)

    import importlib
    import report_mail_engine as rme
    importlib.reload(rme)

    rme.send_reports_via_outlook(hedef, display_only=False)

    import json
    kayitlar = json.loads((tmp_path / "logs" / "BASDAS_Outlook_Gonderim_Log.json").read_text())
    islenen_alicilar = [k["to"] for k in kayitlar]

    assert "abone_degil@test.com" not in islenen_alicilar, (
        "REGRESYON: abonelikten çıkan kişi (Norm_Genel=Hayır) yine de işlem "
        "listesine girdi — mail_router.py'nin abonelik filtresi artık "
        "gerçek gönderim akışına bağlı olmayabilir."
    )

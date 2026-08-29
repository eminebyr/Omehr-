from __future__ import annotations

"""web/app.py DB modu import sırası çöküşü — regresyon testi.

Önceden current_tenant_id() importu, kullanıldığı yerden (satır
~488, modül yüklenirken çalışan _input_mtime_guvenli() çağrısı
içinde) ÇOK SONRA yapılıyordu — yalnız OMEHR_INPUT_SOURCE=db
modunda (Excel modunda bu kod yolu hiç çalışmadığı için) tetiklenen
bir NameError çöküşüne yol açıyordu. Gerçek bir Streamlit sunucusu
DB modunda çalıştırılırken bizzat bulundu.
"""


def test_web_app_does_not_crash_in_db_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_MAIL_DRY_RUN", "1")
    monkeypatch.setenv("OMEHR_DB_BACKEND", "sqlite")
    monkeypatch.setenv("OMEHR_INPUT_SOURCE", "db")
    (tmp_path / "data").mkdir()

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("web/app.py", default_timeout=60)
    at.run()
    assert not at.exception, (
        f"REGRESYON: web/app.py DB modunda çöküyor: {at.exception}"
    )

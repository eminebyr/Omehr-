"""services.powerbi_push testleri.

İKİ FARKLI güven seviyesinde test var:
1. Saf fonksiyonlar (table_schema, dataset_definition, satır dönüşümü) —
   ağ çağrısı YOK, TAM güvenle test edildi.
2. HTTP katmanı (get_access_token, ensure_dataset, push_table) — gerçek
   ağ çağrısı yerine SAHTE bir "session" nesnesiyle test edildi. Bu,
   "doğru isteği doğru biçimde gönderiyor mu" sorusunu cevaplar; "Power
   BI'ın gerçek sunucusu bu isteği kabul ediyor mu" sorusunu CEVAPLAMAZ
   (bkz. services/powerbi_push.py modül docstring'i — bu, gerçek bir
   Azure/Power BI ortamı olmadan doğrulanamaz).
"""
from __future__ import annotations

import pandas as pd
import pytest


# ------------------------------------------------------------------
# Saf fonksiyonlar — ağ çağrısı yok
# ------------------------------------------------------------------

def test_table_schema_maps_pandas_dtypes_to_powerbi_types():
    from services.powerbi_push import table_schema

    df = pd.DataFrame({
        "MağazaID": ["1", "2"],           # object -> String
        "Norm Kadro": [5, 3],              # int64 -> Int64
        "Oran": [0.5, 0.3],                 # float64 -> Double
        "Tarih": pd.to_datetime(["2026-01-01", "2026-01-02"]),  # datetime64 -> Datetime
    })
    schema = table_schema("Fact_Norm", df)

    assert schema["name"] == "Fact_Norm"
    tipler = {c["name"]: c["dataType"] for c in schema["columns"]}
    assert tipler["MağazaID"] == "String"
    assert tipler["Norm Kadro"] == "Int64"
    assert tipler["Oran"] == "Double"
    assert tipler["Tarih"] == "Datetime"


def test_dataset_definition_includes_all_tables_and_relationships():
    from services.powerbi_export import build_powerbi_model
    from services.powerbi_push import dataset_definition

    sheets = {
        "Dim_Magaza": pd.DataFrame([{"MağazaID": 1, "Mağaza": "A", "Bölge Sorumlusu": "X"}]),
        "Dim_Unvan": pd.DataFrame([{"UnvanID": "U1", "Unvan": "Kasiyer"}]),
        "Fact_Norm": pd.DataFrame([{"MağazaID": 1, "UnvanID": "U1", "Norm Kadro": 5}]),
        "Fact_Mevcut": pd.DataFrame([{"PersonelID": "P1", "MağazaID": 1, "UnvanID": "U1"}]),
    }
    model = build_powerbi_model(sheets)
    tanim = dataset_definition(model, "Test Modeli")

    assert tanim["name"] == "Test Modeli"
    assert tanim["defaultMode"] == "Push"
    tablo_adlari = {t["name"] for t in tanim["tables"]}
    assert tablo_adlari == {"Dim_Magaza", "Dim_Unvan", "Dim_Tarih", "Fact_Norm", "Fact_Mevcut"}
    # Dim_Tarih ilişkisi bilerek dahil edilmiyor (bkz. modül docstring'i).
    iliski_tablolari = {(r["fromTable"], r["toTable"]) for r in tanim["relationships"]}
    assert ("Fact_Norm", "Dim_Magaza") in iliski_tablolari
    assert ("Fact_Norm", "Dim_Unvan") in iliski_tablolari
    assert ("Fact_Mevcut", "Dim_Magaza") in iliski_tablolari
    assert not any(t == "Dim_Tarih" for _, t in iliski_tablolari)


def test_rows_are_json_serializable_with_nan_converted_to_none():
    from services.powerbi_push import _satirlari_json_uyumlu_yap
    import json

    df = pd.DataFrame({"A": [1, None], "B": ["x", None]})
    satirlar = _satirlari_json_uyumlu_yap(df)
    # NaN None olmalı, ve tüm çıktı gerçekten JSON'a çevrilebilmeli.
    assert satirlar[1]["A"] is None
    assert satirlar[1]["B"] is None
    json.dumps(satirlar)  # patlamamalı


def test_datetime_rows_are_converted_to_iso_strings():
    from services.powerbi_push import _satirlari_json_uyumlu_yap

    df = pd.DataFrame({"Tarih": pd.to_datetime(["2026-01-15", None])})
    satirlar = _satirlari_json_uyumlu_yap(df)
    assert satirlar[0]["Tarih"] == "2026-01-15T00:00:00"
    assert satirlar[1]["Tarih"] is None


def test_config_from_env_raises_clear_error_when_missing(monkeypatch):
    from services.powerbi_push import PowerBIConfig
    from services.exceptions import ConfigurationError

    for ad in ("BASDAS_POWERBI_TENANT_ID", "BASDAS_POWERBI_CLIENT_ID",
               "BASDAS_POWERBI_CLIENT_SECRET", "BASDAS_POWERBI_WORKSPACE_ID"):
        monkeypatch.delenv(ad, raising=False)

    with pytest.raises(ConfigurationError):
        PowerBIConfig.from_env()


def test_config_from_env_reads_all_values(monkeypatch):
    from services.powerbi_push import PowerBIConfig

    monkeypatch.setenv("BASDAS_POWERBI_TENANT_ID", "tenant-123")
    monkeypatch.setenv("BASDAS_POWERBI_CLIENT_ID", "client-456")
    monkeypatch.setenv("BASDAS_POWERBI_CLIENT_SECRET", "gizli-sir")
    monkeypatch.setenv("BASDAS_POWERBI_WORKSPACE_ID", "ws-789")

    config = PowerBIConfig.from_env()
    assert config.tenant_id == "tenant-123"
    assert config.client_id == "client-456"
    assert config.client_secret == "gizli-sir"
    assert config.workspace_id == "ws-789"
    assert config.dataset_name == "BASDAS Norm Kadro Modeli"  # varsayılan


# ------------------------------------------------------------------
# HTTP katmanı — SAHTE session ile (gerçek ağ çağrısı YOK)
# ------------------------------------------------------------------

class _SahteYanit:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or str(json_data)

    def json(self):
        return self._json_data


class _SahteSession:
    """requests modülünün yerine geçen, çağrıları kaydeden sahte nesne."""

    def __init__(self):
        self.cagrilar = []
        self.post_yaniti = _SahteYanit(200, {"access_token": "sahte-token"})
        self.get_yaniti = _SahteYanit(200, {"value": []})
        self.delete_yaniti = _SahteYanit(200, {})

    def post(self, url, **kwargs):
        self.cagrilar.append(("POST", url, kwargs))
        return self.post_yaniti

    def get(self, url, **kwargs):
        self.cagrilar.append(("GET", url, kwargs))
        return self.get_yaniti

    def delete(self, url, **kwargs):
        self.cagrilar.append(("DELETE", url, kwargs))
        return self.delete_yaniti


def _ornek_config():
    from services.powerbi_push import PowerBIConfig
    return PowerBIConfig(tenant_id="t1", client_id="c1", client_secret="s1", workspace_id="w1", dataset_name="Test")


def test_get_access_token_sends_correct_oauth_request():
    from services.powerbi_push import get_access_token

    session = _SahteSession()
    token = get_access_token(_ornek_config(), session)

    assert token == "sahte-token"
    yontem, url, kwargs = session.cagrilar[0]
    assert yontem == "POST"
    assert "login.microsoftonline.com/t1" in url
    assert kwargs["data"]["grant_type"] == "client_credentials"
    assert kwargs["data"]["client_id"] == "c1"
    assert kwargs["data"]["client_secret"] == "s1"
    assert "analysis.windows.net/powerbi" in kwargs["data"]["scope"]


def test_get_access_token_raises_clear_error_on_auth_failure():
    from services.powerbi_push import get_access_token
    from services.exceptions import WorkbookError

    session = _SahteSession()
    session.post_yaniti = _SahteYanit(401, {}, text="invalid_client")

    with pytest.raises(WorkbookError):
        get_access_token(_ornek_config(), session)


def test_ensure_dataset_reuses_existing_dataset_by_name():
    from services.powerbi_push import ensure_dataset
    from services.powerbi_export import build_powerbi_model

    session = _SahteSession()
    session.get_yaniti = _SahteYanit(200, {"value": [{"id": "var-olan-id", "name": "Test"}]})
    model = build_powerbi_model({})

    dataset_id = ensure_dataset(_ornek_config(), "token", model, session)

    assert dataset_id == "var-olan-id"
    # Var olan bulunduğu için YENİ bir dataset OLUŞTURULMAMALI (POST çağrılmamalı).
    assert not any(y == "POST" for y, _, _ in session.cagrilar)


def test_ensure_dataset_creates_new_when_none_exists():
    from services.powerbi_push import ensure_dataset
    from services.powerbi_export import build_powerbi_model

    session = _SahteSession()
    session.get_yaniti = _SahteYanit(200, {"value": []})  # hiç dataset yok
    session.post_yaniti = _SahteYanit(201, {"id": "yeni-id"})
    model = build_powerbi_model({})

    dataset_id = ensure_dataset(_ornek_config(), "token", model, session)

    assert dataset_id == "yeni-id"
    post_cagrisi = next(c for c in session.cagrilar if c[0] == "POST")
    gonderilen_tanim = post_cagrisi[2]["json"]
    assert gonderilen_tanim["name"] == "Test"
    assert gonderilen_tanim["defaultMode"] == "Push"


def test_push_table_deletes_existing_rows_before_inserting():
    from services.powerbi_push import push_table

    session = _SahteSession()
    df = pd.DataFrame([{"MağazaID": "1", "Norm Kadro": 5}])

    adet = push_table(_ornek_config(), "token", "ds-1", "Fact_Norm", df, session)

    assert adet == 1
    yontemler = [c[0] for c in session.cagrilar]
    assert yontemler.index("DELETE") < yontemler.index("POST")  # önce sil, sonra ekle


def test_push_table_splits_large_dataframes_into_chunks():
    from services.powerbi_push import push_table, MAX_ROWS_PER_REQUEST

    session = _SahteSession()
    satir_sayisi = MAX_ROWS_PER_REQUEST + 5
    df = pd.DataFrame({"MağazaID": [str(i) for i in range(satir_sayisi)]})

    adet = push_table(_ornek_config(), "token", "ds-1", "Fact_Norm", df, session)

    assert adet == satir_sayisi
    post_cagrilari = [c for c in session.cagrilar if c[0] == "POST"]
    assert len(post_cagrilari) == 2  # 10.000 + 5 -> 2 parça


def test_push_table_raises_clear_error_on_insert_failure():
    from services.powerbi_push import push_table
    from services.exceptions import WorkbookError

    session = _SahteSession()
    session.post_yaniti = _SahteYanit(400, {}, text="Bad schema")
    df = pd.DataFrame([{"MağazaID": "1"}])

    with pytest.raises(WorkbookError):
        push_table(_ornek_config(), "token", "ds-1", "Fact_Norm", df, session)


def test_push_to_powerbi_end_to_end_with_fake_session():
    from services.powerbi_push import push_to_powerbi

    session = _SahteSession()
    session.get_yaniti = _SahteYanit(200, {"value": []})
    # post_yaniti hem token hem dataset-create hem rows için kullanılacak;
    # id/access_token'ı ikisinin de bulacağı şekilde ayarla.
    session.post_yaniti = _SahteYanit(200, {"access_token": "tok", "id": "ds-1"})

    sheets = {
        "Dim_Magaza": pd.DataFrame([{"MağazaID": 1, "Mağaza": "A", "Bölge Sorumlusu": "X"}]),
        "Dim_Unvan": pd.DataFrame([{"UnvanID": "U1", "Unvan": "Kasiyer"}]),
        "Fact_Norm": pd.DataFrame([{"MağazaID": 1, "UnvanID": "U1", "Norm Kadro": 5}]),
        "Fact_Mevcut": pd.DataFrame([{"PersonelID": "P1", "MağazaID": 1, "UnvanID": "U1"}]),
    }

    sonuc = push_to_powerbi(sheets, _ornek_config(), session)

    assert sonuc["dataset_id"] == "ds-1"
    assert set(sonuc["tablolar"]) == {"Dim_Magaza", "Dim_Unvan", "Dim_Tarih", "Fact_Norm", "Fact_Mevcut"}
    assert sonuc["tablolar"]["Fact_Norm"] == 1

"""POWER BI REST API — DATASET PUSH MOTORU.

Bu modül, services/powerbi_export.py'nin ürettiği temiz star şema
modelini (Dim_Magaza, Dim_Unvan, Dim_Tarih, Fact_Norm, Fact_Mevcut),
Power BI REST API'sine GERÇEKTEN gönderir (bir "push dataset" oluşturup/
güncelleyerek) — Excel dosyasını elle Power BI Desktop'a bağlamak yerine.

DÜRÜSTÇE ÖNEMLİ SINIR: Bu kod, bu paketi hazırlayan ortamda GERÇEK bir
Power BI/Azure AD servisine karşı TEST EDİLEMEDİ — bu ortamın ağ erişimi
Microsoft uç noktalarına kapalı, ve gerçek bir Azure AD uygulama kaydı/
kimlik bilgisi de yoktu. HTTP katmanı (istek gövdeleri, URL'ler, veri
dönüşümleri) mock'lanarak test edildi (bkz. tests/test_powerbi_push.py)
— yani "doğru isteği doğru biçimde gönderiyor" doğrulandı, ama "Power
BI'ın gerçek sunucusu bu isteği kabul ediyor" doğrulanamadı. İlk gerçek
kullanımda küçük bir uyumsuzluk (ör. API'nin kendisinin zamanla
değişmiş bir alanı) çıkarsa şaşırtıcı olmaz — hatayı paylaşırsanız
hemen düzeltirim.

## Kurulum (Azure AD tarafı — bu adımlar bu kod tarafından YAPILAMAZ,
sizin/BT ekibinizin Azure portalında elle yapması gerekir):

1. https://portal.azure.com > Azure Active Directory > Uygulama kayıtları
   > Yeni kayıt. Bir isim verin (ör. "BASDAS Power BI Push").
2. Kaydedilen uygulamanın "Uygulama (istemci) Kimliği" ve
   "Dizin (kiracı) Kimliği" değerlerini not edin.
3. Sertifikalar ve gizli anahtarlar > Yeni istemci gizli anahtarı
   oluşturun, DEĞERİNİ hemen kopyalayın (bir daha gösterilmez).
4. API izinleri > İzin ekle > Power BI Service > Uygulama izinleri >
   Dataset.ReadWrite.All (veya Tenant.ReadWrite.All) seçin, yönetici
   onayı verin.
5. Power BI (app.powerbi.com) tarafında: hedef çalışma alanına (workspace)
   gidin, "Erişim yönetimi" ile bu uygulamayı (Azure AD App'i) EKLEYİN
   (En az "Katkıda Bulunan" yetkisiyle) — API izni tek başına yetmez,
   çalışma alanına da eklenmesi gerekir.
6. Çalışma alanının ID'sini URL'den alın (app.powerbi.com/groups/{BURASI}).

Bu 6 bilgi (tenant_id, client_id, client_secret, workspace_id) ortam
değişkenleriyle (BASDAS_POWERBI_*) sisteme tanıtılır — bkz. aşağıdaki
Config sınıfı.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from services.exceptions import ConfigurationError, WorkbookError

AUTHORITY_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
MAX_ROWS_PER_REQUEST = 10_000  # Power BI push API'nin belgelenen tek istekteki satır sınırı

# pandas dtype -> Power BI push dataset dataType (yalnız belgelenen 4 değer geçerlidir)
_DTYPE_MAP = {
    "int64": "Int64", "Int64": "Int64",
    "float64": "Double",
    "bool": "Boolean",
    "object": "String",
}


@dataclass(frozen=True)
class PowerBIConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    workspace_id: str
    dataset_name: str = "BASDAS Norm Kadro Modeli"

    @classmethod
    def from_env(cls) -> "PowerBIConfig":
        """Ortam değişkenlerinden okur. Parola/sır gibi diğer tüm gizli
        bilgiler (SMTP parolası vb.) bu projede aynı desenle — config
        dosyasında DEĞİL, ortam değişkeninde — tutuluyor."""
        eksikler = [
            ad for ad in ("OMEHR_POWERBI_TENANT_ID", "OMEHR_POWERBI_CLIENT_ID",
                          "OMEHR_POWERBI_CLIENT_SECRET", "OMEHR_POWERBI_WORKSPACE_ID")
            if not os.environ.get(ad, "").strip()
        ]
        if eksikler:
            raise ConfigurationError(
                "Power BI push için şu ortam değişkenleri eksik: " + ", ".join(eksikler) +
                " — bkz. services/powerbi_push.py modül docstring'indeki Azure AD kurulum adımları."
            )
        return cls(
            tenant_id=os.environ["OMEHR_POWERBI_TENANT_ID"].strip(),
            client_id=os.environ["OMEHR_POWERBI_CLIENT_ID"].strip(),
            client_secret=os.environ["OMEHR_POWERBI_CLIENT_SECRET"].strip(),
            workspace_id=os.environ["OMEHR_POWERBI_WORKSPACE_ID"].strip(),
            dataset_name=os.environ.get("OMEHR_POWERBI_DATASET_NAME", "BASDAS Norm Kadro Modeli").strip(),
        )


def _powerbi_dtype(seri: pd.Series) -> str:
    dtype_str = str(seri.dtype)
    # DÜZELTME: pandas sürümüne göre datetime dtype'ı "datetime64[ns]",
    # "datetime64[us]" gibi FARKLI hassasiyet birimleriyle gösterilebilir
    # (pandas 3.x varsayılanı [us]'dir) — sabit anahtarlı sözlük araması
    # bunu KAÇIRIYORDU (testte yakalandı: gerçek üretim pandas sürümüyle
    # "Datetime" yerine sessizce "String" dönüyordu). Önek kontrolü
    # kullanılır, hassasiyet biriminden bağımsız çalışır.
    if dtype_str.startswith("datetime64"):
        return "Datetime"
    return _DTYPE_MAP.get(dtype_str, "String")


def table_schema(name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Bir DataFrame'den Power BI push dataset tablo şeması üretir (saf
    fonksiyon — ağ çağrısı yok, tam olarak test edilebilir)."""
    return {
        "name": name,
        "columns": [{"name": str(kolon), "dataType": _powerbi_dtype(df[kolon])} for kolon in df.columns],
    }


def dataset_definition(model: dict[str, pd.DataFrame], dataset_name: str) -> dict[str, Any]:
    """services.powerbi_export.build_powerbi_model()'in çıktısından TAM
    bir Power BI push dataset tanımı (tablolar + ilişkiler) üretir. Saf
    fonksiyon — ağ çağrısı yok."""
    tablolar = [
        table_schema("Dim_Magaza", model["dim_magaza"]),
        table_schema("Dim_Unvan", model["dim_unvan"]),
        table_schema("Dim_Tarih", model["dim_tarih"]),
        table_schema("Fact_Norm", model["fact_norm"]),
        table_schema("Fact_Mevcut", model["fact_mevcut"]),
    ]
    iliskiler = [
        {
            "name": f"{row['Fact Tablosu']}_{row['Fact Sütunu']}_{row['Dim Tablosu']}",
            "fromTable": row["Fact Tablosu"], "fromColumn": row["Fact Sütunu"],
            "toTable": row["Dim Tablosu"], "toColumn": row["Dim Sütunu"],
            "crossFilteringBehavior": "OneDirection",
        }
        for _, row in model["iliskiler"].iterrows()
        if row["Dim Tablosu"] != "Dim_Tarih"
    ]
    return {
        "name": dataset_name,
        "defaultMode": "Push",
        "tables": tablolar,
        "relationships": iliskiler,
    }


def _satirlari_json_uyumlu_yap(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Bir DataFrame'i Power BI push API'sinin beklediği satır listesine
    (JSON-uyumlu, NaN'siz, tarihler ISO metin) çevirir. Saf fonksiyon."""
    df = df.copy()
    for kolon in df.columns:
        if str(df[kolon].dtype).startswith("datetime64"):
            df[kolon] = df[kolon].dt.strftime("%Y-%m-%dT%H:%M:%S")
    kayitlar = df.to_dict(orient="records")
    # DÜZELTME: pandas'a (Series/DataFrame İÇİNDEYKEN) None yerleştirmeye
    # çalışmak — ör. `.where(cond, None)` veya `.apply(lambda: ... else None)`
    # — pandas tarafından SESSİZCE NaN'a normalize ediliyor (belgelenmiş
    # pandas davranışı; testte yakalandı). Bu yüzden None dönüşümü, veri
    # ARTIK düz Python sözlüklerine geçtikten SONRA, tek tek yapılır.
    for kayit in kayitlar:
        for anahtar, deger in list(kayit.items()):
            if pd.isna(deger):
                kayit[anahtar] = None
    return kayitlar


def get_access_token(config: PowerBIConfig, session: requests.Session | None = None) -> str:
    """Azure AD'den (client credentials akışı — kullanıcı etkileşimi
    gerektirmez, main.py gibi otomatik/zamanlanmış çalıştırmalar için
    uygundur) bir erişim token'ı alır."""
    session = session or requests
    url = AUTHORITY_URL_TEMPLATE.format(tenant_id=config.tenant_id)
    veri = {
        "grant_type": "client_credentials",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "scope": POWERBI_SCOPE,
    }
    yanit = session.post(url, data=veri, timeout=30)
    if yanit.status_code != 200:
        raise WorkbookError(
            f"Power BI/Azure AD kimlik doğrulaması başarısız (HTTP {yanit.status_code}): "
            f"{yanit.text[:500]}"
        )
    token = yanit.json().get("access_token")
    if not token:
        raise WorkbookError("Azure AD yanıtında access_token bulunamadı.")
    return token


def _find_existing_dataset_id(config: PowerBIConfig, token: str, session: requests.Session) -> str | None:
    url = f"{POWERBI_API_BASE}/groups/{config.workspace_id}/datasets"
    yanit = session.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if yanit.status_code != 200:
        raise WorkbookError(f"Power BI dataset listesi alınamadı (HTTP {yanit.status_code}): {yanit.text[:500]}")
    for ds in yanit.json().get("value", []):
        if ds.get("name") == config.dataset_name:
            return ds.get("id")
    return None


def ensure_dataset(config: PowerBIConfig, token: str, model: dict[str, pd.DataFrame], session: requests.Session | None = None) -> str:
    """Aynı isimde bir dataset varsa ID'sini döner; yoksa şemayı
    OLUŞTURUR ve yeni ID'yi döner. Şema değiştiyse (ör. yeni bir sütun
    eklendiyse) var olan dataset'i GÜNCELLEMEZ — Power BI push API'si
    şema güncellemeyi doğrudan desteklemez; şema değiştiyse dataset'in
    Power BI tarafında silinip yeniden oluşturulması gerekir."""
    session = session or requests
    mevcut_id = _find_existing_dataset_id(config, token, session)
    if mevcut_id:
        return mevcut_id

    tanim = dataset_definition(model, config.dataset_name)
    url = f"{POWERBI_API_BASE}/groups/{config.workspace_id}/datasets"
    yanit = session.post(
        url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=tanim, timeout=60,
    )
    if yanit.status_code not in (200, 201):
        raise WorkbookError(f"Power BI dataset oluşturulamadı (HTTP {yanit.status_code}): {yanit.text[:500]}")
    yeni_id = yanit.json().get("id")
    if not yeni_id:
        raise WorkbookError("Power BI dataset oluşturma yanıtında id bulunamadı.")
    return yeni_id


def push_table(config: PowerBIConfig, token: str, dataset_id: str, table_name: str, df: pd.DataFrame, session: requests.Session | None = None) -> int:
    """Bir tablonun MEVCUT satırlarını SİLİP yerine df'teki satırları
    yazar (tam yenileme — kısmi/artımlı güncelleme değil, bu yüzden
    her çalıştırmada tabloyu tümüyle temsil eden bir df verilmelidir).
    Satır sayısı MAX_ROWS_PER_REQUEST'i aşıyorsa otomatik olarak
    parçalara bölünür. Dönüş: gönderilen toplam satır sayısı."""
    session = session or requests
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = f"{POWERBI_API_BASE}/groups/{config.workspace_id}/datasets/{dataset_id}/tables/{table_name}"

    sil_yaniti = session.delete(f"{base}/rows", headers=headers, timeout=60)
    if sil_yaniti.status_code not in (200, 404):
        raise WorkbookError(f"'{table_name}' tablosu temizlenemedi (HTTP {sil_yaniti.status_code}): {sil_yaniti.text[:500]}")

    satirlar = _satirlari_json_uyumlu_yap(df)
    gonderilen = 0
    for i in range(0, len(satirlar), MAX_ROWS_PER_REQUEST):
        parca = satirlar[i:i + MAX_ROWS_PER_REQUEST]
        yanit = session.post(f"{base}/rows", headers=headers, json={"rows": parca}, timeout=120)
        if yanit.status_code not in (200, 201):
            raise WorkbookError(
                f"'{table_name}' tablosuna satır eklenemedi (HTTP {yanit.status_code}, "
                f"satır {i}-{i+len(parca)}): {yanit.text[:500]}"
            )
        gonderilen += len(parca)
    return gonderilen


def push_to_powerbi(sheets: dict[str, pd.DataFrame], config: PowerBIConfig | None = None, session: requests.Session | None = None) -> dict[str, Any]:
    """Uçtan uca akış: model oluştur -> token al -> dataset'i garanti et
    -> her tabloyu gönder. main.py'den (otomatik/zamanlanmış) veya web
    panelindeki bir düğmeden çağrılabilir."""
    from services.powerbi_export import build_powerbi_model

    config = config or PowerBIConfig.from_env()
    model = build_powerbi_model(sheets)
    session = session or requests

    token = get_access_token(config, session)
    dataset_id = ensure_dataset(config, token, model, session)

    sonuc = {"dataset_id": dataset_id, "tablolar": {}}
    for tablo_adi, df_anahtari in (
        ("Dim_Magaza", "dim_magaza"), ("Dim_Unvan", "dim_unvan"), ("Dim_Tarih", "dim_tarih"),
        ("Fact_Norm", "fact_norm"), ("Fact_Mevcut", "fact_mevcut"),
    ):
        adet = push_table(config, token, dataset_id, tablo_adi, model[df_anahtari], session)
        sonuc["tablolar"][tablo_adi] = adet

    sonuc["yetim_norm_sayisi"] = len(model["yetim_norm"])
    sonuc["yetim_mevcut_sayisi"] = len(model["yetim_mevcut"])
    return sonuc

from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

CONTROL_FILENAME = "KONTROL_NORM_KADRO_24_07_2026.xlsx"
# DÜZELTME: sabit 4 isimlik REGIONS listesi kaldırıldı — kullanılmıyordu.
# Bölge Sorumlusu adı, Mevcut/Norm Eksiği/Net İhtiyaç gibi diğer tüm
# alanlarla aynı ilkeye göre TAMAMEN veri kaynaklı olmalı — 4, 6 ya da
# başka herhangi bir sayıda bölge müdürü ismiyle çalışmalı.

def text_key(value) -> str:
    s = str(value or "").strip().upper()
    table = str.maketrans("İŞĞÜÖÇ", "ISGUOC")
    s = s.translate(table)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s


def _lookup_bagimsizlastir(sheets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Fact_Mevcut/Fact_Norm'daki Mağaza/Bölge Sorumlusu/Unvan sütunlarını,
    Excel formülünün (LibreOffice) hesaplanıp hesaplanmadığından bağımsız
    olarak Dim_Magaza/Dim_Unvan'dan Python'da yeniden türetir. Girdi
    sözlüğünü değiştirmez, kopyalarını döndürür."""
    sheets = dict(sheets)
    dim_magaza = sheets.get("Dim_Magaza")
    dim_unvan = sheets.get("Dim_Unvan")
    mag_ad_map, mag_bolge_map, unvan_ad_map = {}, {}, {}
    if dim_magaza is not None and not dim_magaza.empty and {"MağazaID", "Mağaza"}.issubset(dim_magaza.columns):
        mag_ad_map = dict(zip(dim_magaza["MağazaID"], dim_magaza["Mağaza"]))
        if "Bölge Sorumlusu" in dim_magaza.columns:
            mag_bolge_map = dict(zip(dim_magaza["MağazaID"], dim_magaza["Bölge Sorumlusu"]))
    if dim_unvan is not None and not dim_unvan.empty and {"UnvanID", "Unvan"}.issubset(dim_unvan.columns):
        unvan_ad_map = dict(zip(dim_unvan["UnvanID"], dim_unvan["Unvan"]))
    for ad in ("Fact_Mevcut", "Fact_Norm"):
        if ad not in sheets or sheets[ad] is None or sheets[ad].empty:
            continue
        df = sheets[ad].copy()
        if "MağazaID" in df.columns:
            if "Mağaza" in df.columns and mag_ad_map:
                df["Mağaza"] = df["MağazaID"].map(mag_ad_map).fillna(df["Mağaza"])
            if "Bölge Sorumlusu" in df.columns and mag_bolge_map:
                df["Bölge Sorumlusu"] = df["MağazaID"].map(mag_bolge_map).fillna(df["Bölge Sorumlusu"])
        if "UnvanID" in df.columns and "Unvan" in df.columns and unvan_ad_map:
            df["Unvan"] = df["UnvanID"].map(unvan_ad_map).fillna(df["Unvan"])
        sheets[ad] = df
    return sheets

STORE_ALIASES = {
    "BUCA2MENDERES": "BUCA2",
    "BUCAMENDERES": "BUCA2",
    "BUCA": "BUCAFIRAT",
    "EFELER": "AYDINEFELER",
    "TORBALI": "TORBALI1",
}

def store_key(value) -> str:
    k = text_key(value)
    # GAZIEMIR -2 / TORBALI-2 gibi tire-boşluk farklarını tekilleştirir.
    return STORE_ALIASES.get(k, k)

ROLE_ALIASES = {
    "YONETICIY": "YONETICIYARDIMCISI",
    "YONETICIYARD": "YONETICIYARDIMCISI",
    "YONETICIYARDIMCISI": "YONETICIYARDIMCISI",
    "REYON": "REYONGOREVLISI",
    "SARKUTERIY": "SARKUTERIYARDIMCISI",
    "SARKUTERIYARDIMCISI": "SARKUTERIYARDIMCISI",
    "KASAPY": "KASAPYARDIMCISI",
    "KASAPYARDIMCISI": "KASAPYARDIMCISI",
    "MANAVYARD": "MANAVYARDIMCISI",
    "MANAVYARDIMCISI": "MANAVYARDIMCISI",
    "PARTTIME": "PARTTIME",
    "PARTTİME": "PARTTIME",
    "PARTTME": "PARTTIME",
    "UNLUMAMULLER": "UNLUMAMULLER",
    "UNLUMAMÜLLER": "UNLUMAMULLER",
}

def role_key(value) -> str:
    k = text_key(value)
    return ROLE_ALIASES.get(k, k)

DISPLAY_ROLE = {
    "YONETICI": "YÖNETİCİ",
    "YONETICIYARDIMCISI": "YÖNETİCİ YARDIMCISI",
    "KASIYER": "KASİYER",
    "REYONGOREVLISI": "REYON GÖREVLİSİ",
    "BAKLIYAT": "BAKLİYAT",
    "SARKUTERI": "ŞARKÜTERİ",
    "SARKUTERIYARDIMCISI": "ŞARKÜTERİ YARDIMCISI",
    "KASAP": "KASAP",
    "KASAPYARDIMCISI": "KASAP YARDIMCISI",
    "MANAV": "MANAV",
    "MANAVYARDIMCISI": "MANAV YARDIMCISI",
    "MANAVTERAZI": "MANAV TERAZİ",
    "PARTTIME": "PART TİME",
    "ONLINESOFOR": "ONLİNE ŞOFÖR",
    "ONLINETOPLAYICI": "ONLİNE TOPLAYICI",
    "UNLUMAMULLER": "UNLU MAMÜLLER",
    "KOZMETIK": "KOZMETİK",
}

def active_people(frame: pd.DataFrame) -> pd.DataFrame:
    """DÜZELTME (KRİTİK çok-kiracılı hata): bu fonksiyon önceden
    Bölge Sorumlusu'nun SABİT, 4 gerçek isimden oluşan bir listede
    (REGIONS) olmasını ŞART koşuyordu — orijinal firma DIŞINDAKİ HER
    kiracı için TÜM aktif personeli bu kontrolden dolayı "aktif değil"
    sayıp Genel Özet panosundaki Aktif Mevcut/detay tablolarını
    SESSİZCE boşaltıyordu (bizzat kanıtlandı: 2 aktif kişiden 0'ı aktif
    sayılıyordu). Artık merkezi, kiracıdan bağımsız kurala
    (services.personnel_status.active_people — yalnız çıkış durumuna
    bakar) devrediyor; REGIONS/bölge filtresi TAMAMEN kaldırıldı."""
    from services.personnel_status import active_people as _merkezi_aktif_personel
    return _merkezi_aktif_personel(frame)

def reconcile_store_net(frame: pd.DataFrame) -> pd.DataFrame:
    """Mağaza net farkını unvan satırlarına eksiksiz dağıtır.

    Kutucuklarda brüt unvan açığı/fazlası değil mağazanın net durumu gösterilir.
    Fazla mağazada yalnızca fazla, eksik mağazada yalnızca eksik işaretlenir.
    Dağıtım, departman bazındaki en büyük Mevcut-Norm farkından başlar.
    """
    x = frame.copy()
    x["Eksik"] = 0
    x["Fazla"] = 0
    keys = ["Bölge Sorumlusu", "MağazaID", "Mağaza"]
    for _, indexes in x.groupby(keys, dropna=False).groups.items():
        idx = list(indexes)
        gaps = (
            pd.to_numeric(x.loc[idx, "Mevcut"], errors="coerce").fillna(0)
            - pd.to_numeric(x.loc[idx, "Norm"], errors="coerce").fillna(0)
        ).astype(int)
        net = int(gaps.sum())
        if net > 0:
            remaining = net
            for row_index in gaps[gaps > 0].sort_values(ascending=False).index:
                amount = min(int(gaps.loc[row_index]), remaining)
                x.at[row_index, "Fazla"] = amount
                remaining -= amount
                if remaining == 0:
                    break
        elif net < 0:
            remaining = -net
            for row_index in (-gaps[gaps < 0]).sort_values(ascending=False).index:
                amount = min(int(-gaps.loc[row_index]), remaining)
                x.at[row_index, "Eksik"] = amount
                remaining -= amount
                if remaining == 0:
                    break
    return x

def _long_control(df: pd.DataFrame, store_col: str, value_name: str) -> pd.DataFrame:
    x = df.copy()
    x = x[x[store_col].notna()].copy()
    x = x[~x[store_col].astype(str).str.strip().str.upper().eq("TOPLAM")]
    cols = [c for c in x.columns if c not in {"Unnamed: 0", store_col, "TOPLAM", "TAKIM LİDERİ"}]
    rows = []
    for _, r in x.iterrows():
        store = str(r[store_col]).strip()
        for col in cols:
            v = pd.to_numeric(pd.Series([r.get(col)]), errors="coerce").fillna(0).iloc[0]
            if float(v) != 0:
                rk = role_key(col)
                rows.append({"StoreKey": store_key(store), "Mağaza": store, "RoleKey": rk,
                             "Unvan": DISPLAY_ROLE.get(rk, str(col).strip()), value_name: int(v)})
    return pd.DataFrame(rows)

def _long_fact_norm(df: pd.DataFrame) -> pd.DataFrame:
    """Güncel Fact_Norm'u mağaza + departman/unvan seviyesinde toplar."""
    x = df.copy()
    x = x[x["Mağaza"].notna()].copy()
    x["StoreKey"] = x["Mağaza"].map(store_key)
    x["RoleKey"] = x["Unvan"].map(role_key)
    x["Norm"] = pd.to_numeric(x["Norm Kadro"], errors="coerce").fillna(0)
    grouped = x.groupby(["StoreKey", "RoleKey"], as_index=False)["Norm"].sum()
    grouped["Norm"] = grouped["Norm"].astype(int)
    store_names = x.drop_duplicates("StoreKey").set_index("StoreKey")["Mağaza"].to_dict()
    role_names = x.drop_duplicates("RoleKey").set_index("RoleKey")["Unvan"].to_dict()
    grouped["Mağaza"] = grouped["StoreKey"].map(store_names)
    grouped["Unvan"] = grouped["RoleKey"].map(role_names)
    return grouped

def build_dashboard_model(sheets: dict[str, pd.DataFrame], control_path: Path):
    # KRİTİK GÜVENİLİRLİK ADIMI: Fact_Mevcut/Fact_Norm'daki Mağaza/Bölge
    # Sorumlusu/Unvan sütunları Excel formülüdür (VLOOKUP). LibreOffice
    # dosyayı henüz yeniden hesaplamadıysa bu sütunlar BOŞ okunur ve bu
    # fonksiyonun ürettiği "detail" tablosundaki Eksik/Fazla mağaza
    # gruplamaları sessizce bozulur (CEO Özet'teki "En Riskli Mağazalar" /
    # "Norm Fazlası" listelerinin neredeyse boş görünmesinin nedeni budur).
    # engine_core.py'de uygulanan AYNI düzeltme burada da tekrarlanır:
    # Dim_Magaza/Dim_Unvan'dan Python'da kendi VLOOKUP eşdeğerimizi
    # uygularız, LibreOffice'in çalışıp çalışmadığından bağımsız olarak.
    sheets = _lookup_bagimsizlastir(sheets)
    fm = active_people(sheets["Fact_Mevcut"])
    norm = _long_fact_norm(sheets["Fact_Norm"])
    baseline_path = control_path.with_name("NORM_KAPSAM_BAZI.json")
    if baseline_path.is_file():
        import json
        baseline = pd.DataFrame(json.loads(baseline_path.read_text(encoding="utf-8")).get("rows", []))
        required = {"StoreKey", "RoleKey", "BaselineRaw", "BaselineEffective", "InScope"}
        if baseline.empty or not required.issubset(baseline.columns):
            raise ValueError("Norm kapsam başlangıç dosyasının şeması geçersiz.")
        baseline["_HasBaseline"] = True
    else:
        # DÜZELTME: Bu, eski/terk edilmiş bir kalibrasyon mekanizmasıdır
        # (bkz. src/state_engine.py'deki "KULLANICI KARARI: ... KALDIRILDI"
        # notu — taban dosyasına göre delta hesaplamak, Fact_Norm/
        # Fact_Mevcut güncellendiğinde rakamların ESKİ değerde "takılı"
        # kalmasına yol açtığı için BİLEREK terk edilmişti). Taban dosyası
        # yoksa (yeni kurulum, ya da müşteriye özel eski bir tarihli
        # anlık görüntü hiç verilmemişse) fonksiyon artık ÇÖKMÜYOR — boş
        # bir taban ile devam ediyor. Aşağıdaki `has_baseline` bayrağı bu
        # durumda TÜM satırlar için False olacak ve zaten var olan
        # "taban yoksa effective=Mevcut" yedek yoluna (bkz. ~290. satır)
        # düşülecek — bu, state_engine.py'nin güncel/doğru mantığıyla
        # birebir tutarlıdır.
        baseline = pd.DataFrame(columns=["StoreKey", "RoleKey", "BaselineRaw", "BaselineEffective", "InScope", "_HasBaseline"])
    # SAVUNMA: baseline.json'dan gelen StoreKey/RoleKey sayısal görünümlü
    # (ör. tamamen rakamlardan oluşan bir mağaza kodu) olabilir ve JSON'da
    # sayı olarak saklanmışsa pandas bunu float64 okuyabilir; norm tarafında
    # ise bu hep string'dir. Tip uyuşmazlığı merge'ü ValueError ile
    # çökertir ("You are trying to merge on str and float64 columns").
    # Birleştirmeden önce her iki tarafı da açıkça string'e sabitliyoruz.
    for _df in (norm, baseline):
        for _col in ("StoreKey", "RoleKey"):
            if _col in _df.columns:
                _df[_col] = _df[_col].astype(str)
    detail = norm.merge(baseline, on=["StoreKey", "RoleKey"], how="outer")
    # Dış birleşmede isim alanlarını norm tablosundan alamayan satırlar için tamamla.
    store_names = {}
    role_names = {}
    for src in (norm,):
        for _, r in src.iterrows():
            store_names.setdefault(r["StoreKey"], r["Mağaza"])
            role_names.setdefault(r["RoleKey"], r["Unvan"])
    detail["Mağaza"] = detail["StoreKey"].map(store_names)
    detail["Unvan"] = detail["RoleKey"].map(role_names)
    for c in ("Norm",):
        detail[c] = pd.to_numeric(detail.get(c, 0), errors="coerce").fillna(0).astype(int)
    # Mağaza-bölge eşleştirmesi: önce Fact_Mevcut, sonra Fact_Norm.
    region_map = {}
    id_map = {}
    for source in (fm, sheets.get("Fact_Norm", pd.DataFrame())):
        if source.empty: continue
        for _, r in source.iterrows():
            sk = store_key(r.get("Mağaza"))
            reg = str(r.get("Bölge Sorumlusu") or "").strip()
            if sk and reg:  # DÜZELTME: sabit REGIONS listesi kaldırıldı — herhangi bir DOLU bölge adı kabul edilir (çok kiracılı).
                region_map.setdefault(sk, reg)
                id_map.setdefault(sk, r.get("MağazaID", ""))
    detail["Bölge Sorumlusu"] = detail["StoreKey"].map(region_map).fillna("")
    detail["MağazaID"] = detail["StoreKey"].map(id_map).fillna("")
    detail = detail[detail["Bölge Sorumlusu"].ne("")].copy()  # DÜZELTME: sabit REGIONS listesi yerine yalnız "bölgesi belirlenebilmiş" kontrolü

    # Personel isimleri departman esaslı eşleştirilir; görünen unvan ise
    # Fact_Mevcut'taki gerçek personel unvanıdır.
    people = fm.copy()
    people["StoreKey"] = people["Mağaza"].map(store_key)
    people["RoleKey"] = people.get("Departman", people.get("Unvan", "")).map(role_key)
    people["_Personel Detayı"] = people.apply(
        lambda r: f"{str(r.get('İsim Soyisim') or '').strip()} ({str(r.get('Unvan') or '').strip()})".strip(),
        axis=1,
    )
    names = people.groupby(["StoreKey","RoleKey"], dropna=False).agg(
        **{
            "Mevcut": ("İsim Soyisim", "count"),
            "Personel Adı Soyadı": ("İsim Soyisim", lambda s: ", ".join(dict.fromkeys(s.dropna().astype(str)))),
            "Gerçek Unvan / Personel": ("_Personel Detayı", lambda s: ", ".join(dict.fromkeys(v for v in s if v and v != "()"))),
            "Gerçek Unvanlar": ("Unvan", lambda s: ", ".join(dict.fromkeys(s.dropna().astype(str)))),
        }
    ).reset_index()
    # Norm tanımı olmayan çalışan da toplam aktif mevcutta ve personel
    # listelerinde görünür. Ancak EKSİK/FAZLA değeri yalnızca resmi kontrol
    # tablosundaki mağaza+departman sınıflamasından gelir.
    # SAVUNMA: detail/names birleştirmesinden önce StoreKey/RoleKey'i açıkça
    # string'e sabitle — biri boş/NaN ağırlıklı kalıp pandas tarafından
    # float64'e yükseltilirse (özellikle tamamı NaN olan bir grup varsa)
    # merge tip hatasıyla çöker; bu satır o senaryoyu kalıcı olarak önler.
    for _df in (detail, names):
        for _col in ("StoreKey", "RoleKey"):
            if _col in _df.columns:
                _df[_col] = _df[_col].astype(str)
    detail = detail.merge(names, on=["StoreKey","RoleKey"], how="outer")
    detail["Mağaza"] = detail["Mağaza"].fillna(detail["StoreKey"].map(
        people.drop_duplicates("StoreKey").set_index("StoreKey")["Mağaza"].to_dict()
    ))
    detail["Unvan"] = detail["Unvan"].fillna(detail["RoleKey"].map(DISPLAY_ROLE)).fillna(detail["RoleKey"])
    detail["Bölge Sorumlusu"] = detail["Bölge Sorumlusu"].fillna(detail["StoreKey"].map(region_map)).fillna("")
    detail["MağazaID"] = detail["MağazaID"].fillna(detail["StoreKey"].map(id_map)).fillna("")
    detail = detail[detail["Bölge Sorumlusu"].ne("")].copy()  # DÜZELTME: sabit REGIONS listesi yerine yalnız "bölgesi belirlenebilmiş" kontrolü
    for c in ("Norm","Eksik","Fazla","Mevcut"):
        if c in detail.columns:
            detail[c] = pd.to_numeric(detail.get(c, 0), errors="coerce").fillna(0).astype(int)
    for c in ("BaselineRaw", "BaselineEffective"):
        detail[c] = pd.to_numeric(detail.get(c, 0), errors="coerce").fillna(0).astype(int)
    has_baseline = detail["_HasBaseline"].eq(True)
    in_scope = detail["InScope"].eq(True) | detail["Norm"].gt(0)
    effective = pd.Series(0, index=detail.index, dtype=int)
    effective.loc[has_baseline] = (
        detail.loc[has_baseline, "BaselineEffective"]
        + detail.loc[has_baseline, "Mevcut"]
        - detail.loc[has_baseline, "BaselineRaw"]
    ).clip(lower=0).astype(int)
    effective.loc[~has_baseline & in_scope] = detail.loc[~has_baseline & in_scope, "Mevcut"]
    detail["Eksik"] = (detail["Norm"] - effective).clip(lower=0).astype(int)
    detail["Fazla"] = (effective - detail["Norm"]).clip(lower=0).astype(int)
    for c in ("Personel Adı Soyadı", "Gerçek Unvan / Personel", "Gerçek Unvanlar"):
        detail[c] = detail[c].fillna("")
    detail["UnvanID"] = detail["RoleKey"]

    stores = detail.groupby(["Bölge Sorumlusu","MağazaID","Mağaza"], dropna=False)[["Mevcut","Norm","Eksik","Fazla"]].sum().reset_index()
    stores = stores.dropna(subset=["Bölge Sorumlusu","Mağaza"]).copy()
    stores = stores[(stores["Bölge Sorumlusu"].astype(str).str.strip() != "") & (stores["Mağaza"].astype(str).str.strip() != "")]

    kpis = {
        "Aktif Mevcut": int(len(fm)),
        "Toplam Norm": int(detail["Norm"].sum()),
        "Norm Eksiği": int(detail["Eksik"].sum()),
        "Norm Fazlası": int(detail["Fazla"].sum()),
    }
    kpis["Net İhtiyaç"] = kpis["Norm Fazlası"] - kpis["Norm Eksiği"]
    return fm, detail, stores, kpis

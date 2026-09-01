from __future__ import annotations

"""Mağaza satış sapmasını mevcut operasyon ve iş gücü kanıtlarıyla açıklar.

Hesaplar UI'dan bağımsız tutulur; Streamlit ve diğer sunucu tüketicileri aynı
mağaza/dönem eşleşmesini kullanabilir. Ana norm veya AI motoruna dokunmaz.
"""

from typing import Any

import pandas as pd


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def _period(frame: pd.DataFrame) -> pd.Series:
    for name in ("Ay", "Dönem", "Donem", "Tarih"):
        if name in frame.columns:
            return frame[name].astype(str).str[:7]
    return pd.Series("", index=frame.index, dtype="object")


def _store_key(frame: pd.DataFrame) -> pd.Series:
    for name in ("MagazaID", "MağazaID", "Mağaza", "Magaza"):
        if name in frame.columns:
            return frame[name].fillna("").astype(str).str.strip()
    return pd.Series("", index=frame.index, dtype="object")


def _indexed(frame: pd.DataFrame | None, period: str = "") -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    view = frame.copy()
    periods = _period(view)
    if period:
        view = view[periods.eq("") | periods.eq(period)].copy()
    view["_store_key"] = _store_key(view)
    return view.drop_duplicates("_store_key", keep="last").set_index("_store_key")


def _value(frame: pd.DataFrame, key: str, *columns: str) -> float | None:
    if frame.empty or key not in frame.index:
        return None
    row = frame.loc[key]
    for column in columns:
        if column in frame.columns:
            return _number(row.get(column))
    return None


def _change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1) * 100


def _diagnose(row: dict[str, Any]) -> tuple[str, str, str]:
    sales_rate, norm_rate = row.get("Hedef Gerçekleşme %"), row.get("Norm Karşılama %")
    if sales_rate is None:
        return "VERİ EKSİK", "Belirsiz", "Satış hedefi ve gerçekleşen dönem verisini tamamla."
    if sales_rate >= 100 and norm_rate < 95:
        return "EKSİK KADROYLA HEDEF ÜSTÜ", "Desteklenmiyor", "Mesai ve çalışan yükü sürdürülebilirliğini incele."
    if sales_rate >= 100:
        return "HEDEF TUTTU", "Desteklenmiyor", "Fire ve iş yükü göstergelerini koruma sınırı olarak izle."
    if norm_rate >= 98:
        return "TAM KADRO / DÜŞÜK SATIŞ", "Desteklenmiyor", "Fiş, sepet, fire ve mağaza yönetimi açıklaması iste."
    if (row.get("Fiş Değişim %") or 0) < -3 and (row.get("Sepet Değişim %") or 0) >= -3:
        return "MÜŞTERİ TRAFİĞİ DÜŞÜŞÜ", "Desteklenmiyor", "Trafik, kampanya, rekabet ve mağaza çekiciliğini açıkla."
    if (row.get("Sepet Değişim %") or 0) < -3:
        return "ORTALAMA SEPET DÜŞÜŞÜ", "Desteklenmiyor", "Ürün karması, fiyat, kampanya ve stok bulunurluğunu açıkla."
    people_evidence = norm_rate < 95 and (
        (row.get("Fazla Mesai Saat") or 0) > 0
        or (row.get("Kayıp FTE") or 0) > 0
        or (row.get("İş Yükü Endeksi") or 0) >= 70
    )
    if people_evidence:
        return "PERSONEL ETKİSİ KANITLI", "Kanıtlı", "Eksik unvan/saat ile satış kaybı bağlantısını ve telafi planını kaydet."
    return "KÖK NEDEN AÇIKLANMADI", "Belirsiz", "Fiş, sepet, stok, kategori ve yönetici kırılımıyla kanıt sun."


def build_sales_root_cause(
    *, sheets: dict[str, pd.DataFrame], stores: pd.DataFrame,
    targets: list[dict[str, Any]] | pd.DataFrame, inflation_pct: float = 32.11,
) -> tuple[pd.DataFrame, str, str]:
    operations = sheets.get("Aylık Operasyon KPI", sheets.get("Aylik Operasyon KPI", pd.DataFrame())).copy()
    if operations.empty or stores.empty:
        return pd.DataFrame(), "", ""
    periods = sorted(p for p in _period(operations).dropna().unique().tolist() if p)
    latest, previous = (periods[-1] if periods else ""), (periods[-2] if len(periods) > 1 else "")
    current, prior = _indexed(operations, latest), _indexed(operations, previous)
    overtime = _indexed(sheets.get("Fazla Mesai"), latest)
    absence = _indexed(sheets.get("Devamsızlık"), latest)
    workload = _indexed(sheets.get("İş Yükü Endeksi", sheets.get("Is Yuku Endeksi")))
    waste = _indexed(sheets.get("Fire ve İade", sheets.get("Fire ve Iade")), latest)
    performance = _indexed(sheets.get("Performans"), latest)
    # DÜZELTME: Satış hedefi ARTIK ÖNCELİKLE Excel'deki "Satış Hedefi" sayfasından
    # okunuyor (Ay, MagazaID, Hedef Ciro sütunları) — çünkü gerçek kullanım akışı
    # "Excel yükle -> Railway motoru hesaplar" şeklinde, Vercel'de ayrıca elle hedef
    # girilmesini beklemek bu akışla uyuşmuyordu. Vercel/Supabase girişi (varsa)
    # yalnız Excel'de o mağaza/ay için değer YOKSA yedek olarak kullanılır; açıklama/
    # aksiyon planı/sorumlu alanları hâlâ yalnız Vercel'den gelir (Excel'de karşılığı yok).
    excel_targets = _indexed(
        sheets.get("Satış Hedefi", sheets.get("Satis Hedefi", sheets.get("Satış Hedefi ", pd.DataFrame()))),
        latest,
    )
    target_frame = pd.DataFrame(targets)
    if not target_frame.empty:
        target_frame = target_frame[target_frame.get("period", "").astype(str).eq(latest)].copy()
        target_frame["_store_key"] = target_frame.get("store_id", "").astype(str).str.strip()
        target_frame = target_frame.drop_duplicates("_store_key", keep="last").set_index("_store_key")

    rows: list[dict[str, Any]] = []
    for _, store in stores.iterrows():
        store_id = str(store.get("MağazaID") or store.get("Mağaza") or "").strip()
        store_name = str(store.get("Mağaza") or store_id).strip()
        source_key = store_id if store_id in current.index else store_name
        target_key = store_id if not target_frame.empty and store_id in target_frame.index else store_name
        revenue = _value(current, source_key, "Aylık Ciro", "Ciro")
        tickets = _value(current, source_key, "Aylık Fiş", "Fiş Adedi")
        basket = _value(current, source_key, "Ort. Sepet", "Ortalama Sepet")
        revenue_change = _change(revenue, _value(prior, source_key, "Aylık Ciro", "Ciro"))
        excel_key = store_id if store_id in excel_targets.index else store_name
        target = _value(excel_targets, excel_key, "Hedef Ciro", "Satış Hedefi")
        if target is None:
            target = _value(target_frame, target_key, "sales_target")
        norm = _number(store.get("Norm", store.get("Norm Kadro"))) or 0
        current_staff = _number(store.get("Mevcut", store.get("Aktif Mevcut"))) or 0
        row = {
            "MağazaID": store_id, "Mağaza": store_name,
            "Norm": int(norm), "Mevcut": int(current_staff),
            "Norm Karşılama %": current_staff / norm * 100 if norm else 0,
            "Satış Hedefi": target, "Gerçekleşen Ciro": revenue,
            "Hedef Gerçekleşme %": revenue / target * 100 if revenue is not None and target not in (None, 0) else None,
            "Fiş Değişim %": _change(tickets, _value(prior, source_key, "Aylık Fiş", "Fiş Adedi")),
            "Sepet Değişim %": _change(basket, _value(prior, source_key, "Ort. Sepet", "Ortalama Sepet")),
            "Reel Büyüme %": ((1 + revenue_change / 100) / (1 + inflation_pct / 100) - 1) * 100 if revenue_change is not None else None,
            "Fazla Mesai Saat": _value(overtime, source_key, "Fazla Mesai Saat"),
            "Kayıp FTE": _value(absence, source_key, "Fiili Kayıp FTE"),
            "İş Yükü Endeksi": _value(workload, source_key, "İş Yükü Endeksi"),
            "Fire Oranı %": _value(waste, source_key, "Fire Oranı %"),
            "Yönetici Puanı": _value(performance, source_key, "Yönetici Puanı"),
            "Satış Açıklaması": target_frame.loc[target_key].get("explanation") if not target_frame.empty and target_key in target_frame.index else None,
            "Aksiyon Planı": target_frame.loc[target_key].get("action_plan") if not target_frame.empty and target_key in target_frame.index else None,
            "Sorumlu": target_frame.loc[target_key].get("owner_name") if not target_frame.empty and target_key in target_frame.index else None,
        }
        row["Otomatik Kök Neden"], row["Personel İddiası"], row["İstenen Aksiyon"] = _diagnose(row)
        rows.append(row)
    return pd.DataFrame(rows), latest, previous

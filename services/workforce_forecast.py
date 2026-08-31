from __future__ import annotations

"""Mağaza + unvan düzeyinde açıklanabilir iş gücü talep tahmini.

Bu modül resmî Yönetim Normu'nu değiştirmez. 30/60/90 günlük karar destek
çıktısı üretir. Tahmin; aktivite iş yükü, operasyon eğilimi, kapasite,
fazla mesai, devamsızlık/izin, sezon-kampanya, özel gün ve turnover
girdilerini ayrı ayrı gösterir.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import unicodedata

import numpy as np
import pandas as pd

OUTPUT_FILE_NAME = "OMEHR_Magaza_Unvan_Isgucu_Tahmini.xlsx"
FORECAST_MODE = "decision_support_only"
MAXIMUM_NORM_EFFECT = 0.0
MAXIMUM_TRANSFER_EFFECT = 0.0


def _norm(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _find_col(df: pd.DataFrame, *tokens: str) -> str | None:
    normalized = {c: _norm(c) for c in df.columns}
    wanted = [_norm(t) for t in tokens]
    for c, n in normalized.items():
        if all(t in n for t in wanted):
            return c
    return None


def _clean_titled_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Başlığın ilk satırda dekoratif başlıktan sonra geldiği sayfaları düzeltir."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # pd.read_excel(header=0) sonucunda sütunların çoğu Unnamed ise ilk veri satırı gerçek başlıktır.
    unnamed_ratio = sum(str(c).startswith("Unnamed") for c in out.columns) / max(1, len(out.columns))
    if unnamed_ratio >= 0.4 and len(out):
        header = out.iloc[0].tolist()
        out = out.iloc[1:].copy()
        out.columns = [str(v).strip() if pd.notna(v) else f"Kolon_{i+1}" for i, v in enumerate(header)]
    return out.dropna(how="all").reset_index(drop=True)


def _sheet(sheets: dict[str, pd.DataFrame], *names: str) -> pd.DataFrame:
    for name in names:
        if name in sheets:
            return _clean_titled_sheet(sheets[name])
    norm_map = {_norm(k): k for k in sheets}
    for name in names:
        hit = norm_map.get(_norm(name))
        if hit:
            return _clean_titled_sheet(sheets[hit])
    return pd.DataFrame()


def _number(series: pd.Series | Any, default: float = 0.0) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce").fillna(default)
    return pd.Series(dtype=float)


def _parameter_map(sheets: dict[str, pd.DataFrame]) -> dict[str, float]:
    params = {
        "Son 30 Gün Ağırlığı": 0.50,
        "Son 60 Gün Ağırlığı": 0.30,
        "Son 90 Gün Ağırlığı": 0.20,
        "Beklenen Turnover Oranı": 0.08,
        "Sezon Katsayısı": 1.00,
        "Kampanya Katsayısı": 1.00,
        "Yeni Mağaza Etkisi": 1.00,
        "Fazla Mesai Tampon Üst Sınırı": 0.15,
        "Kayıp Kapasite Tampon Üst Sınırı": 0.20,
        "Operasyon Trend Alt Sınırı": -0.15,
        "Operasyon Trend Üst Sınırı": 0.20,
        "Tahmin Güven Alt Sınırı": 0.35,
    }
    for name in ("Tahmin_Parametreleri", "Isgucu_Tahmin_Parametreleri"):
        df = _sheet(sheets, name)
        if df.empty:
            continue
        pcol = _find_col(df, "parametre")
        vcol = _find_col(df, "deger")
        if not pcol or not vcol:
            continue
        for _, row in df.iterrows():
            key = str(row.get(pcol, "")).strip()
            val = pd.to_numeric(row.get(vcol), errors="coerce")
            if key and pd.notna(val):
                params[key] = float(val)
    return params


def _store_trends(sheets: dict[str, pd.DataFrame], params: dict[str, float]) -> pd.DataFrame:
    op = _sheet(sheets, "Aylık Operasyon KPI", "Operasyon", "Fact_Operasyon", "Operasyon_KPI", "Günlük Operasyon")
    if op.empty:
        return pd.DataFrame(columns=["MağazaID", "Operasyon Trend", "Operasyon Gözlem", "Operasyon Veri Kalitesi"])
    sid = _find_col(op, "magaza", "id")
    date = _find_col(op, "ay") or _find_col(op, "tarih") or _find_col(op, "donem")
    revenue = _find_col(op, "ciro")
    tickets = _find_col(op, "fis")
    online = _find_col(op, "online", "siparis")
    if not sid or not date or (not revenue and not tickets):
        return pd.DataFrame(columns=["MağazaID", "Operasyon Trend", "Operasyon Gözlem", "Operasyon Veri Kalitesi"])
    x = op.copy()
    x[date] = pd.to_datetime(x[date], errors="coerce")
    metrics = [c for c in (revenue, tickets, online) if c]
    for c in metrics:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna(subset=[sid, date])
    rows = []
    lo = params["Operasyon Trend Alt Sınırı"]
    hi = params["Operasyon Trend Üst Sınırı"]
    for store, g in x.groupby(sid):
        g = g.sort_values(date)
        metric_trends = []
        for c in metrics:
            s = g.set_index(date)[c].dropna().resample("MS").sum().tail(12)
            if len(s) >= 4 and s.iloc[:-1].mean() != 0:
                # sağlamlaştırılmış kısa/uzun dönem oranı
                recent = s.tail(3).mean()
                base = s.iloc[:-3].tail(6).mean() if len(s) >= 7 else s.head(max(1, len(s)-3)).mean()
                if base and np.isfinite(base):
                    metric_trends.append(float(recent / base - 1))
        trend = float(np.nanmedian(metric_trends)) if metric_trends else 0.0
        trend = max(lo, min(hi, trend))
        obs = int(len(g))
        quality = "Yüksek" if obs >= 12 and len(metric_trends) >= 2 else "Orta" if obs >= 6 else "Düşük"
        rows.append({"MağazaID": str(store), "Operasyon Trend": trend, "Operasyon Gözlem": obs, "Operasyon Veri Kalitesi": quality})
    return pd.DataFrame(rows)


def _store_buffers(sheets: dict[str, pd.DataFrame], current_by_store: pd.Series, params: dict[str, float]) -> pd.DataFrame:
    stores = pd.DataFrame({"MağazaID": current_by_store.index.astype(str), "Aktif Mevcut Mağaza": current_by_store.values})
    stores["Fazla Mesai Tamponu"] = 0.0
    stores["Kayıp Kapasite Tamponu"] = 0.0

    overtime = _sheet(sheets, "Fazla Mesai")
    if not overtime.empty:
        sid = _find_col(overtime, "magaza", "id")
        hours = _find_col(overtime, "fazla", "mesai", "saat")
        if sid and hours:
            tmp = overtime.assign(_hours=_number(overtime[hours]))
            month = _find_col(tmp, "ay") or _find_col(tmp, "tarih") or _find_col(tmp, "donem")
            person = _find_col(tmp, "personel", "id")
            # Personel satırları varsa önce mağaza-ay toplamı alınır; mağaza-ay
            # toplamı hazır geliyorsa doğrudan kullanılır. Sonra son aylardaki
            # ortalama aylık toplam hesaplanır. Böylece kişi bazlı kayıtlar
            # yanlışlıkla ortalamaya düşürülmez.
            if month:
                tmp[month] = pd.to_datetime(tmp[month], errors="coerce")
                monthly = tmp.groupby([sid, month], as_index=False)["_hours"].sum()
                monthly = monthly.sort_values(month).groupby(sid, as_index=False).tail(6)
                o = monthly.groupby(sid, as_index=False)["_hours"].mean()
            elif person:
                o = tmp.groupby(sid, as_index=False)["_hours"].sum()
            else:
                o = tmp.groupby(sid, as_index=False)["_hours"].mean()
            # 180 saat / kişi / ay üzerinden FTE'ye çevir. Üst sınır mağaza
            # mevcut kadrosunun belirlenen oranıdır.
            o["Fazla Mesai Tamponu"] = o["_hours"] / 180.0
            stores = stores.merge(o[[sid, "Fazla Mesai Tamponu"]].rename(columns={sid:"MağazaID"}), on="MağazaID", how="left", suffixes=("", "_y"))
            stores["Fazla Mesai Tamponu"] = stores.pop("Fazla Mesai Tamponu_y").fillna(stores["Fazla Mesai Tamponu"])
            fm_cap = stores["Aktif Mevcut Mağaza"] * params["Fazla Mesai Tampon Üst Sınırı"]
            stores["Fazla Mesai Tamponu"] = stores["Fazla Mesai Tamponu"].clip(lower=0, upper=fm_cap)

    absence = _sheet(sheets, "Devamsızlık")
    leave = _sheet(sheets, "İzin")
    losses = []
    if not absence.empty:
        sid = _find_col(absence, "magaza", "id")
        fte = _find_col(absence, "fiili", "kayip", "fte")
        if sid and fte:
            losses.append(absence.assign(_loss=_number(absence[fte])).groupby(sid)["_loss"].mean())
    if not leave.empty:
        sid = _find_col(leave, "magaza", "id")
        day_cols = [c for c in leave.columns if "IZIN" in _norm(c) and "GUN" in _norm(c)]
        if sid and day_cols:
            tmp = leave.copy()
            tmp["_loss"] = sum((_number(tmp[c]) for c in day_cols), start=pd.Series(0.0, index=tmp.index)) / 30.0
            losses.append(tmp.groupby(sid)["_loss"].mean())
    if losses:
        combined = pd.concat(losses, axis=1).fillna(0).sum(axis=1).rename("Kayıp Kapasite Tamponu")
        stores = stores.merge(combined, left_on="MağazaID", right_index=True, how="left", suffixes=("", "_y"))
        stores["Kayıp Kapasite Tamponu"] = stores.pop("Kayıp Kapasite Tamponu_y").fillna(stores["Kayıp Kapasite Tamponu"])
    cap = stores["Aktif Mevcut Mağaza"] * params["Kayıp Kapasite Tampon Üst Sınırı"]
    stores["Kayıp Kapasite Tamponu"] = stores["Kayıp Kapasite Tamponu"].clip(lower=0, upper=cap)
    return stores


def _turnover_rates(staff: pd.DataFrame, sid: str, tid: str, params: dict[str, float], as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Mağaza-unvan-kıdem bazlı beklenen turnover oranı üretir.

    Son 180 günlük çıkışlar, aynı dönemde risk altında bulunan girişler ile
    oranlanır. Küçük örneklemlerde oran şirket geneline doğru yumuşatılır
    (empirical-Bayes shrinkage). Veri yetersizse parametre varsayımına döner.

    as_of: verilirse (geriye dönük doğrulama/backtest amaçlı), "bugün" yerine
    bu tarih referans alınır VE bu tarihten SONRAKİ çıkış kayıtları hesaba
    katılmadan önce bilinmiyormuş gibi maskelenir — aksi halde backtest,
    henüz gerçekleşmemiş (gelecekteki) çıkışları "biliyormuş" gibi kullanıp
    yapay olarak isabetli görünürdü (bakış-ileri sızıntısı/look-ahead leak).
    Canlı tahmin akışı (as_of=None) davranışı BİREBİR AYNI kalır.
    """
    entry = _find_col(staff, "ise", "giris")
    exit_col = _find_col(staff, "isten", "cikis")
    if not entry or not exit_col:
        keys = staff[[sid, tid]].drop_duplicates().copy()
        keys["Beklenen Turnover Oranı (90G)"] = params["Beklenen Turnover Oranı"]
        keys["Turnover Veri Durumu"] = "Varsayılan - tarih alanı eksik"
        return keys
    x = staff.copy()
    x[entry] = pd.to_datetime(x[entry], errors="coerce")
    x[exit_col] = pd.to_datetime(x[exit_col], errors="coerce")
    if as_of is not None:
        x.loc[x[exit_col] > as_of, exit_col] = pd.NaT
        reference = as_of
    else:
        reference = max([d for d in [x[entry].max(), x[exit_col].max(), pd.Timestamp.today().normalize()] if pd.notna(d)])
    start = reference - pd.Timedelta(days=180)
    x["_tenure_days"] = (x[exit_col].fillna(reference) - x[entry]).dt.days.clip(lower=0)
    x["_tenure_group"] = np.where(x["_tenure_days"] <= 90, "İlk 90 Gün", "90 Gün Üzeri")
    x["_at_risk"] = ((x[entry].notna()) & (x[entry] <= reference) & (x[exit_col].isna() | (x[exit_col] >= start))).astype(int)
    x["_exit180"] = ((x[exit_col] >= start) & (x[exit_col] <= reference)).astype(int)
    global_risk = max(1, int(x["_at_risk"].sum()))
    global_rate_180 = float(x["_exit180"].sum() / global_risk)
    default_180 = max(0.0, min(0.60, params["Beklenen Turnover Oranı"] * 2.0))
    prior_rate = global_rate_180 if global_risk >= 30 else default_180
    rows=[]
    for (store,title), g in x.groupby([sid,tid], dropna=False):
        risk = int(g["_at_risk"].sum())
        exits = int(g["_exit180"].sum())
        raw = exits / risk if risk else prior_rate
        # 20 kişilik eşdeğer öncül: küçük mağaza/unvan gruplarını stabilize eder.
        shrunk180 = (exits + prior_rate * 20.0) / (risk + 20.0)
        rate90 = max(0.0, min(0.35, shrunk180 / 2.0))
        early = g[g["_tenure_group"] == "İlk 90 Gün"]
        early_risk = int(early["_at_risk"].sum())
        early_exit = int(early["_exit180"].sum())
        early_rate = (early_exit / early_risk / 2.0) if early_risk else rate90
        rows.append({sid:store, tid:title, "Beklenen Turnover Oranı (90G)":rate90,
                     "İlk 90 Gün Turnover Oranı":max(0.0,min(0.60,early_rate)),
                     "Turnover Risk Altındaki Kişi":risk, "Turnover Çıkış Gözlemi":exits,
                     "Turnover Veri Durumu":"Yüksek" if risk>=30 else "Orta" if risk>=10 else "Düşük"})
    return pd.DataFrame(rows)


def _calendar_multiplier(sheets: dict[str, pd.DataFrame], horizon_days: int) -> tuple[float, str]:
    cal = _sheet(sheets, "Tahmin_Takvimi", "Ozel_Gun_Takvimi")
    if cal.empty:
        return 1.0, "Takvim girdisi yok"
    active = _find_col(cal, "aktif")
    coeff = _find_col(cal, "katsayi")
    horizon = _find_col(cal, "ufuk", "gun")
    if not coeff:
        return 1.0, "Katsayı sütunu yok"
    x = cal.copy()
    if active:
        x = x[x[active].astype(str).map(_norm).isin({"EVET","E","YES","1","TRUE","AKTIF"})]
    if horizon:
        h = pd.to_numeric(x[horizon], errors="coerce")
        x = x[h.isna() | (h <= horizon_days)]
    vals = pd.to_numeric(x[coeff], errors="coerce").dropna()
    if vals.empty:
        return 1.0, "Aktif katsayı yok"
    # etkiler çarpan olarak birikir, aşırı değerler sınırlandırılır
    mult = float(np.prod(vals.clip(0.80, 1.25)))
    return max(0.80, min(1.35, mult)), f"{len(vals)} aktif takvim etkisi"


def run(sheets: dict[str, pd.DataFrame], outdir: Path) -> dict[str, Any]:
    params = _parameter_map(sheets)
    activity = _sheet(sheets, "Gunluk_Aktivite_Hacmi")
    capacity = _sheet(sheets, "Kapasite_Parametreleri")
    norm = _sheet(sheets, "Fact_Norm")
    staff = _sheet(sheets, "Fact_Mevcut")
    minimums = _sheet(sheets, "Minimum_Kadro_Kurallari")

    required = {"Gunluk_Aktivite_Hacmi": activity, "Kapasite_Parametreleri": capacity, "Fact_Norm": norm, "Fact_Mevcut": staff}
    missing = [name for name, frame in required.items() if frame.empty]
    if missing:
        return {"status":"SKIPPED", "reason":"Zorunlu sayfa eksik", "missing":missing}

    # Kolonlar
    a_sid = _find_col(activity, "magaza", "id")
    a_store = next((c for c in activity.columns if "MAGAZA" in _norm(c) and "ID" not in _norm(c)), None)
    a_tid = _find_col(activity, "unvan", "id")
    a_title = next((c for c in activity.columns if "UNVAN" in _norm(c) and "ID" not in _norm(c)), None)
    a_work = _find_col(activity, "is", "yuku", "dk"); a_date = _find_col(activity, "tarih")
    c_tid = _find_col(capacity, "unvan", "id"); c_net = _find_col(capacity, "net", "uretken", "dakika")
    n_sid = _find_col(norm, "magaza", "id"); n_tid = _find_col(norm, "unvan", "id"); n_val = _find_col(norm, "norm", "kadro")
    s_sid = _find_col(staff, "magaza", "id"); s_tid = _find_col(staff, "unvan", "id"); s_exit = _find_col(staff, "isten", "cikis")
    if not all([a_sid, a_tid, a_work, c_tid, c_net, n_sid, n_tid, n_val, s_sid, s_tid]):
        return {"status":"SKIPPED", "reason":"Tahmin için zorunlu kolonlardan biri bulunamadı"}

    act = activity.copy()
    act[a_work] = pd.to_numeric(act[a_work], errors="coerce").fillna(0)
    if a_date:
        act[a_date] = pd.to_datetime(act[a_date], errors="coerce")
    recent = act
    if a_date and act[a_date].notna().any():
        max_date = act[a_date].max()
        recent = act[act[a_date] >= max_date - pd.Timedelta(days=89)].copy()
    base = recent.groupby([a_sid, a_tid], as_index=False).agg(
        **{"Günlük İş Yükü Dk":(a_work,"mean"), "Aktivite Gözlem":(a_work,"count")}
    )
    names = act[[a_sid, a_tid] + ([a_store] if a_store and a_store not in (a_sid,a_tid) else []) + ([a_title] if a_title and a_title not in (a_sid,a_tid,a_store) else [])].drop_duplicates([a_sid,a_tid])
    base = base.merge(names, on=[a_sid,a_tid], how="left")
    cap = capacity[[c_tid,c_net]].copy(); cap[c_net] = pd.to_numeric(cap[c_net], errors="coerce")
    base = base.merge(cap.rename(columns={c_tid:a_tid}), on=a_tid, how="left")
    base["Ham İş Yükü FTE"] = base["Günlük İş Yükü Dk"] / base[c_net].replace(0,np.nan)

    norm2 = norm.groupby([n_sid,n_tid], as_index=False)[n_val].sum().rename(columns={n_sid:a_sid,n_tid:a_tid,n_val:"Yönetim Normu"})
    base = base.merge(norm2, on=[a_sid,a_tid], how="outer")
    base["Günlük İş Yükü Dk"] = base["Günlük İş Yükü Dk"].fillna(0)
    base["Ham İş Yükü FTE"] = base["Ham İş Yükü FTE"].fillna(base["Yönetim Normu"])
    base["Yönetim Normu"] = pd.to_numeric(base["Yönetim Normu"], errors="coerce").fillna(0)

    active = staff.copy()
    if s_exit:
        active = active[active[s_exit].isna() | active[s_exit].astype(str).str.strip().isin(["","NaT","nan","None"])]
    current = active.groupby([s_sid,s_tid]).size().rename("Aktif Mevcut").reset_index().rename(columns={s_sid:a_sid,s_tid:a_tid})
    base = base.merge(current, on=[a_sid,a_tid], how="outer")
    base["Aktif Mevcut"] = base["Aktif Mevcut"].fillna(0)
    base["Yönetim Normu"] = pd.to_numeric(base.get("Yönetim Normu",0), errors="coerce").fillna(0)
    base["Günlük İş Yükü Dk"] = pd.to_numeric(base.get("Günlük İş Yükü Dk",0), errors="coerce").fillna(0)
    base["Ham İş Yükü FTE"] = pd.to_numeric(base.get("Ham İş Yükü FTE",0), errors="coerce").fillna(base["Yönetim Normu"])

    # Minimum kadro
    if not minimums.empty:
        m_tid = _find_col(minimums,"unvan","id"); m_min = _find_col(minimums,"minimum","kisi")
        if m_tid and m_min:
            base = base.merge(minimums[[m_tid,m_min]].rename(columns={m_tid:a_tid,m_min:"Minimum Kadro"}), on=a_tid, how="left")
    if "Minimum Kadro" not in base:
        base["Minimum Kadro"] = 0
    base["Minimum Kadro"] = pd.to_numeric(base["Minimum Kadro"], errors="coerce").fillna(0)

    store_current = active.groupby(s_sid).size()
    trends = _store_trends(sheets, params)
    buffers = _store_buffers(sheets, store_current, params)
    base[a_sid] = base[a_sid].astype(str)
    base = base.merge(trends.rename(columns={"MağazaID":a_sid}), on=a_sid, how="left")
    base = base.merge(buffers.rename(columns={"MağazaID":a_sid}), on=a_sid, how="left")
    turnover = _turnover_rates(staff, s_sid, s_tid, params).rename(columns={s_sid:a_sid, s_tid:a_tid})
    base = base.merge(turnover, on=[a_sid,a_tid], how="left")
    base["Operasyon Trend"] = base["Operasyon Trend"].fillna(0)
    base["Fazla Mesai Tamponu"] = base["Fazla Mesai Tamponu"].fillna(0)
    base["Kayıp Kapasite Tamponu"] = base["Kayıp Kapasite Tamponu"].fillna(0)
    turnover_base = base["Beklenen Turnover Oranı (90G)"] if "Beklenen Turnover Oranı (90G)" in base.columns else pd.Series(params["Beklenen Turnover Oranı"], index=base.index)
    base["Beklenen Turnover Oranı (90G)"] = pd.to_numeric(turnover_base, errors="coerce").fillna(params["Beklenen Turnover Oranı"])
    early_turnover = base["İlk 90 Gün Turnover Oranı"] if "İlk 90 Gün Turnover Oranı" in base.columns else pd.Series(np.nan, index=base.index)
    base["İlk 90 Gün Turnover Oranı"] = pd.to_numeric(early_turnover, errors="coerce").fillna(base["Beklenen Turnover Oranı (90G)"])
    base["Turnover Veri Durumu"] = base.get("Turnover Veri Durumu", pd.Series("Varsayılan", index=base.index)).fillna("Varsayılan")

    # Mağaza tamponlarını unvanın mevcut payına dağıt
    store_total = base.groupby(a_sid)["Aktif Mevcut"].transform("sum").replace(0,np.nan)
    share = (base["Aktif Mevcut"] / store_total).fillna(0)
    base["FM Tampon FTE"] = base["Fazla Mesai Tamponu"] * share
    base["Kayıp Kapasite FTE"] = base["Kayıp Kapasite Tamponu"] * share

    horizon_frames=[]
    for horizon in (30,60,90):
        h = base.copy()
        calendar_mult, calendar_note = _calendar_multiplier(sheets, horizon)
        trend_mult = (1 + h["Operasyon Trend"] * horizon / 90.0).clip(0.80,1.30)
        global_mult = params["Sezon Katsayısı"] * params["Kampanya Katsayısı"] * params["Yeni Mağaza Etkisi"] * calendar_mult
        h["Tahmin Ufku Gün"] = horizon
        h["Operasyon Çarpanı"] = trend_mult
        h["Takvim/Sezon Çarpanı"] = global_mult
        h["Tahmini İş Yükü FTE (Saf)"] = h["Ham İş Yükü FTE"] * trend_mult * global_mult
        # Saha süreleri henüz doğrulanmamış olabileceği için iş yükü tahmini resmî
        # yönetim normuna en fazla %35 ağırlıkla bağlanır; tek başına kadroyu ikiye
        # katlamasına izin verilmez. Normu olmayan yeni kombinasyonlarda saf FTE kullanılır.
        activity_weight = np.minimum(pd.to_numeric(h.get("Aktivite Gözlem",0),errors="coerce").fillna(0)/20, 1) * 0.35
        workload_capped = np.where(h["Yönetim Normu"]>0,
                                   np.minimum(h["Tahmini İş Yükü FTE (Saf)"], h["Yönetim Normu"]*1.20),
                                   h["Tahmini İş Yükü FTE (Saf)"])
        h["İş Yükü Ağırlığı"] = activity_weight
        h["Tahmini İş Yükü FTE"] = np.where(
            h["Yönetim Normu"]>0,
            h["Yönetim Normu"]*(1-activity_weight) + workload_capped*activity_weight,
            workload_capped
        )
        # Varsayılan turnover oranı gerçek mağaza–unvan gözlemine dayanmıyorsa
        # yayımlanan kadro ihtiyacına doğrudan eklenmez; yalnız senaryo bilgisidir.
        turnover_observed = h["Turnover Veri Durumu"].isin(["Yüksek", "Orta", "Düşük"])
        h["Turnover Riski FTE (Senaryo)"] = h["Aktif Mevcut"] * h["Beklenen Turnover Oranı (90G)"] * horizon / 90.0
        h["Turnover Riski FTE"] = h["Turnover Riski FTE (Senaryo)"].where(turnover_observed, 0.0)
        # Fazla mesai ve kayıp kapasite çoğu durumda aynı kapasite açığının iki
        # farklı belirtisidir. Çifte sayımı önlemek için toplam yerine büyük olan
        # tampon yayımlanan tahmine eklenir; iki ham bileşen ayrıca görünür kalır.
        h["Operasyon Tampon FTE"] = pd.concat([h["FM Tampon FTE"], h["Kayıp Kapasite FTE"]], axis=1).max(axis=1)
        h["Tahmini Gerekli Kadro (Ham)"] = h["Tahmini İş Yükü FTE"] + h["Operasyon Tampon FTE"] + h["Turnover Riski FTE"]
        # DÜZELTME: "Tahmini Gerekli Kadro (Ham)" birçok np.where/aritmetik
        # zincirinden üretiliyor; girdilerden biri (ör. Beklenen Turnover
        # Oranı, Aktif Mevcut) sayısal olmayan/karışık bir dtype taşırsa
        # bu iki sütunun .max(axis=1) sonucu OBJECT dtype olabiliyor —
        # np.rint() bunu işleyemiyor ("'float' object has no attribute
        # 'rint'", gerçek testte yakalandı). "Minimum Kadro" için zaten
        # yapılan pd.to_numeric coerce'u burada da uygulanır.
        _gerekli_ham = pd.to_numeric(h["Tahmini Gerekli Kadro (Ham)"], errors="coerce").fillna(0)
        _minimum_kadro = pd.to_numeric(h["Minimum Kadro"], errors="coerce").fillna(0)
        h["Tahmini Gerekli Kadro"] = np.rint(pd.concat([_gerekli_ham, _minimum_kadro], axis=1).max(axis=1)).astype(int)
        h["Yuvarlama Etkisi Kişi"] = h["Tahmini Gerekli Kadro"] - pd.concat([_gerekli_ham, _minimum_kadro], axis=1).max(axis=1)
        h["Tahmini Açık/Fazla"] = h["Tahmini Gerekli Kadro"] - h["Aktif Mevcut"].astype(int)
        h["Yönetim Normundan Fark"] = h["Tahmini Gerekli Kadro"] - h["Yönetim Normu"].astype(int)
        h["Takvim Açıklaması"] = calendar_note
        # Güven: aktivite gözlemi, operasyon geçmişi, kapasite ve veri durumuna göre
        obs_score = np.minimum(pd.to_numeric(h.get("Aktivite Gözlem",0),errors="coerce").fillna(0)/20,1)
        op_score = np.minimum(pd.to_numeric(h.get("Operasyon Gözlem",0),errors="coerce").fillna(0)/12,1)
        cap_score = h[c_net].notna().astype(float)
        turnover_score = h["Turnover Veri Durumu"].map({"Yüksek":1.0,"Orta":0.7,"Düşük":0.4,"Varsayılan":0.2}).fillna(0.2)
        h["Tahmin Güveni %"] = ((0.40*obs_score + 0.30*op_score + 0.15*cap_score + 0.15*turnover_score)*100).round(1)
        h["Karar Durumu"] = np.select(
            [h["Tahmin Güveni %"]<35, h["Tahmini Açık/Fazla"]>=2, h["Tahmini Açık/Fazla"]<=-2],
            ["Düşük güven - saha doğrulaması", "İşe alım/transfer değerlendirmesi", "Fazla kapasite/transfer değerlendirmesi"],
            default="İzle"
        )
        h["Norma Otomatik Etki"] = 0.0
        h["Transfer Kararına Otomatik Etki"] = 0.0
        horizon_frames.append(h)

    result = pd.concat(horizon_frames, ignore_index=True)
    # Anlaşılır kolon adları
    rename = {a_sid:"MağazaID", a_tid:"UnvanID", c_net:"Net Üretken Dakika"}
    if a_store: rename[a_store]="Mağaza"
    if a_title: rename[a_title]="Unvan"
    result = result.rename(columns=rename)
    # Birleşmeler aynı adlı kimlik alanlarında _x/_y üretebilir; tek kanonik kolonda birleştir.
    def _coalesce_identity(target: str, tokens: tuple[str, ...]):
        if target in result.columns:
            return
        candidates=[c for c in result.columns if all(t in _norm(c) for t in tokens)]
        if candidates:
            result[target]=result[candidates].bfill(axis=1).iloc[:,0]
    _coalesce_identity("MağazaID", ("MAGAZA","ID"))
    _coalesce_identity("UnvanID", ("UNVAN","ID"))
    if "Mağaza" not in result.columns:
        candidates=[c for c in result.columns if "MAGAZA" in _norm(c) and "ID" not in _norm(c)]
        if candidates: result["Mağaza"]=result[candidates].bfill(axis=1).iloc[:,0]
    if "Unvan" not in result.columns:
        candidates=[c for c in result.columns if "UNVAN" in _norm(c) and "ID" not in _norm(c)]
        if candidates: result["Unvan"]=result[candidates].bfill(axis=1).iloc[:,0]
    preferred = ["Tahmin Ufku Gün","MağazaID","Mağaza","UnvanID","Unvan","Aktif Mevcut","Yönetim Normu","Minimum Kadro",
                 "Günlük İş Yükü Dk","Net Üretken Dakika","Ham İş Yükü FTE","Operasyon Trend","Operasyon Çarpanı",
                 "Takvim/Sezon Çarpanı","FM Tampon FTE","Kayıp Kapasite FTE","Operasyon Tampon FTE","Beklenen Turnover Oranı (90G)","İlk 90 Gün Turnover Oranı","Turnover Risk Altındaki Kişi","Turnover Çıkış Gözlemi","Turnover Veri Durumu","Turnover Riski FTE (Senaryo)","Turnover Riski FTE",
                 "Tahmini İş Yükü FTE (Saf)","İş Yükü Ağırlığı","Tahmini İş Yükü FTE","Tahmini Gerekli Kadro (Ham)","Tahmini Gerekli Kadro","Yuvarlama Etkisi Kişi","Tahmini Açık/Fazla",
                 "Yönetim Normundan Fark","Tahmin Güveni %","Karar Durumu","Operasyon Veri Kalitesi","Takvim Açıklaması",
                 "Norma Otomatik Etki","Transfer Kararına Otomatik Etki"]
    result = result[[c for c in preferred if c in result.columns]]
    # Kimlik eşleşmesi olmayan satırlar yönetici toplamlarını bozmasın. Bu satırlar
    # ayrı veri kalitesi sorunu olarak kaydedilir ve yayımlanan tahminden çıkarılır.
    invalid_identity = (
        result.get("Mağaza", pd.Series(index=result.index, dtype=object)).isna()
        | result.get("Unvan", pd.Series(index=result.index, dtype=object)).isna()
        | result.get("Mağaza", pd.Series(index=result.index, dtype=object)).astype(str).str.strip().str.lower().isin(["", "none", "nan"])
        | result.get("Unvan", pd.Series(index=result.index, dtype=object)).astype(str).str.strip().str.lower().isin(["", "none", "nan"])
    )
    invalid_rows = result.loc[invalid_identity].copy()
    result = result.loc[~invalid_identity].copy()

    summary = result.groupby("Tahmin Ufku Gün",as_index=False).agg(
        **{"Tahmini Gerekli Kadro":("Tahmini Gerekli Kadro","sum"),
           "Aktif Mevcut":("Aktif Mevcut","sum"),
           "Toplam Tahmini Açık":("Tahmini Açık/Fazla",lambda s:int(s.clip(lower=0).sum())),
           "Toplam Tahmini Fazla":("Tahmini Açık/Fazla",lambda s:int((-s.clip(upper=0)).sum())),
           "Ortalama Güven %":("Tahmin Güveni %","mean")})
    summary["Net Durum"] = summary["Toplam Tahmini Fazla"] - summary["Toplam Tahmini Açık"]

    assumptions = pd.DataFrame([{"Parametre":k,"Değer":v} for k,v in params.items()])
    assumptions = pd.concat([assumptions, pd.DataFrame([
        {"Parametre":"Tahmin Modu","Değer":FORECAST_MODE},
        {"Parametre":"Norma Otomatik Etki","Değer":MAXIMUM_NORM_EFFECT},
        {"Parametre":"Transfer Kararına Otomatik Etki","Değer":MAXIMUM_TRANSFER_EFFECT},
        {"Parametre":"Uyarı","Değer":"Çıktı karar desteğidir; resmî norm değildir."},
    ])], ignore_index=True)

    from services.forecast_validation import run as run_validation
    validation = run_validation(sheets, outdir)
    outdir = Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    path = outdir / OUTPUT_FILE_NAME
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Yönetici Özeti", index=False)
        result.to_excel(writer, sheet_name="Mağaza_Unvan_Tahmini", index=False)
        assumptions.to_excel(writer, sheet_name="Varsayımlar", index=False)
        trends.to_excel(writer, sheet_name="Operasyon_Trendleri", index=False)
        if not invalid_rows.empty:
            invalid_rows.to_excel(writer, sheet_name="Veri_Kalitesi_Eslesmeyen", index=False)
        for sheet_name, frame in validation.items():
            if frame is not None and not frame.empty:
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return {"status":"SUCCESS","file":str(path),"rows":len(result),"stores":int(result["MağazaID"].nunique()),
            "titles":int(result["UnvanID"].nunique()),"mode":FORECAST_MODE,
            "maximum_norm_effect":MAXIMUM_NORM_EFFECT,"maximum_transfer_effect":MAXIMUM_TRANSFER_EFFECT}
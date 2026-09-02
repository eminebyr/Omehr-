from __future__ import annotations

"""BULUT MOTORU KÖPRÜSÜ (2026-08-16 eklendi).

Amaç: Vercel'deki hafif arayüzün "Canlı motoru çalıştır" butonu için, BU
sunucudaki (Railway — kalıcı dosya sistemine ve gerçek input/referans
dosyalarına sahip TEK yer) resmi motoru çalıştırıp JSON'a uygun, sade bir
özet döndürmek.

Vercel'in kendi içinde motoru çalıştırmaya ÇALIŞMASI (ayrı bir
`cloud_adapter.py` ile) temelden yanlış bir yaklaşımdı: src/engine_core.py,
input Excel'i VE reference/*.xlsx kontrol dosyalarını DİSKTEN okur —
Vercel'in serverless Python fonksiyonlarında kalıcı disk yoktur. Bu modül,
o mimari uyumsuzluğu ortadan kaldırır: hesaplama HER ZAMAN burada
(Railway'de) yapılır, Vercel yalnız sonucu GÖRÜNTÜLER.

web/app.py'nin Genel Özet sekmesindeki KPI kartlarıyla BİREBİR AYNI resmi
kaynağı (src.engine_core.load() + state() + kpis()) kullanır — ayrı,
kalibre edilmemiş bir hesap yolu YOKTUR (bkz. web/app.py'deki ilgili not).
"""

import sys

import pandas as pd

from services.runtime_paths import code_root, runtime_root


def _df_to_records(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    """Bir DataFrame'i JSON'a güvenli (NaN/Timestamp içermeyen) kayıt listesine çevirir."""
    if df is None or df.empty:
        return []
    x = df.copy()
    if limit is not None:
        x = x.head(limit)
    # JSON serileştirmede patlayabilecek tipleri (NaT, Timestamp, NaN) güvenli hale getirir.
    for c in x.columns:
        if pd.api.types.is_datetime64_any_dtype(x[c]):
            x[c] = x[c].dt.strftime("%Y-%m-%d").fillna("")
    x = x.where(pd.notnull(x), None)
    return x.to_dict(orient="records")


def run_official_engine_summary() -> dict:
    """Resmi motoru (src.engine_core) çalıştırır, hafif bir JSON özeti döndürür.

    NOT: bu, main.py'nin yaptığı gibi TAM Excel/PDF rapor setini ÜRETMEZ
    (o, dakikalar sürebilir ve Vercel'in "Canlı motoru çalıştır" butonunun
    ihtiyacı olan şey değil) — yalnız KPI kartları + mağaza bazlı özet +
    unvan bazlı özet + risk özeti gibi, gösterge panosunun (dashboard)
    ihtiyaç duyduğu rakamları hesaplar. Kullanılan state()/kpis()/
    risk_table()/scenarios() fonksiyonlarının KENDİSİ tam resmi motorun
    BİZZAT parçasıdır — ayrı/basitleştirilmiş bir yeniden hesaplama DEĞİLDİR.
    """
    src_path = str(code_root() / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # DÜZELTME (web/app.py'deki AYNI kritik notla tutarlı): engine_core
    # KOD DEPOSUNUN src/ klasöründe yaşar, kiracının çalışma zamanı veri
    # dizininde DEĞİL — bu yüzden import'tan ÖNCE yol yukarıda eklenir.
    import engine_core as ec  # noqa: E402

    _p, sheets, norm, staff, _h = ec.load()
    st, tt = ec.state(norm, staff, sheets)  # st: mağaza bazlı | tt: mağaza+unvan bazlı detay
    kp = ec.kpis(st)
    risk = ec.risk_table(st)
    scens = ec.scenarios(st, tt, staff, sheets)

    # MAĞAZA BAZLI ÖZET (Bölge & Mağaza sayfası için): her mağazanın
    # mevcut/norm/eksik/fazla toplamları — doğrudan state()'in kendi
    # mağaza-seviyesi çıktısı (st), ikinci bir hesaplama YAPILMAZ.
    magaza_bazli = _df_to_records(
        st.rename(columns={
            "Mağaza": "magaza", "Bölge Sorumlusu": "bolge_sorumlusu",
            "Norm Kadro": "norm", "Aktif Mevcut": "mevcut",
            "Norm Eksiği": "eksik", "Norm Fazlası": "fazla", "Net Fark": "net_fark",
        })[["magaza", "bolge_sorumlusu", "mevcut", "norm", "eksik", "fazla", "net_fark"]]
        .sort_values("magaza")
    )

    # UNVAN BAZLI ÖZET (Unvan Analizi sayfası için): şirket genelinde her
    # unvanın toplam eksik/fazla dağılımı — tt (mağaza+unvan detayı)
    # 'Unvan' kırılımında toplanır.
    unvan_grouped = (
        tt.groupby("Unvan", dropna=False)[["Aktif Mevcut", "Norm Kadro", "Norm Eksiği", "Norm Fazlası"]]
        .sum()
        .reset_index()
    )
    unvan_grouped["Net Fark"] = unvan_grouped["Norm Fazlası"] - unvan_grouped["Norm Eksiği"]
    unvan_bazli = _df_to_records(
        unvan_grouped.rename(columns={
            "Unvan": "unvan", "Norm Kadro": "norm", "Aktif Mevcut": "mevcut",
            "Norm Eksiği": "eksik", "Norm Fazlası": "fazla", "Net Fark": "net_fark",
        })[["unvan", "mevcut", "norm", "eksik", "fazla", "net_fark"]]
        .sort_values("eksik", ascending=False)
    )

    # MAĞAZA+UNVAN DETAYI (isteğe bağlı, daha derin bir tablo/filtre için):
    # veri hacmi küçük olduğundan (mağaza × unvan) TAMAMI döndürülür.
    magaza_unvan_detay = _df_to_records(
        tt.rename(columns={
            "Mağaza": "magaza", "Unvan": "unvan", "Bölge Sorumlusu": "bolge_sorumlusu",
            "Norm Kadro": "norm", "Aktif Mevcut": "mevcut",
            "Norm Eksiği": "eksik", "Norm Fazlası": "fazla", "Net Fark": "net_fark",
        })[["magaza", "bolge_sorumlusu", "unvan", "mevcut", "norm", "eksik", "fazla", "net_fark"]]
    )

    transfer_pool_size = 0
    try:
        transfer_pool_size = int(pd.to_numeric(st.get("Norm Fazlası", 0), errors="coerce").fillna(0).sum())
    except Exception:
        pass

    summary = {
        "kpis": {
            "aktif_mevcut": kp.get("Aktif Mevcut", 0),
            "toplam_norm": kp.get("Toplam Norm", 0),
            "norm_eksigi": kp.get("Norm Eksiği", 0),
            "norm_fazlasi": kp.get("Norm Fazlası", 0),
            "net_ihtiyac": kp.get("Net İhtiyaç", 0),
        },
        "magaza_bazli": magaza_bazli,
        "unvan_bazli": unvan_bazli,
        "magaza_unvan_detay": magaza_unvan_detay,
        "risk_summary": _df_to_records(
            risk[["Mağaza", "Unvan", "Norm Eksiği", "Risk Puanı", "Risk Seviyesi"]]
            if risk is not None and not risk.empty and {"Mağaza", "Unvan", "Risk Puanı", "Risk Seviyesi"}.issubset(risk.columns)
            else risk,
            limit=25,
        ),
        "transfer_scenarios": {
            "havuz_buyuklugu": transfer_pool_size,
            "senaryo_sayisi": len(scens) if hasattr(scens, "__len__") else 0,
        },
        "ai_summary": {},
    }
    from services.cloud_module_snapshots import build_module_snapshots

    summary["modules"] = build_module_snapshots(
        sheets=sheets,
        staff=staff,
        store_title_detail=tt,
        scenarios=scens,
        output_dir=runtime_root() / "output",
    )
    from services.supabase_sync import sync_dashboard_summaries, sync_kpi_snapshot
    from services.version import APP_VERSION

    summary["supabase_sync"] = sync_dashboard_summaries(summary)
    # DÜZELTME: bu köprü daha önce yalnız sync_dashboard_summaries()
    # çağırıyordu (mağaza/unvan/modül tabloları) ama omehr_kpi_snapshot'ı
    # HİÇ güncellemiyordu — panelin "Son veri" saati bu tablodan okunduğu
    # için, "Motoru çalıştır" butonuna basınca arka planda gerçekten
    # başarılı çalışsa bile ekrandaki saat DEĞİŞMİYORDU (kullanıcı için
    # görünür bir teyit yoktu). kp, ec.kpis(st)'nin HAM (Türkçe anahtarlı)
    # çıktısı — sync_kpi_snapshot'ın beklediği formatla zaten birebir uyumlu.
    summary["kpi_sync_ok"] = sync_kpi_snapshot(kp, engine_version=APP_VERSION)
    return summary
from __future__ import annotations
"""Basit ve savunmacı, ŞİRKET TOPLAMI düzeyinde kısa vadeli ciro
projeksiyonu. Yeterli tarihsel veri yoksa tahmin uydurmaz; SKIPPED döner.

GÖZLEM MODU: Bu modülün çıktısı hiçbir
norm veya transfer hesaplamasına BAĞLI DEĞİLDİR — yalnız bilgi amaçlı,
şirket toplamı bir Excel raporu üretir. MAXIMUM_NORM_EFFECT ve
MAXIMUM_TRANSFER_EFFECT sabitleri 0.0'dır ve bunu AÇIKÇA belgeler; bu
bir "henüz kimse bağlamadı" tesadüfü değil, BİLİNÇLİ bir tasarım
kararıdır. Mağaza bazlı personel talep tahmini AYRI, gelecekteki bir
ayrı bir geliştirme ve doğrulama sürecinin konusudur.
"""
from pathlib import Path
import unicodedata
import pandas as pd

# Gözlem modu parametreleri — aşamalı
# devreye alma" bölümü. Bu sabitler BİLEREK burada, tek bir yerde
# tutuluyor (gelecekte config_features.json'a taşınabilir).
FORECAST_MODE = "observation_only"
MINIMUM_HISTORY_MONTHS = 6  # önceden 3 idi — erken/yetersiz veride yanıltmasın diye yükseltildi
MINIMUM_OBSERVATIONS = 8
MAXIMUM_NORM_EFFECT = 0.0      # bu modülün çıktısı norma HİÇ etki etmez (kasıtlı)
MAXIMUM_TRANSFER_EFFECT = 0.0  # bu modülün çıktısı transfer kararına HİÇ etki etmez (kasıtlı)
OUTPUT_FILE_NAME = "OMEHR_Ciro_Kisa_Vadeli_Projeksiyonu.xlsx"


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _find_col(df: pd.DataFrame, *tokens: str) -> str | None:
    wanted = [_norm(token) for token in tokens]
    for column in df.columns:
        normalized = _norm(column)
        if all(token in normalized for token in wanted):
            return column
    return None


def _clean_embedded_header(frame: pd.DataFrame) -> pd.DataFrame:
    """Başlığı ilk veri satırında bulunan Excel sayfalarını normalleştirir.

    ``Aylık Operasyon KPI`` sayfası kurumsal başlığı ilk satırda, gerçek
    kolon adlarını ikinci satırda taşır. pandas varsayılan okumada bu nedenle
    kolonları ``AYLIK OPERASYON KPI / Unnamed:*`` olarak görür. En güçlü
    tarih-ciro-mağaza başlık satırı bulunup gerçek tabloya çevrilir.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    result = frame.copy()
    if _find_col(result, "ciro") and (_find_col(result, "ay") or _find_col(result, "tarih")):
        return result.dropna(how="all").reset_index(drop=True)
    best_row, best_score = None, 0
    for row_index in range(min(12, len(result))):
        values = {_norm(value) for value in result.iloc[row_index].dropna()}
        score = sum(any(token in value for value in values) for token in ("AY", "CIRO", "MAGAZA"))
        if score > best_score:
            best_row, best_score = row_index, score
    if best_row is None or best_score < 2:
        return result.dropna(how="all").reset_index(drop=True)
    headers = [str(value).strip() if pd.notna(value) else f"Kolon_{i + 1}" for i, value in enumerate(result.iloc[best_row])]
    result = result.iloc[best_row + 1:].copy()
    result.columns = headers
    return result.dropna(how="all").reset_index(drop=True)


def _forecast_value(monthly: pd.Series) -> tuple[float, float, float]:
    window = monthly.tail(min(6, len(monthly)))
    average = float(window.mean())
    changes = window.pct_change().replace([float("inf"), -float("inf")], pd.NA).dropna()
    trend = float(changes.mean()) if not changes.empty else 0.0
    cautious = round(average * (1 + max(min(trend, 0.10), -0.10)), 2)
    return average, trend, cautious


def run(sheets: dict, outdir: Path) -> dict:
    candidates = ['Aylık Operasyon KPI', 'Operasyon', 'Fact_Operasyon', 'Operasyon_KPI', 'Ciro_Fis_Sepet']
    source_name = next((name for name in candidates if name in sheets and not sheets[name].empty), None)
    df = _clean_embedded_header(sheets[source_name]) if source_name else None
    if df is None:
        return {'status': 'SKIPPED', 'reason': 'Tarihsel operasyon sayfası bulunamadı'}
    date_col = _find_col(df, 'ay') or _find_col(df, 'tarih') or _find_col(df, 'donem')
    revenue_col = _find_col(df, 'ciro')
    if not date_col or not revenue_col:
        return {'status': 'SKIPPED', 'reason': 'Tarih/ciro sütunu bulunamadı'}
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df[revenue_col] = pd.to_numeric(df[revenue_col], errors='coerce')
    x = df.dropna(subset=[date_col, revenue_col]).sort_values(date_col)
    # Gelecek aya ait plan/tahmin satırları tarihsel gerçekleşen gibi modele
    # sokulmaz. İçinde bulunulan ay kullanılabilir; sonraki aylar dışarıda kalır.
    current_month = pd.Timestamp.now().to_period('M').to_timestamp()
    x = x[x[date_col].dt.to_period('M').dt.to_timestamp().le(current_month)].copy()
    if len(x) < MINIMUM_OBSERVATIONS:
        return {'status': 'SKIPPED', 'reason': f'En az {MINIMUM_OBSERVATIONS} tarihsel gözlem gerekir', 'rows': len(x)}
    monthly = x.set_index(date_col)[revenue_col].resample('MS').sum().dropna()
    if len(monthly) < MINIMUM_HISTORY_MONTHS:
        return {
            'status': 'SKIPPED',
            'reason': f'En az {MINIMUM_HISTORY_MONTHS} aylık tarihsel veri gerekir (gözlem modu eşiği)',
            'months': len(monthly),
        }
    forecast, trend, cautious_forecast = _forecast_value(monthly)
    next_month = monthly.index.max() + pd.offsets.MonthBegin(1)
    result = pd.DataFrame([{
        'Tahmin Ayı': next_month.strftime('%Y-%m'),
        'Son Aylık Ciro': float(monthly.iloc[-1]),
        '6 Aylık Ortalama': forecast,
        'Ortalama Aylık Değişim %': round(trend * 100, 2),
        'Temkinli Tahmin': cautious_forecast,
        'Yöntem': 'Hareketli ortalama + sınırlandırılmış trend (şirket toplamı)',
        'Mod': 'Gözlem — karar amaçlı kullanılmamalıdır',
        'Norma Etkisi': 0.0,
        'Transfer Kararına Etkisi': 0.0,
        'Not': 'Bu bir ciro projeksiyonudur; mağaza bazlı personel talep tahmini DEĞİLDİR.',
    }])
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / OUTPUT_FILE_NAME
    history = monthly.rename('Toplam Ciro').reset_index().rename(columns={date_col: 'Ay', 'index': 'Ay'})
    store_id_col = _find_col(x, 'magaza', 'id')
    store_name_col = next((column for column in x.columns if _norm(column) == 'MAGAZA'), None)
    store_rows = []
    if store_id_col:
        for store_id, group in x.groupby(store_id_col):
            store_monthly = group.set_index(date_col)[revenue_col].resample('MS').sum().dropna()
            if len(store_monthly) < MINIMUM_HISTORY_MONTHS:
                continue
            store_average, store_trend, store_forecast = _forecast_value(store_monthly)
            store_rows.append({
                'MağazaID': str(store_id),
                'Mağaza': str(group[store_name_col].dropna().iloc[-1]).strip() if store_name_col and group[store_name_col].notna().any() else '',
                'Tahmin Ayı': (store_monthly.index.max() + pd.offsets.MonthBegin(1)).strftime('%Y-%m'),
                'Son Aylık Ciro': float(store_monthly.iloc[-1]),
                '6 Aylık Ortalama': store_average,
                'Ortalama Aylık Değişim %': round(store_trend * 100, 2),
                'Temkinli Tahmin': store_forecast,
                'Gözlem Ayı': int(len(store_monthly)),
            })
    store_forecast = pd.DataFrame(store_rows)
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name='Şirket Projeksiyonu', index=False)
        history.to_excel(writer, sheet_name='Tarihsel Aylık Toplamlar', index=False)
        (store_forecast if not store_forecast.empty else pd.DataFrame([{'Durum': 'Mağaza bazlı yeterli tarihçe yok'}])).to_excel(
            writer, sheet_name='Mağaza Projeksiyonu', index=False
        )
    return {
        'status': 'SUCCESS',
        'file': str(path),
        'months': len(monthly),
        'forecast': float(result.iloc[0]['Temkinli Tahmin']),
        'source_sheet': source_name,
        'latest_actual_month': monthly.index.max().strftime('%Y-%m'),
        'store_forecasts': int(len(store_forecast)),
        'forecast_mode': FORECAST_MODE,
        'maximum_norm_effect': MAXIMUM_NORM_EFFECT,
        'maximum_transfer_effect': MAXIMUM_TRANSFER_EFFECT,
    }

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
import pandas as pd

# Gözlem modu parametreleri — aşamalı
# devreye alma" bölümü. Bu sabitler BİLEREK burada, tek bir yerde
# tutuluyor (gelecekte config_features.json'a taşınabilir).
FORECAST_MODE = "observation_only"
MINIMUM_HISTORY_MONTHS = 6  # önceden 3 idi — erken/yetersiz veride yanıltmasın diye yükseltildi
MINIMUM_OBSERVATIONS = 8
MAXIMUM_NORM_EFFECT = 0.0      # bu modülün çıktısı norma HİÇ etki etmez (kasıtlı)
MAXIMUM_TRANSFER_EFFECT = 0.0  # bu modülün çıktısı transfer kararına HİÇ etki etmez (kasıtlı)
OUTPUT_FILE_NAME = "BASDAS_Ciro_Kisa_Vadeli_Projeksiyonu.xlsx"


def run(sheets: dict, outdir: Path) -> dict:
    candidates = ['Operasyon', 'Fact_Operasyon', 'Operasyon_KPI', 'Ciro_Fis_Sepet']
    df = next((sheets[n].copy() for n in candidates if n in sheets and not sheets[n].empty), None)
    if df is None:
        return {'status': 'SKIPPED', 'reason': 'Tarihsel operasyon sayfası bulunamadı'}
    date_col = next((c for c in df.columns if str(c).lower() in ('tarih', 'date', 'ay', 'dönem', 'donem')), None)
    revenue_col = next((c for c in df.columns if 'ciro' in str(c).lower()), None)
    if not date_col or not revenue_col:
        return {'status': 'SKIPPED', 'reason': 'Tarih/ciro sütunu bulunamadı'}
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df[revenue_col] = pd.to_numeric(df[revenue_col], errors='coerce')
    x = df.dropna(subset=[date_col, revenue_col]).sort_values(date_col)
    if len(x) < MINIMUM_OBSERVATIONS:
        return {'status': 'SKIPPED', 'reason': f'En az {MINIMUM_OBSERVATIONS} tarihsel gözlem gerekir', 'rows': len(x)}
    monthly = x.set_index(date_col)[revenue_col].resample('MS').sum().dropna()
    if len(monthly) < MINIMUM_HISTORY_MONTHS:
        return {
            'status': 'SKIPPED',
            'reason': f'En az {MINIMUM_HISTORY_MONTHS} aylık tarihsel veri gerekir (gözlem modu eşiği)',
            'months': len(monthly),
        }
    window = monthly.tail(min(6, len(monthly)))
    forecast = float(window.mean())
    trend = float(window.pct_change().replace([float('inf'), -float('inf')], pd.NA).dropna().mean() or 0)
    next_month = monthly.index.max() + pd.offsets.MonthBegin(1)
    result = pd.DataFrame([{
        'Tahmin Ayı': next_month.strftime('%Y-%m'),
        'Son Aylık Ciro': float(monthly.iloc[-1]),
        '6 Aylık Ortalama': forecast,
        'Ortalama Aylık Değişim %': round(trend * 100, 2),
        'Temkinli Tahmin': round(forecast * (1 + max(min(trend, 0.10), -0.10)), 2),
        'Yöntem': 'Hareketli ortalama + sınırlandırılmış trend (şirket toplamı)',
        'Mod': 'Gözlem — karar amaçlı kullanılmamalıdır',
        'Norma Etkisi': 0.0,
        'Transfer Kararına Etkisi': 0.0,
        'Not': 'Bu bir ciro projeksiyonudur; mağaza bazlı personel talep tahmini DEĞİLDİR.',
    }])
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / OUTPUT_FILE_NAME
    result.to_excel(path, index=False)
    return {
        'status': 'SUCCESS',
        'file': str(path),
        'months': len(monthly),
        'forecast': float(result.iloc[0]['Temkinli Tahmin']),
        'forecast_mode': FORECAST_MODE,
        'maximum_norm_effect': MAXIMUM_NORM_EFFECT,
        'maximum_transfer_effect': MAXIMUM_TRANSFER_EFFECT,
    }

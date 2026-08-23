from __future__ import annotations

import pandas as pd


def _key(value: object) -> str:
    s = str(value or '').strip().upper()
    table = str.maketrans('ÇĞİÖŞÜÂÎÛ', 'CGIOSUAIU')
    return ' '.join(s.translate(table).split())

PAIRS = (
    ('YONETICI', 'YONETICI YARDIMCISI'),
    ('MANAV', 'MANAV YARDIMCISI'),
    ('SARKUTERI', 'SARKUTERI YARDIMCISI'),
    ('KASAP', 'KASAP YARDIMCISI'),
)


def balance_store_title_rows(
    frame: pd.DataFrame,
    *,
    key_col: str,
    norm_col: str,
    current_col: str,
    deficit_col: str,
    surplus_col: str,
    warning_col: str = '_Ana Unvan Personelsiz',
) -> pd.DataFrame:
    """Ana/yardimci rol dagilimini ayni aile toplami uzerinden dengeler.

    Satirlar ayri kalir. Ancak aile toplam mevcut, aile toplam normu
    karsiliyorsa dagilimdan dogan yapay eksik/fazla sifirlanir. Aile
    toplaminda gercek acik veya fazla varsa yalniz gercek fark raporlanir.

    KARAR (kullanici ile netlestirildi -- src/state_engine.py::
    _reconcile_main_family_rules ile AYNI kural, "Kural A"): burasi
    KPI/norm dengeleme katmanidir ve soruyu "ayni aile icindeki fiili
    kapasite normu karsiliyor mu?" olarak yanitlar. Ana unvanda HIC
    gercek kisi olmasa bile, aile toplam kapasitesi aile toplam normunu
    karsiliyorsa Eksik/Fazla dengelenir (KASITLI) -- yapay 1 eksik + 1
    fazla ile toplam rakamlarin/transfer motorunun sismesi ONLENIR.

    Kaybedilmemesi gereken bilgi (ana unvanda gercek kimse yok) KPI
    sayisini BOZMADAN, warning_col'da (varsayilan '_Ana Unvan
    Personelsiz') ayri bir niteliksel bayrak olarak korunur.
    """
    out = frame.copy()
    if out.empty or key_col not in out.columns:
        return out
    for col in (norm_col, current_col, deficit_col, surplus_col):
        out[col] = pd.to_numeric(out.get(col, 0), errors='coerce').fillna(0).astype(int)
    if warning_col not in out.columns:
        out[warning_col] = False
    try:
        from services.norm_rule_config import load_norm_rules
        min_main = int((load_norm_rules().get('assistant_balance') or {}).get('minimum_main_current', 1) or 1)
    except Exception:
        min_main = 1
    keys = out[key_col].map(_key)
    for main, assistant in PAIRS:
        idx = out.index[keys.isin((main, assistant))].tolist()
        if not idx:
            continue
        main_idx = [i for i in idx if keys.loc[i] == main]
        main_current = int(out.loc[main_idx, current_col].sum()) if main_idx else 0
        total_norm = int(out.loc[idx, norm_col].sum())
        total_current = int(out.loc[idx, current_col].sum())
        if total_norm == 0 and total_current == 0:
            continue
        # NITELIKSEL UYARI (KPI'yi etkilemez): ana unvanda gercek kisi
        # sayisi tabanin altindaysa bile Kural A ile dengeleme uygulanir,
        # ama "bu magazada bu rolde dogrudan gorevli personel yok"
        # bilgisi ayri bir bayrakla korunur.
        if main_current < min_main and main_idx:
            out.at[main_idx[0], warning_col] = True
        out.loc[idx, [deficit_col, surplus_col]] = 0
        target = next((i for i in idx if keys.loc[i] == main), idx[0])
        if total_current < total_norm:
            out.at[target, deficit_col] = total_norm - total_current
        elif total_current > total_norm:
            out.at[target, surplus_col] = total_current - total_norm
    return out


def balance_detail_table(tt: pd.DataFrame) -> pd.DataFrame:
    """Mağaza+Unvan detay tablosunu tüm mağazalar için dengeler."""
    if tt is None or tt.empty or 'Mağaza' not in tt.columns or 'Unvan' not in tt.columns:
        return tt.copy() if tt is not None else tt
    parts = []
    for _, grp in tt.groupby('Mağaza', dropna=False, sort=False):
        parts.append(balance_store_title_rows(
            grp,
            key_col='Unvan', norm_col='Norm Kadro', current_col='Aktif Mevcut',
            deficit_col='Norm Eksiği', surplus_col='Norm Fazlası'
        ))
    out = pd.concat(parts, ignore_index=True) if parts else tt.copy()
    if 'Net Fark' in out.columns:
        out['Net Fark'] = pd.to_numeric(out['Norm Fazlası'], errors='coerce').fillna(0).astype(int) - pd.to_numeric(out['Norm Eksiği'], errors='coerce').fillna(0).astype(int)
    return out


def family_balance_notes(tt: pd.DataFrame, store_key: str) -> list[str]:
    """Servis katmanı köprüsü — web/ katmanı src/ dosyalarını doğrudan import
    edemez (bkz. tools/check_architecture.py). Gerçek üretim mantığı
    src.state_engine.family_balance_notes içindedir (kutucuklu Excel/PDF
    raporlarındaki "MEVCUT DURUM AÇIKLAMASI" ile aynı metin kalıbı); bu
    fonksiyon sadece web/tab_modules için izin verilen bir erişim noktasıdır.
    """
    from src.state_engine import family_balance_notes as _impl
    return _impl(tt, store_key)

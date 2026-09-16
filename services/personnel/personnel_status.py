from __future__ import annotations

import pandas as pd

EXIT_COLUMNS = (
    "İşten Çıkış", "Isten Cikis", "İşten Çıkış Tarihi", "Cikis Tarihi", "Çıkış Tarihi"
)


def first_exit_column(frame: pd.DataFrame) -> str | None:
    for c in EXIT_COLUMNS:
        if c in frame.columns:
            return c
    return None


def exit_is_recorded(value, *, bugun=None) -> bool:
    """Kullanıcı çıkışı işlediyse VE çıkış tarihi GELDİYSE (bugün veya
    geçmişse) kayıt pasiftir.

    DÜZELTME (iş kuralı değişikliği — kullanıcı ile netleştirildi,
    OMEHR hızlandırma şartnamesi Madde 13/76): önceden resmi İşten
    Çıkış alanına HERHANGİ bir tarih yazılması (GELECEKTE olsa bile)
    kişiyi ANINDA pasif sayıyordu. Artık gelecek tarihli bir çıkış
    kaydı girildiğinde kişi ÇIKIŞ TARİHİNE KADAR aktif kalır — o gün
    geldiğinde otomatik olarak pasif olur (ayrı bir işlem gerekmez,
    her hesaplama "bugün" ile karşılaştırır). Açıklama/not alanındaki
    metin (ör. '15.08.2026 istifa edecek') hâlâ resmi çıkış SAYILMAZ —
    yalnız bu resmi alan dikkate alınır.
    """
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    text = str(value).strip()
    if text in {"", "None", "nan", "NaT", "<NA>"}:
        return False
    try:
        # DÜZELTME (kritik tarih ayrıştırma hatası): dayfirst=True HER
        # zaman uygulanırsa, ISO biçimli "2026-08-10" gibi bir metin
        # YANLIŞ olarak "10 Ekim 2026" diye ayrıştırılıyordu (gün/ay
        # karışıklığı) — bizzat kanıtlandı. Artık yalnız NOKTA ayraçlı,
        # gerçekten belirsiz olabilecek Türkçe biçimli metinlerde
        # (ör. "16.08.2026") dayfirst uygulanır; ISO metinler (tire
        # ayraçlı) ve zaten bir datetime/Timestamp nesnesi olan
        # değerler pandas'ın kendi doğru biçim çıkarımıyla ayrıştırılır.
        _dayfirst = isinstance(value, str) and "." in value
        cikis_tarihi = pd.to_datetime(value, dayfirst=_dayfirst, errors="raise")
    except Exception:
        # Tarih olarak ayrıştırılamayan ama boş da olmayan bir değer —
        # güvenli tarafta kal: resmi bir kayıt VAR sayılır (veri kaybı/
        # yanlış-aktif riskini önlemek için).
        return True
    referans = pd.Timestamp(bugun) if bugun is not None else pd.Timestamp.now().normalize()
    return cikis_tarihi.normalize() <= referans


def row_is_active(row) -> bool:
    for c in EXIT_COLUMNS:
        try:
            if c in row:
                return not exit_is_recorded(row.get(c))
        except Exception:
            continue
    # Çıkış kolonu yoksa eski Durum alanına yalnız yedek olarak bakılır.
    try:
        if "Durum" in row:
            value = row.get("Durum")
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return True
            return str(value).strip().casefold() in {"", "aktif"}
    except Exception:
        pass
    return True


def active_people(frame: pd.DataFrame) -> pd.DataFrame:
    """Tek ve merkezi aktif-personel filtresi.

    Tüm KPI, web, PDF ve Excel raporları bunu kullanmalıdır. Böylece çıkışı
    Excel'e/web panele işlenen bir kişinin bir yerde aktif, başka yerde pasif
    görünmesi önlenir.
    """
    if frame is None:
        return pd.DataFrame()
    x = frame.copy()
    exit_col = first_exit_column(x)
    if exit_col:
        mask = ~x[exit_col].map(exit_is_recorded)
        return x.loc[mask].copy()
    if "Durum" in x.columns:
        d = x["Durum"].astype(str).str.strip().str.casefold()
        mask = d.isin({"", "aktif", "none", "nan", "nat"}) | x["Durum"].isna()
        return x.loc[mask].copy()
    return x

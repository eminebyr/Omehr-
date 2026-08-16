from pathlib import Path
import pandas as pd

from src.state_engine import state
from src.kpi_engine import kpis


def _input_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'input' / 'BASDAS_AI_NORM_TRANSFER_INPUT.xlsx'


def test_all_branch_kpis_and_family_consistency():
    sheets = pd.read_excel(_input_path(), sheet_name=None)
    stores, detail = state(sheets['Fact_Norm'], sheets['Fact_Mevcut'], sheets)
    kp = kpis(stores)
    assert kp == {
        'Aktif Mevcut': 596,
        'Toplam Norm': 607,
        'Norm Eksiği': 49,
        'Norm Fazlası': 23,
        'Net İhtiyaç': -26,
    }
    store_names = set(stores['Mağaza'].dropna().astype(str).str.strip())
    assert len(store_names) == 48
    assert (detail['Norm Eksiği'] >= 0).all()
    assert (detail['Norm Fazlası'] >= 0).all()


def _referential_control_map(sheets):
    """src/state_engine.py'nin AYNI mantığıyla REFERENTIAL_CONTROL'ü
    (MağazaID, Unvan) -> Norm Eksiği Kontrol eşlemesine çevirir — testin
    'gerçek kontrol kaynağını' bağımsızca okuyup doğrulayabilmesi için."""
    from src.text_utils import txt, _title_key, req, numeric
    ctl = sheets.get('REFERENTIAL_CONTROL')
    if ctl is None or ctl.empty:
        return {}
    c = ctl.copy()
    c_mid = req(c, 'MağazaID', 'MagazaID')
    c_uid = req(c, 'UnvanID')
    c_e = req(c, 'Norm Eksiği Kontrol', 'Norm Eksigi Kontrol')
    dim_u = sheets.get('Dim_Unvan', pd.DataFrame())
    if not dim_u.empty and {'UnvanID', 'Unvan'}.issubset(dim_u.columns):
        uid_to_name = {txt(r['UnvanID']): _title_key(r['Unvan']) for _, r in dim_u.iterrows()}
    else:
        uid_to_name = {}
    c['_MağazaID'] = c[c_mid].map(txt)
    c['_Unvan'] = c[c_uid].map(lambda x: uid_to_name.get(txt(x), _title_key(txt(x))))
    c['_Eksik'] = numeric(c[c_e]).astype(int)
    return c.groupby(['_MağazaID', '_Unvan'])['_Eksik'].sum().to_dict()


def test_specialist_titles_cover_main_family_in_every_branch():
    """DÜZELTME: Önceden bu test 'Aktif Mevcut >= Norm Kadro ise Norm
    Eksiği kesinlikle 0 olmalı' varsayımıyla yazılmıştı — ama
    REFERENTIAL_CONTROL sayfası bunu KASITLI olarak geçersiz kılabilir
    (gerçek veride doğrulandı: İZMİRSPOR/ŞARKÜTERİ M050/U042 için
    REFERENTIAL_CONTROL'de AÇIKÇA 'Norm Eksiği Kontrol=1' kaydı var).

    Artık test naif sayımın HER ZAMAN doğru olduğunu VARSAYMIYOR —
    bunun yerine: sayım ile gerçek sonuç arasındaki HER sapmanın,
    REFERENTIAL_CONTROL sayfasındaki AÇIK bir kayıtla İZLENEBİLİR
    olduğunu doğruluyor. Bu hem mevcut (doğru, denetlenmiş) davranışla
    uyumludur HEM DE gerçek bir regresyonu (kontrol sayfasında hiç
    karşılığı olmayan, yani hesaplama hatasından kaynaklanan bir sapma)
    hâlâ yakalar.
    """
    from src.text_utils import txt, _title_key

    sheets = pd.read_excel(_input_path(), sheet_name=None)
    stores, detail = state(sheets['Fact_Norm'], sheets['Fact_Mevcut'], sheets)
    kontrol = _referential_control_map(sheets)

    main = detail[detail['Unvan'].isin(['YÖNETİCİ', 'MANAV', 'ŞARKÜTERİ', 'KASAP'])]
    bad = main[(main['Aktif Mevcut'] >= main['Norm Kadro']) & (main['Norm Eksiği'] > 0)]

    izlenemeyen = []
    for _, row in bad.iterrows():
        anahtar = (txt(row['MağazaID']), _title_key(row['Unvan']))
        beklenen = kontrol.get(anahtar)
        if beklenen != int(row['Norm Eksiği']):
            izlenemeyen.append({
                'Mağaza': row['Mağaza'], 'Unvan': row['Unvan'],
                'Aktif Mevcut': row['Aktif Mevcut'], 'Norm Kadro': row['Norm Kadro'],
                'Hesaplanan Norm Eksiği': row['Norm Eksiği'],
                'REFERENTIAL_CONTROL değeri': beklenen,
            })
    assert not izlenemeyen, (
        f"{len(izlenemeyen)} satırda naif sayımla çelişen bir Norm Eksiği var VE "
        f"bu, REFERENTIAL_CONTROL sayfasındaki hiçbir kayıtla İZLENEMİYOR "
        f"(gerçek bir hesaplama hatası olabilir): {izlenemeyen}"
    )

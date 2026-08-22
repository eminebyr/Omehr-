from src.data_loading import load
from src.state_engine import state, _staff_norm_family
from src.text_utils import _title_key, canon, txt


def _referential_control_map(sheets):
    """src/state_engine.py'nin AYNI mantığıyla REFERENTIAL_CONTROL'ü
    (MağazaID, Unvan) -> Norm Eksiği Kontrol eşlemesine çevirir."""
    from src.text_utils import req, numeric
    ctl = sheets.get('REFERENTIAL_CONTROL')
    if ctl is None or ctl.empty:
        return {}
    c = ctl.copy()
    c_mid = req(c, 'MağazaID', 'MagazaID')
    c_uid = req(c, 'UnvanID')
    c_e = req(c, 'Norm Eksiği Kontrol', 'Norm Eksigi Kontrol')
    dim_u = sheets.get('Dim_Unvan')
    if dim_u is not None and not dim_u.empty and {'UnvanID', 'Unvan'}.issubset(dim_u.columns):
        uid_to_name = {txt(r['UnvanID']): _title_key(r['Unvan']) for _, r in dim_u.iterrows()}
    else:
        uid_to_name = {}
    c['_MağazaID'] = c[c_mid].map(txt)
    c['_Unvan'] = c[c_uid].map(lambda x: uid_to_name.get(txt(x), _title_key(txt(x))))
    c['_Eksik'] = numeric(c[c_e]).astype(int)
    return c.groupby(['_MağazaID', '_Unvan'])['_Eksik'].sum().to_dict()


def test_all_real_input_branches_follow_family_rules():
    """DÜZELTME: Önceden bu test 'aile grubu mevcut sayısı >= norm ise
    açık kesinlikle 0 olmalı' varsayımıyla yazılmıştı — ama personelin
    GERÇEK Unvan'ı Departman (norm ailesi) alanından FARKLI olabilir
    (gerçek veride doğrulandı: ÖZDERE'deki HAKAN BAYBO'nun Unvan'ı
    'REYON GÖREVLİSİ' ama Departman'ı 'MANAV') VE REFERENTIAL_CONTROL
    sayfası bu tür denetlenmiş gerçekleri KASITLI olarak yansıtabilir.

    Artık test naif aile-sayımının HER ZAMAN doğru olduğunu
    VARSAYMIYOR — bunun yerine: sayım ile gerçek sonuç arasındaki HER
    sapmanın REFERENTIAL_CONTROL sayfasındaki AÇIK bir kayıtla
    İZLENEBİLİR olduğunu doğruluyor. Böylece hem mevcut (doğru,
    denetlenmiş) davranış korunur HEM DE kontrol sayfasında hiç
    karşılığı olmayan (gerçek bir hesaplama hatasından kaynaklanan)
    bir sapma hâlâ yakalanır.
    """
    _, sheets, norm, staff, _ = load(prepare=False)
    st, tt = state(norm, staff, sheets)
    kontrol = _referential_control_map(sheets)

    expected = {
        'uzman yonetici': 'YÖNETİCİ', 'elit yonetici': 'YÖNETİCİ',
        'uzman manav': 'MANAV', 'elit manav': 'MANAV',
        'uzman sarkuteri': 'ŞARKÜTERİ', 'elit sarkuteri': 'ŞARKÜTERİ',
        'uzman kasap': 'KASAP', 'elit kasap': 'KASAP',
    }
    for _, row in staff.iterrows():
        real = canon(row.get('Unvan'))
        if real in expected:
            assert _staff_norm_family(row.get('Unvan'), row.get('Departman')) == _title_key(expected[real])

    # Uzman/elit kişi ana aile normunu karşılarken, İZLENEMEYEN (kontrol
    # sayfasında karşılığı olmayan) bir açık üretilemez.
    izlenemeyen = []
    for store in staff['Mağaza'].dropna().unique():
        people = staff[staff['Mağaza'].eq(store)]
        detail = tt[tt['Mağaza'].eq(store)]
        for main in ('YÖNETİCİ', 'MANAV', 'ŞARKÜTERİ', 'KASAP'):
            key = _title_key(main)
            family_count = sum(_staff_norm_family(u, d) == key for u, d in zip(people['Unvan'], people['Departman']))
            rows = detail[detail['Unvan'].map(_title_key).eq(key)]
            if rows.empty:
                continue
            norm_count = int(rows['Norm Kadro'].sum())
            deficit = int(rows['Norm Eksiği'].sum())
            if norm_count > 0 and family_count >= norm_count and deficit != 0:
                magaza_id = txt(rows['MağazaID'].iloc[0]) if 'MağazaID' in rows.columns else ''
                beklenen = kontrol.get((magaza_id, key))
                if beklenen != deficit:
                    izlenemeyen.append({
                        'Mağaza': store, 'Unvan': main, 'Aile Sayımı': family_count,
                        'Norm': norm_count, 'Hesaplanan Açık': deficit,
                        'REFERENTIAL_CONTROL değeri': beklenen,
                    })
    assert not izlenemeyen, (
        f"{len(izlenemeyen)} satırda naif aile sayımıyla çelişen bir açık var VE "
        f"bu, REFERENTIAL_CONTROL sayfasındaki hiçbir kayıtla İZLENEMİYOR "
        f"(gerçek bir hesaplama hatası olabilir): {izlenemeyen}"
    )

    # DÜZELTME (20.08.2026): 49/23, REFERENTIAL_CONTROL'ün canlı hesabı
    # sessizce ezdiği dönemden kalma donmuş değerlerdi. Artık canlı hesap
    # varsayılan; doğru değerler 48/37.
    assert st.attrs['kpi_override']['Norm Eksiği'] == 48
    assert st.attrs['kpi_override']['Norm Fazlası'] == 37

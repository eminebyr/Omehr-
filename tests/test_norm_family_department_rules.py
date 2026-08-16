import pandas as pd

from src.state_engine import state


def test_real_titles_count_by_department_and_assistants_stay_separate():
    norm = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"YÖNETİCİ","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"YÖNETİCİ YARDIMCISI","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"ŞARKÜTERİ","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"ŞARKÜTERİ YARDIMCISI","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"KASAP","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"KASAP YARDIMCISI","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"MANAV","Norm Kadro":1},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"MANAV YARDIMCISI","Norm Kadro":1},
    ])
    staff = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"A","Unvan":"ELİT YÖNETİCİ","Departman":"YÖNETİCİ","Norm fazlası Norm eksiği":"Uygun"},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"B","Unvan":"UZMAN ŞARKÜTERİ","Departman":"ŞARKÜTERİ","Norm fazlası Norm eksiği":"Uygun"},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"C","Unvan":"ELİT KASAP","Departman":"KASAP","Norm fazlası Norm eksiği":"Uygun"},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"D","Unvan":"UZMAN MANAV","Departman":"MANAV","Norm fazlası Norm eksiği":"Uygun"},
    ])
    _, title = state(norm, staff, {})
    by_role = title.set_index("Unvan")
    assert by_role.loc["YÖNETİCİ", "Norm Eksiği"] == 0
    assert by_role.loc["ŞARKÜTERİ", "Norm Eksiği"] == 0
    assert by_role.loc["KASAP", "Norm Eksiği"] == 0
    assert by_role.loc["MANAV", "Norm Eksiği"] == 0
    assert by_role.loc["YÖNETİCİ YARDIMCISI", "Norm Eksiği"] == 1
    assert by_role.loc["ŞARKÜTERİ YARDIMCISI", "Norm Eksiği"] == 1
    assert by_role.loc["KASAP YARDIMCISI", "Norm Eksiği"] == 1
    assert by_role.loc["MANAV YARDIMCISI", "Norm Eksiği"] == 1



def test_one_main_plus_one_helper_can_balance_main_norm_two():
    norm = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"MANAV","Norm Kadro":2},
    ])
    staff = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"A","Unvan":"MANAV","Departman":"MANAV"},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"B","Unvan":"MANAV YARDIMCISI","Departman":"MANAV YARDIMCISI"},
    ])
    _, title = state(norm, staff, {})
    by_role = title.set_index("Unvan")
    assert by_role.loc["MANAV", "Norm Eksiği"] == 0
    assert by_role.loc["MANAV YARDIMCISI", "Norm Fazlası"] == 0


def test_zero_main_plus_two_helpers_closes_norm_via_family_capacity_but_flags_warning():
    """KARAR (kullanıcı ile netleştirildi): burada 0 gerçek MANAV var ama
    2 MANAV YARDIMCISI aile toplam normunu (2) karşılıyor — KPI/norm
    dengeleme katmanı bunu "aile kapasitesi normu karşılıyor mu?" sorusu
    olarak yanıtlar ve Eksik'i 0'a indirir (Kural A). "Bu mağazada MANAV
    rolünde doğrudan görevli kimse yok" bilgisi KAYBOLMAZ — ayrı bir
    niteliksel uyarı sütununda (Ana Unvan Personelsiz Uyarısı) korunur."""
    norm = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","Unvan":"MANAV","Norm Kadro":2},
    ])
    staff = pd.DataFrame([
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"A","Unvan":"MANAV YARDIMCISI","Departman":"MANAV YARDIMCISI"},
        {"MağazaID":"M1","Mağaza":"TEST","Bölge Sorumlusu":"BÖLGE","İsim Soyisim":"B","Unvan":"MANAV YARDIMCISI","Departman":"MANAV YARDIMCISI"},
    ])
    _, title = state(norm, staff, {})
    by_role = title.set_index("Unvan")
    assert by_role.loc["MANAV", "Norm Eksiği"] == 0
    assert bool(by_role.loc["MANAV", "Ana Unvan Personelsiz Uyarısı"]) is True

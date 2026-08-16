import pandas as pd
from services.family_balance import balance_store_title_rows, balance_detail_table


def test_two_manager_assistants_cover_manager_norm_via_family_capacity_with_warning():
    """KARAR (kullanıcı ile netleştirildi, son sürüm): KPI/norm dengeleme
    katmanı "aile kapasitesi normu karşılıyor mu?" sorusunu yanıtlar —
    0 ana personel olsa bile aile toplamı normu karşılıyorsa Eksik/Fazla
    dengelenir (Kural A). "Ana unvanda doğrudan görevli personel yok"
    bilgisi KAYBOLMAZ — ayrı bir niteliksel uyarı sütununda korunur.
    Bu, src/state_engine.py::_reconcile_main_family_rules ile AYNI
    karardır (bkz. TUM_SUBELER_AILE_DENGE_DUZELTME_NOTU.md, Kural A)."""
    df=pd.DataFrame([
        {'Unvan':'YÖNETİCİ','Norm Kadro':1,'Aktif Mevcut':0,'Norm Eksiği':1,'Norm Fazlası':0},
        {'Unvan':'YÖNETİCİ YARDIMCISI','Norm Kadro':1,'Aktif Mevcut':2,'Norm Eksiği':0,'Norm Fazlası':1},
    ])
    out=balance_store_title_rows(df,key_col='Unvan',norm_col='Norm Kadro',current_col='Aktif Mevcut',deficit_col='Norm Eksiği',surplus_col='Norm Fazlası')
    assert out['Norm Eksiği'].sum()==0
    assert out['Norm Fazlası'].sum()==0
    yonetici = out[out['Unvan']=='YÖNETİCİ'].iloc[0]
    assert bool(yonetici['_Ana Unvan Personelsiz']) is True, "0 ana personel varken uyarı bayrağı True olmalı."


def test_same_rule_for_manav_sarkuteri_kasap_all_stores():
    """3 mağazanın hepsinde ana unvanda 0 gerçek personel var ama aile
    toplamı normu karşılıyor — hepsi Kural A ile dengelenir, hepsinde
    uyarı bayrağı True olur."""
    rows=[]
    for store,main,assistant in [
        ('A','MANAV','MANAV YARDIMCISI'),
        ('B','ŞARKÜTERİ','ŞARKÜTERİ YARDIMCISI'),
        ('C','KASAP','KASAP YARDIMCISI'),
    ]:
        rows += [
            {'Mağaza':store,'Unvan':main,'Norm Kadro':1,'Aktif Mevcut':0,'Norm Eksiği':1,'Norm Fazlası':0,'Net Fark':-1},
            {'Mağaza':store,'Unvan':assistant,'Norm Kadro':1,'Aktif Mevcut':2,'Norm Eksiği':0,'Norm Fazlası':1,'Net Fark':1},
        ]
    out=balance_detail_table(pd.DataFrame(rows))
    assert out['Norm Eksiği'].sum()==0
    assert out['Norm Fazlası'].sum()==0
    assert out['Net Fark'].sum()==0
    for main in ('MANAV', 'ŞARKÜTERİ', 'KASAP'):
        satir = out[out['Unvan']==main].iloc[0]
        assert bool(satir['_Ana Unvan Personelsiz']) is True, f"{main}: uyarı bayrağı True olmalı."


def test_family_balance_still_covers_legitimate_case_when_main_has_minimum_staff():
    """Ana unvanda en az 1 gerçek kişi varken meşru mahsup davranışı
    (fazla yardımcının doğru raporlanması) çalışır ve uyarı bayrağı
    False kalır (yanlış pozitif üretmez)."""
    df=pd.DataFrame([
        {'Unvan':'YÖNETİCİ','Norm Kadro':1,'Aktif Mevcut':1,'Norm Eksiği':0,'Norm Fazlası':0},
        {'Unvan':'YÖNETİCİ YARDIMCISI','Norm Kadro':1,'Aktif Mevcut':1,'Norm Eksiği':0,'Norm Fazlası':0},
    ])
    out=balance_store_title_rows(df,key_col='Unvan',norm_col='Norm Kadro',current_col='Aktif Mevcut',deficit_col='Norm Eksiği',surplus_col='Norm Fazlası')
    assert out['Norm Eksiği'].sum()==0
    assert out['Norm Fazlası'].sum()==0
    assert bool(out[out['Unvan']=='YÖNETİCİ'].iloc[0]['_Ana Unvan Personelsiz']) is False

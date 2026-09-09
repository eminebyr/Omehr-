from pathlib import Path
import pandas as pd
from services.workforce_forecast import run


def test_workforce_forecast_produces_three_horizons(tmp_path):
    sheets={
      'Gunluk_Aktivite_Hacmi':pd.DataFrame({'Tarih':['2026-07-01']*10,'MağazaID':['M1']*10,'Mağaza':['TEST']*10,'UnvanID':['U1']*10,'Unvan':['KASİYER']*10,'İş Yükü (Dk)':[900]*10}),
      'Kapasite_Parametreleri':pd.DataFrame({'UnvanID':['U1'],'Net Üretken Dakika':[450]}),
      'Fact_Norm':pd.DataFrame({'MağazaID':['M1'],'UnvanID':['U1'],'Norm Kadro':[2]}),
      'Fact_Mevcut':pd.DataFrame({'MağazaID':['M1','M1'],'UnvanID':['U1','U1'],'İşten Çıkış':[None,None]}),
      'Aylık Operasyon KPI':pd.DataFrame({'Ay':pd.date_range('2025-08-01',periods=12,freq='MS'),'MagazaID':['M1']*12,'Aylık Ciro':range(100,112),'Aylık Fiş':range(1000,1012)}),
    }
    result=run(sheets,tmp_path)
    assert result['status']=='SUCCESS'
    detail=pd.read_excel(Path(result['file']),sheet_name='Mağaza_Unvan_Tahmini')
    assert set(detail['Tahmin Ufku Gün'])=={30,60,90}
    assert detail['Norma Otomatik Etki'].eq(0).all()


def test_forecast_keeps_all_active_staff_and_activity_only_rows_do_not_create_openings(tmp_path):
    sheets = {
        'Gunluk_Aktivite_Hacmi': pd.DataFrame({
            'Tarih': ['2026-07-01'] * 2,
            'MağazaID': ['M1', 'M1'],
            'Mağaza': ['TEST', 'TEST'],
            'UnvanID': ['U1', 'U2'],
            'Unvan': ['KASİYER', 'YENİ ROL'],
            'İş Yükü (Dk)': [450, 900],
        }),
        'Kapasite_Parametreleri': pd.DataFrame({
            'UnvanID': ['U1', 'U2', 'U3'],
            'Net Üretken Dakika': [450, 450, 450],
        }),
        'Fact_Norm': pd.DataFrame({'MağazaID': ['M1'], 'UnvanID': ['U1'], 'Norm Kadro': [1]}),
        'Fact_Mevcut': pd.DataFrame({
            'MağazaID': ['M1', 'M1', 'M1'],
            'UnvanID': ['U1', 'U3', 'U3'],
            'İşten Çıkış': [None, None, None],
        }),
        'Minimum_Kadro_Kurallari': pd.DataFrame({
            'UnvanID': ['U1', 'U2', 'U3'],
            'Minimum Kişi': [1, 1, 1],
        }),
        'Dim_Magaza': pd.DataFrame({'MağazaID': ['M1'], 'Mağaza': ['TEST']}),
        'Dim_Unvan': pd.DataFrame({'UnvanID': ['U1', 'U2', 'U3'], 'Unvan': ['KASİYER', 'YENİ ROL', 'YÖNETİCİ']}),
    }

    outcome = run(sheets, tmp_path)
    detail = pd.read_excel(Path(outcome['file']), sheet_name='Mağaza_Unvan_Tahmini')
    summary = pd.read_excel(Path(outcome['file']), sheet_name='Yönetici Özeti')
    view = detail[detail['Tahmin Ufku Gün'].eq(30)]

    assert view['Aktif Mevcut'].sum() == 3
    assert view.loc[view['Unvan'].eq('YENİ ROL'), 'Tahmini Açık/Fazla'].item() == 0
    assert view.loc[view['Unvan'].eq('YENİ ROL'), 'Tahmin Kapsamı'].item() == 'Norm inceleme adayı'
    assert view.loc[view['Unvan'].eq('YÖNETİCİ'), 'Tahmini Açık/Fazla'].item() == 0
    assert summary.loc[summary['Tahmin Ufku Gün'].eq(30), 'Aktif Mevcut'].item() == 3

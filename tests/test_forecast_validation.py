from pathlib import Path
import pandas as pd

from services.forecast_validation import operational_backtest
from services.workforce_forecast import run


def test_operational_backtest_metrics_are_produced(tmp_path: Path):
    dates = pd.date_range('2025-01-01', periods=12, freq='MS')
    op = pd.DataFrame({'Ay': dates, 'MağazaID':['M1']*12, 'Ciro':[100+i*5 for i in range(12)], 'Fiş':[50+i for i in range(12)]})
    detail, summary = operational_backtest({'Aylık Operasyon KPI':op})
    assert not detail.empty
    assert {'MAE','RMSE','MAPE %','WAPE %','Bias'}.issubset(summary.columns)


def test_workforce_forecast_keeps_decision_effect_zero(tmp_path: Path):
    dates = pd.date_range('2026-01-01', periods=30, freq='D')
    sheets = {
        'Gunluk_Aktivite_Hacmi': pd.DataFrame({'Tarih':dates,'MağazaID':['M1']*30,'Mağaza':['A']*30,'UnvanID':['U1']*30,'Unvan':['Kasiyer']*30,'İş Yükü (Dk)':[900]*30}),
        'Kapasite_Parametreleri': pd.DataFrame({'UnvanID':['U1'],'Net Üretken Dakika':[450]}),
        'Fact_Norm': pd.DataFrame({'MağazaID':['M1'],'UnvanID':['U1'],'Norm Kadro':[2]}),
        'Fact_Mevcut': pd.DataFrame({'PersonelID':['P1','P2'],'MağazaID':['M1','M1'],'UnvanID':['U1','U1'],'İşe Giriş':['2025-01-01','2025-02-01'],'İşten Çıkış':[None,None]}),
    }
    result = run(sheets,tmp_path)
    assert result['status']=='SUCCESS'
    detail = pd.read_excel(result['file'],sheet_name='Mağaza_Unvan_Tahmini')
    assert (detail['Norma Otomatik Etki']==0).all()
    assert (detail['Transfer Kararına Otomatik Etki']==0).all()

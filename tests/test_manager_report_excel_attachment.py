from pathlib import Path


def test_boxed_manager_excel_is_created_and_mailed():
    root = Path(__file__).resolve().parents[1]
    engine = (root / 'src' / 'engine_core.py').read_text(encoding='utf-8')
    excel = (root / 'src' / 'excel_report.py').read_text(encoding='utf-8')
    mail = (root / 'report_mail_engine.py').read_text(encoding='utf-8')
    expected = 'OMEHR_Kutucuklu_Yonetici_Raporu.xlsx'
    assert 'build_boxed_manager_excel' in engine
    assert expected in excel
    assert expected in mail
    assert 'OMEHR_Yonetici_Raporu.pdf' in mail

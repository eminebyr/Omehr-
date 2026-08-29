from pathlib import Path

import pandas as pd


def _valid_excel(path: Path, value: str):
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        pd.DataFrame({'Değer': [value]}).to_excel(writer, sheet_name='Fact_Mevcut', index=False)


def test_corrupt_input_is_quarantined_and_latest_valid_backup_restored(tmp_path, monkeypatch):
    import common_veri_okuma as cvo

    for name in ('input', 'backup', 'backups'):
        (tmp_path/name).mkdir()
    corrupt = tmp_path/'input'/'OMEHR_AI_NORM_TRANSFER_INPUT.xlsx'
    corrupt.write_bytes(b'yarim yazilmis excel')
    old = tmp_path/'backups'/'OMEHR_AI_NORM_TRANSFER_INPUT__20260828_120000.xlsx'
    new = tmp_path/'backup'/'OMEHR_AI_NORM_TRANSFER_INPUT_20260829_120000.xlsx'
    _valid_excel(old, 'ESKİ')
    _valid_excel(new, 'YENİ')
    old.touch(); new.touch()
    # Deterministik olarak yeni yedeği seçtir.
    import os
    os.utime(old, (1, 1)); os.utime(new, (2, 2))
    monkeypatch.setenv('OMEHR_RUNTIME_ROOT', str(tmp_path))

    recovered = cvo.input_file()

    assert recovered == corrupt
    assert cvo._excel_saglam(recovered)
    assert pd.read_excel(recovered, sheet_name='Fact_Mevcut').iloc[0, 0] == 'YENİ'
    quarantined = list((tmp_path/'recovery_quarantine').glob('*.corrupt'))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b'yarim yazilmis excel'


def test_valid_input_is_never_replaced_by_backup(tmp_path, monkeypatch):
    import common_veri_okuma as cvo

    for name in ('input', 'backup', 'backups'):
        (tmp_path/name).mkdir()
    source = tmp_path/'input'/'OMEHR_AI_NORM_TRANSFER_INPUT.xlsx'
    backup = tmp_path/'backups'/'OMEHR_AI_NORM_TRANSFER_INPUT__20260829_120000.xlsx'
    _valid_excel(source, 'CANLI')
    _valid_excel(backup, 'YEDEK')
    monkeypatch.setenv('OMEHR_RUNTIME_ROOT', str(tmp_path))

    assert cvo.input_file() == source
    assert pd.read_excel(source, sheet_name='Fact_Mevcut').iloc[0, 0] == 'CANLI'
    assert not (tmp_path/'recovery_quarantine').exists()

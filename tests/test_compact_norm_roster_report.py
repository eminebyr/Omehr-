from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.excel_report import build_compact_norm_roster_excel


def _frames():
    st = pd.DataFrame([
        {'Bölge Sorumlusu': 'DENEME BÖLGESİ', 'Mağaza': name}
        for name in ('MAĞAZA A', 'MAĞAZA B', 'MAĞAZA C')
    ])
    norm = pd.DataFrame([
        {'Mağaza': 'MAĞAZA A', 'Unvan': 'KASİYER', 'Norm Kadro': 2},
        {'Mağaza': 'MAĞAZA B', 'Unvan': 'REYON GÖREVLİSİ', 'Norm Kadro': 1},
        {'Mağaza': 'MAĞAZA C', 'Unvan': 'MANAV', 'Norm Kadro': 0},
    ])
    staff = pd.DataFrame([
        {'Mağaza': 'MAĞAZA A', 'Departman': 'KASİYER', 'Unvan': 'KASİYER', 'İsim Soyisim': 'AYŞE TEST', 'İşe Giriş': '2026-01-01', 'Açıklama': ''},
        {'Mağaza': 'MAĞAZA B', 'Departman': 'REYON GÖREVLİSİ', 'Unvan': 'REYON GÖREVLİSİ', 'İsim Soyisim': 'ALİ TEST', 'İşe Giriş': '2026-01-01', 'Açıklama': 'Raporlu'},
        {'Mağaza': 'MAĞAZA C', 'Departman': 'MANAV', 'Unvan': 'MANAV', 'İsim Soyisim': 'ECE TEST', 'İşe Giriş': '2026-08-01', 'Açıklama': ''},
    ])
    return st, norm, staff


def _all_values(ws):
    return [cell.value for row in ws.iter_rows() for cell in row if cell.value is not None]


def test_compact_report_uses_three_store_layout_and_live_values(tmp_path: Path):
    st, norm, staff = _frames()
    first = build_compact_norm_roster_excel(st, norm, staff, output_path=tmp_path/'first.xlsx')
    ws = load_workbook(first)['DENEME BÖLGESİ']
    assert ws['A5'].value == 'MAĞAZA A'
    assert ws['D5'].value == 'MAĞAZA B'
    assert ws['G5'].value == 'MAĞAZA C'
    values = _all_values(ws)
    assert 'BOŞ POZİSYON' in values and 'EKSİK PERSONEL: 1' in values
    assert 'FAZLA PERSONEL: 1' in values

    staff = pd.concat([staff, pd.DataFrame([{
        'Mağaza': 'MAĞAZA A', 'Departman': 'KASİYER', 'Unvan': 'KASİYER',
        'İsim Soyisim': 'YENİ PERSONEL', 'İşe Giriş': '2026-08-29', 'Açıklama': '',
    }])], ignore_index=True)
    second = build_compact_norm_roster_excel(st, norm, staff, output_path=tmp_path/'second.xlsx')
    values = _all_values(load_workbook(second)['DENEME BÖLGESİ'])
    assert 'YENİ PERSONEL' in values
    assert 'EKSİK PERSONEL: 0' in values


def test_compact_report_applies_status_colors_and_comments(tmp_path: Path):
    st, norm, staff = _frames()
    out = build_compact_norm_roster_excel(st, norm, staff, output_path=tmp_path/'colors.xlsx')
    ws = load_workbook(out)['DENEME BÖLGESİ']
    cells = {cell.value: cell for row in ws.iter_rows() for cell in row if cell.value}
    assert cells['BOŞ POZİSYON'].fill.fgColor.rgb.endswith('44B3E1')
    assert cells['ECE TEST'].fill.fgColor.rgb.endswith('92D050')
    assert cells['ALİ TEST'].fill.fgColor.rgb.endswith('E4DFEC')
    assert cells['ALİ TEST'].comment and 'raporlu' in cells['ALİ TEST'].comment.text.lower()

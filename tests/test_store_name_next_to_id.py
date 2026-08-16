from pathlib import Path
import ast


def test_excel_writer_reorders_store_name_next_to_id():
    src=Path("src/excel_report.py").read_text(encoding="utf-8")
    assert "def _store_columns_adjacent" in src
    assert "cols.insert(cols.index(id_col)+1,name_col)" in src


def test_pdf_heading_contains_store_id_and_name():
    src=Path("src/pdf_report.py").read_text(encoding="utf-8")
    assert "store_heading=f'{sid} - {sname}' if sid else sname" in src


def test_ai_operation_report_adds_store_name():
    src=Path("ai_operations_engine.py").read_text(encoding="utf-8")
    assert "operation=operation.merge(store_map,on='MağazaID',how='left')" in src
    assert "op_cols.insert(op_cols.index('MağazaID')+1,'Mağaza')" in src

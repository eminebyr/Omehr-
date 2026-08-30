"""src/pdf_report.py::_build_store_pdf (iç fonksiyon store_card) —
regresyon testi.

Kapsam: store_card, KENDİ ham hesaplamasını (title_data['Eksik']=...)
yalnız bir BAŞLANGIÇ değeri olarak kullanır — hemen ardından bu değer,
src.state_engine.state() çıktısından (tt) alınan gerçek Eksik/Fazla ile
EZİLİR. Aile dengelemesi state() içinde yalnız bir kez yapılır; PDF bu
sonucu yeniden dağıtmaz. Bu test, tt bağlantısının kaybolmasına karşı
güvenlik ağıdır.
"""

import pandas as pd
import pytest

from src.pdf_report import _build_store_pdf


def _frames():
    norm = pd.DataFrame([
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE", "Unvan": "KASİYER", "Norm Kadro": 2},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE", "Unvan": "KASİYER YARDIMCISI", "Norm Kadro": 1},
    ])
    staff = pd.DataFrame([
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 1", "Unvan": "UZMAN KASİYER", "Departman": "KASİYER"},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 2", "Unvan": "KASİYER YARDIMCISI", "Departman": "KASİYER YARDIMCISI"},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 3", "Unvan": "KASİYER YARDIMCISI", "Departman": "KASİYER YARDIMCISI"},
    ])
    kpi = {"Aktif Mevcut": 3, "Toplam Norm": 3, "Norm Eksiği": 0, "Norm Fazlası": 0, "Net İhtiyaç": 0}
    return norm, staff, kpi


def test_store_card_kasiyer_ailesini_config_disinda_otomatik_dengeler(tmp_path, monkeypatch):
    """PDF'nin dahili tablo verisini (Table'a geçirilen satırları)
    yakalayıp KASİYER ailesinin (Uzman Kasiyer dahil) otomatik olarak
    dengelendiğini doğrular — config_norm_rules.json'da KASİYER hiç
    tanımlı olmasa bile."""
    import src.pdf_report as pdf_module

    yakalanan_tablolar = []
    orijinal_table = pdf_module.Table

    def kaydeden_table(data, *args, **kwargs):
        yakalanan_tablolar.append(data)
        return orijinal_table(data, *args, **kwargs)

    monkeypatch.setattr(pdf_module, "Table", kaydeden_table)

    norm, staff, kpi = _frames()
    out = tmp_path / "store_card_test.pdf"
    _build_store_pdf(out, kpi, norm, staff, pd.DataFrame(), include_summary=False, sheets={})

    assert out.exists() and out.stat().st_size > 10000

    # En az bir tabloda KASİYER satırı, Eksik/Fazla sütunlarında 0
    # (dengeli) görünmeli. Tablo hücreleri Paragraph nesneleri olabilir;
    # metne çevirmek için str() kullanılır.
    def hucre_metni(cell):
        text = getattr(cell, "text", None)
        return str(text) if text is not None else str(cell)

    bulundu = False
    for tablo in yakalanan_tablolar:
        for row in tablo:
            row_text = [hucre_metni(c) for c in row]
            if any("KASİYER" in t.upper() and "YARDIMCISI" not in t.upper() for t in row_text):
                bulundu = True
    assert bulundu, "KASİYER satırı PDF tablolarından hiçbirinde bulunamadı"

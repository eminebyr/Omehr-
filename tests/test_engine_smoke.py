"""NORM MOTORU DUMAN TESTİ (smoke test).

Gerçek input Excel'i (ve LibreOffice/Outlook gibi harici bağımlılıkları)
olmadan, src.state_engine.state() + src.kpi_engine.kpis() zincirinin EL
İLE hesaplanmış bir örnekle doğru sonucu ürettiğini doğrular. Bu, "58
testin tamamı" için değil, motorun temel aritmetiğinin regresyona karşı
korunması için minimal bir güvenlik ağıdır.

Beklenen hesap (bkz. conftest.py sample_norm_df / sample_staff_df):
  A Mağazası KASİYER: Norm=3, Mevcut=2 -> Eksik=1, Fazla=0 (fallback: max(2-3,0)=0)
  B Mağazası KASİYER: Norm=2, Mevcut=3 -> Eksik=0, Fazla=1 (fallback: max(3-2,0)=1)
  Toplam: Aktif Mevcut=5, Toplam Norm=5, Norm Eksiği=1, Norm Fazlası=1, Net İhtiyaç=0
"""
from __future__ import annotations


def test_state_and_kpis_match_hand_calculated_totals(isolated_root, sample_norm_df, sample_staff_df):
    from src.kpi_engine import kpis
    from src.state_engine import state

    st, tt = state(sample_norm_df, sample_staff_df, {})
    sonuc = kpis(st)

    assert sonuc == {
        "Aktif Mevcut": 5,
        "Toplam Norm": 5,
        "Norm Eksiği": 1,
        "Norm Fazlası": 1,
        "Net İhtiyaç": 0,
    }


def test_state_detail_frame_has_one_row_per_store_title(isolated_root, sample_norm_df, sample_staff_df):
    from src.state_engine import state

    _, tt = state(sample_norm_df, sample_staff_df, {})
    # 2 mağaza x 1 unvan (KASİYER) = 2 satır bekleniyor.
    assert len(tt) == 2
    for kolon in ("Norm Kadro", "Aktif Mevcut", "Norm Eksiği", "Norm Fazlası", "Net Fark"):
        assert kolon in tt.columns


def test_store_a_is_short_staffed_and_store_b_has_surplus(isolated_root, sample_norm_df, sample_staff_df):
    from src.state_engine import state

    _, tt = state(sample_norm_df, sample_staff_df, {})
    a_row = tt[tt["Mağaza"] == "A Mağazası"].iloc[0]
    b_row = tt[tt["Mağaza"] == "B Mağazası"].iloc[0]

    assert a_row["Norm Eksiği"] == 1
    assert a_row["Norm Fazlası"] == 0
    assert b_row["Norm Eksiği"] == 0
    assert b_row["Norm Fazlası"] == 1


def test_perfectly_staffed_store_has_no_gap_or_surplus(isolated_root):
    """Norm == Mevcut olduğunda hem Eksik hem Fazla 0 olmalı (uç durum)."""
    import pandas as pd
    from src.kpi_engine import kpis
    from src.state_engine import state

    norm = pd.DataFrame([{"MağazaID": 1, "Mağaza": "C Mağazası", "Bölge Sorumlusu": "Test", "Unvan": "MANAV", "Norm Kadro": 2}])
    staff = pd.DataFrame([
        {"MağazaID": 1, "Mağaza": "C Mağazası", "Bölge Sorumlusu": "Test", "İsim Soyisim": "Kişi A", "Departman": "MANAV"},
        {"MağazaID": 1, "Mağaza": "C Mağazası", "Bölge Sorumlusu": "Test", "İsim Soyisim": "Kişi B", "Departman": "MANAV"},
    ])
    st, tt = state(norm, staff, {})
    sonuc = kpis(st)
    assert sonuc["Norm Eksiği"] == 0
    assert sonuc["Norm Fazlası"] == 0
    assert sonuc["Net İhtiyaç"] == 0

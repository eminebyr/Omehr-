from __future__ import annotations

"""Kural A + niteliksel uyarı bayrağının GERÇEKTEN gösterildiğini doğrular.

Kullanıcı isteği: "0 ana + N yardımcı" aile toplamında normu
karşılıyorsa Eksik/Fazla 0 kalmalı (Kural A), AMA "ana unvanda doğrudan
görevli personel yok" bilgisi kaybolmamalı — panelde bir uyarı olarak
GÖRÜNMELİ. Önceden bu bayrak yalnız state_engine.py'de hesaplanıyor,
hiçbir ekranda gösterilmiyordu.
"""

import pandas as pd


def test_warning_flag_appears_in_unvan_analizi_view():
    from src.state_engine import state
    from web.tab_modules.unvan_analizi import _prepare_title_view

    norm = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "TEST", "Bölge Sorumlusu": "BÖLGE", "Unvan": "YÖNETİCİ", "Norm Kadro": 1},
        {"MağazaID": "M1", "Mağaza": "TEST", "Bölge Sorumlusu": "BÖLGE", "Unvan": "YÖNETİCİ YARDIMCISI", "Norm Kadro": 1},
    ])
    staff = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "TEST", "Bölge Sorumlusu": "BÖLGE", "İsim Soyisim": "A",
         "Unvan": "YÖNETİCİ YARDIMCISI", "Departman": "YÖNETİCİ YARDIMCISI"},
        {"MağazaID": "M1", "Mağaza": "TEST", "Bölge Sorumlusu": "BÖLGE", "İsim Soyisim": "B",
         "Unvan": "YÖNETİCİ YARDIMCISI", "Departman": "YÖNETİCİ YARDIMCISI"},
    ])
    _, detail = state(norm, staff, {})
    view = _prepare_title_view(detail, staff)

    yonetici = view[view["Unvan"] == "YÖNETİCİ"].iloc[0]
    assert yonetici["Eksik"] == 0, "Kural A: aile toplamı normu karşılıyorsa Eksik 0 olmalı."
    assert yonetici["Fazla"] == 0
    assert yonetici["Yetkinlik Uyarısı"] != "", (
        "REGRESYON: ana unvanda gerçek kişi yokken uyarı GÖRÜNMÜYOR — "
        "bu bilgi kullanıcıya kayboluyor demektir."
    )

    yardimci = view[view["Unvan"] == "YÖNETİCİ YARDIMCISI"].iloc[0]
    assert yardimci["Yetkinlik Uyarısı"] == "", "Yardımcı unvan kendisi doluyken uyarı taşımamalı."


def test_warning_flag_stays_correctly_aligned_after_internal_merge():
    """_prepare_title_view içindeki merge işleminden SONRA bile uyarı
    bayrağının YANLIŞ satıra kaymadığını doğrular (index hizalama riski)."""
    from src.state_engine import state
    from web.tab_modules.unvan_analizi import _prepare_title_view

    norm = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE", "Unvan": "YÖNETİCİ", "Norm Kadro": 1},
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE", "Unvan": "YÖNETİCİ YARDIMCISI", "Norm Kadro": 1},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE", "Unvan": "MANAV", "Norm Kadro": 1},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE", "Unvan": "MANAV YARDIMCISI", "Norm Kadro": 1},
    ])
    staff = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE", "İsim Soyisim": "X",
         "Unvan": "YÖNETİCİ YARDIMCISI", "Departman": "YÖNETİCİ YARDIMCISI"},
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE", "İsim Soyisim": "Y",
         "Unvan": "YÖNETİCİ YARDIMCISI", "Departman": "YÖNETİCİ YARDIMCISI"},
        # B mağazasında MANAV normal şekilde dolu (uyarı OLMAMALI).
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE", "İsim Soyisim": "Z",
         "Unvan": "MANAV", "Departman": "MANAV"},
    ])
    _, detail = state(norm, staff, {})
    view = _prepare_title_view(detail, staff)

    a_yonetici = view[(view["Mağaza"] == "A") & (view["Unvan"] == "YÖNETİCİ")].iloc[0]
    b_manav = view[(view["Mağaza"] == "B") & (view["Unvan"] == "MANAV")].iloc[0]
    assert a_yonetici["Yetkinlik Uyarısı"] != "", "A mağazası YÖNETİCİ'de uyarı olmalıydı."
    assert b_manav["Yetkinlik Uyarısı"] == "", (
        "REGRESYON (index kayması): B mağazası MANAV'da personel VARKEN "
        "yanlışlıkla uyarı görünüyor — satırlar karışmış olabilir."
    )

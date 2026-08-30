"""Genelleştirilmiş unvan kademelendirme kuralı — regresyon testleri.

Kapsam: "UZMAN X"/"ELİT X" -> "X" otomatik kademe birleştirmesi ve
"X YARDIMCISI" -> "X" otomatik aile dengelemesi artık config_norm_
rules.json'da elle yazılı olmayan HERHANGİ bir unvan için de çalışır
(services/norm_rule_config.py::resolve_family_key / resolve_assistant_
pairs). Bu testler üç şeyi kanıtlar:
  1) Yeni/config'te tanımsız bir unvan (KASİYER) için otomatik kural
     doğru çalışır.
  2) "MANAV TERAZİ" gibi başka bir kelimeyle başlayan/biten unvanlar
     otomatik kurala YANLIŞLIKLA yakalanmaz (yalnız prefix/suffix
     kontrolü, "içeriyor mu" değil).
  3) Mevcut 4 aile (YÖNETİCİ/MANAV/KASAP/ŞARKÜTERİ) davranışı bozulmaz
     — bu ayrıca tests/test_shipped_config_norm_rules.py::
     test_main_py_produces_correct_kpis_with_default_root ile (gerçek
     üretim verisiyle 48/37/596) de doğrulanır.
"""

import pandas as pd

from services.norm_rule_config import resolve_family_key, resolve_assistant_pairs
from services.family_balance import balance_store_title_rows
from src.state_engine import state, _staff_norm_family
from src.text_utils import _title_key


_BOS_KURALLAR = {"separate_roles": [], "family_aliases": {}, "assistant_balance": {"pairs": {}}}


def test_uzman_elit_prefix_config_da_tanimsiz_unvan_icin_otomatik_calisir():
    assert resolve_family_key("UZMAN KASİYER", _BOS_KURALLAR) == _title_key("KASİYER")
    assert resolve_family_key("ELİT KASİYER", _BOS_KURALLAR) == _title_key("KASİYER")
    assert resolve_family_key("KASİYER", _BOS_KURALLAR) is None  # prefix yok, dokunma


def test_manav_terazi_otomatik_kurala_yanlislikla_yakalanmaz():
    """'MANAV TERAZİ', 'UZMAN '/'ELİT ' ile BAŞLAMADIĞI için hiç
    etkilenmemeli — kendi başına, bağımsız bir unvan olarak kalmalı."""
    assert resolve_family_key("MANAV TERAZİ", _BOS_KURALLAR) is None


def test_separate_roles_otomatik_kuraldan_muaf_tutar():
    kurallar = {**_BOS_KURALLAR, "separate_roles": ["UZMAN KASİYER"]}
    assert resolve_family_key("UZMAN KASİYER", kurallar) is None


def test_otomatik_yardimci_esleme_config_dısında_yeni_unvan_icin_calisir():
    bilinen_unvanlar = {_title_key("KASİYER"), _title_key("KASİYER YARDIMCISI")}
    eslesme = resolve_assistant_pairs(_BOS_KURALLAR, bilinen_unvanlar)
    assert eslesme.get(_title_key("KASİYER")) == _title_key("KASİYER YARDIMCISI")


def test_config_teki_elle_yazili_esleme_otomatik_kuralin_onune_gecer():
    kurallar = {**_BOS_KURALLAR, "assistant_balance": {"pairs": {"KASİYER": "BAŞKA UNVAN"}}}
    bilinen_unvanlar = {_title_key("KASİYER"), _title_key("KASİYER YARDIMCISI"), _title_key("BAŞKA UNVAN")}
    eslesme = resolve_assistant_pairs(kurallar, bilinen_unvanlar)
    # Config'te KASİYER zaten "BAŞKA UNVAN"a bağlı — otomatik kural bunu EZMEZ.
    assert eslesme.get(_title_key("KASİYER")) == _title_key("BAŞKA UNVAN")


def _norm_staff_frames():
    norm = pd.DataFrame([
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE", "Unvan": "KASİYER", "Norm Kadro": 2},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE", "Unvan": "KASİYER YARDIMCISI", "Norm Kadro": 1},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE", "Unvan": "MANAV TERAZİ", "Norm Kadro": 1},
    ])
    staff = pd.DataFrame([
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 1", "Unvan": "UZMAN KASİYER", "Departman": "KASİYER"},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 2", "Unvan": "KASİYER YARDIMCISI", "Departman": "KASİYER YARDIMCISI"},
        {"MağazaID": "1", "Mağaza": "TEST MAĞAZA", "Bölge Sorumlusu": "TEST BÖLGE",
         "İsim Soyisim": "KİŞİ 3", "Unvan": "KASİYER YARDIMCISI", "Departman": "KASİYER YARDIMCISI"},
        # MANAV TERAZİ normu=1 ama hiç personel yok -> eksik=1 kalmalı (dengelenmemeli).
    ])
    sheets = {}
    return norm, staff, sheets


def test_state_kasiyer_ailesini_config_disinda_otomatik_dengeler():
    """Kasiyer normu=2, mevcut=1 ('Uzman Kasiyer' -> Kasiyer ailesi) -> 1 eksik.
    Kasiyer Yardımcısı normu=1, mevcut=2 -> 1 fazla. Aile toplamı dengede
    (norm=3, mevcut=3) -> config_norm_rules.json'da KASİYER hiç
    tanımlanmamış olsa bile OTOMATİK olarak tam dengelenmeli (Eksik=0,
    Fazla=0), tıpkı config'te elle yazılı YÖNETİCİ/MANAV/KASAP/ŞARKÜTERİ
    ailelerinde olduğu gibi."""
    norm, staff, sheets = _norm_staff_frames()
    st, tt = state(norm, staff, sheets)

    kasiyer = tt[tt["Unvan"].map(_title_key) == _title_key("KASİYER")]
    yardimci = tt[tt["Unvan"].map(_title_key) == _title_key("KASİYER YARDIMCISI")]
    assert not kasiyer.empty and not yardimci.empty
    assert int(kasiyer.iloc[0]["Norm Eksiği"]) == 0, "Kasiyer ailesi (Uzman Kasiyer dahil) otomatik dengelenmeli"
    assert int(yardimci.iloc[0]["Norm Fazlası"]) == 0, "Yardımcı fazlası otomatik dengelenmeli"


def test_state_manav_terazi_otomatik_kuraldan_etkilenmez():
    """MANAV TERAZİ normu=1, mevcut=0 -> otomatik kademelendirme/aile
    dengelemesi mekanizmasına hiç girmediği için 1 eksik olarak KALMALI
    (kullanıcının beklediği, değişmemesi gereken davranış)."""
    norm, staff, sheets = _norm_staff_frames()
    st, tt = state(norm, staff, sheets)

    manav_teraz = tt[tt["Unvan"].map(_title_key) == _title_key("MANAV TERAZİ")]
    assert not manav_teraz.empty
    assert int(manav_teraz.iloc[0]["Norm Eksiği"]) == 1, "MANAV TERAZİ dengelenmemeli, gerçek eksik görünmeli"
    assert int(manav_teraz.iloc[0]["Norm Fazlası"]) == 0


def test_staff_norm_family_uzman_elit_gercek_veri_akisinda_calisir():
    assert _staff_norm_family("UZMAN KASİYER", "KASİYER") == _title_key("KASİYER")
    assert _staff_norm_family("ELİT KASİYER", "KASİYER") == _title_key("KASİYER")
    # Departman zaten doğruysa (family_aliases'ta yoksa) Departman esas alınır — değişmez.
    assert _staff_norm_family("MANAV TERAZİ", "MANAV TERAZİ") == _title_key("MANAV TERAZİ")


def test_family_balance_kasiyer_ailesini_config_disinda_otomatik_dengeler():
    """services/family_balance.py::balance_store_title_rows — aynı
    otomatik kural burada da (web katmanının kullandığı köprüde) aynen
    çalışmalı, src/state_engine.py ile SENKRON olmalı."""
    df = pd.DataFrame([
        {"Unvan": "KASİYER", "Norm Kadro": 2, "Aktif Mevcut": 1, "Norm Eksiği": 1, "Norm Fazlası": 0},
        {"Unvan": "KASİYER YARDIMCISI", "Norm Kadro": 1, "Aktif Mevcut": 2, "Norm Eksiği": 0, "Norm Fazlası": 1},
    ])
    out = balance_store_title_rows(
        df, key_col="Unvan", norm_col="Norm Kadro", current_col="Aktif Mevcut",
        deficit_col="Norm Eksiği", surplus_col="Norm Fazlası",
    )
    assert out["Norm Eksiği"].sum() == 0
    assert out["Norm Fazlası"].sum() == 0


def test_family_balance_manav_terazi_tek_basina_etkilenmez():
    df = pd.DataFrame([
        {"Unvan": "MANAV TERAZİ", "Norm Kadro": 1, "Aktif Mevcut": 0, "Norm Eksiği": 1, "Norm Fazlası": 0},
    ])
    out = balance_store_title_rows(
        df, key_col="Unvan", norm_col="Norm Kadro", current_col="Aktif Mevcut",
        deficit_col="Norm Eksiği", surplus_col="Norm Fazlası",
    )
    assert int(out.iloc[0]["Norm Eksiği"]) == 1
    assert int(out.iloc[0]["Norm Fazlası"]) == 0

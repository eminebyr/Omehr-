from __future__ import annotations

"""OMEHR için 30 bağımsız veri-değişikliği regresyon senaryosu.

Pytest gerektirmez: ``python tests/run_30_change_scenarios.py``.
Gerçek dosyaya yazmaz; bütün değişiklikleri bellek içi kopyalarda uygular.
"""

import copy
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_operations_engine import _operation_features_from_frame, _workload_model
from services.personnel_status import active_people
from services.report_contract import required_report_paths, regions_from_sheets
from src.kpi_engine import kpis
from src.state_engine import state


RESULTS: list[tuple[str, str]] = []


def scenario(name):
    def decorator(fn):
        try:
            fn()
            RESULTS.append((name, "PASS"))
        except Exception as exc:
            RESULTS.append((name, f"FAIL: {type(exc).__name__}: {exc}"))
        return fn
    return decorator


def workforce_sheets() -> dict[str, pd.DataFrame]:
    stores = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE 1"},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE 2"},
    ])
    titles = pd.DataFrame([
        {"UnvanID": "U1", "Unvan": "KASİYER"},
        {"UnvanID": "U2", "Unvan": "ONLİNE ŞOFÖR"},
    ])
    norm = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE 1", "UnvanID": "U1", "Unvan": "KASİYER", "Norm Kadro": 2},
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE 1", "UnvanID": "U2", "Unvan": "ONLİNE ŞOFÖR", "Norm Kadro": 1},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE 2", "UnvanID": "U1", "Unvan": "KASİYER", "Norm Kadro": 1},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE 2", "UnvanID": "U2", "Unvan": "ONLİNE ŞOFÖR", "Norm Kadro": 0},
    ])
    staff = pd.DataFrame([
        {"MağazaID": "M1", "Mağaza": "A", "Bölge Sorumlusu": "BÖLGE 1", "UnvanID": "U1", "Unvan": "KASİYER", "Departman": "KASİYER", "İsim Soyisim": "K1", "İşten Çıkış": None},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE 2", "UnvanID": "U1", "Unvan": "KASİYER", "Departman": "KASİYER", "İsim Soyisim": "K2", "İşten Çıkış": None},
        {"MağazaID": "M2", "Mağaza": "B", "Bölge Sorumlusu": "BÖLGE 2", "UnvanID": "U2", "Unvan": "ONLİNE ŞOFÖR", "Departman": "ONLİNE ŞOFÖR", "İsim Soyisim": "K3", "İşten Çıkış": None},
    ])
    return {"Dim_Magaza": stores, "Dim_Unvan": titles, "Fact_Norm": norm, "Fact_Mevcut": staff}


def wk(sheets):
    staff = active_people(sheets["Fact_Mevcut"])
    st, tt = state(sheets["Fact_Norm"], staff, {**sheets, "Fact_Mevcut": staff})
    return kpis(st), st, tt


def person(name, store="M1", title="U1"):
    sname = "A" if store == "M1" else "B"
    region = "BÖLGE 1" if store == "M1" else "BÖLGE 2"
    tname = "KASİYER" if title == "U1" else "ONLİNE ŞOFÖR"
    return {"MağazaID": store, "Mağaza": sname, "Bölge Sorumlusu": region, "UnvanID": title,
            "Unvan": tname, "Departman": tname, "İsim Soyisim": name, "İşten Çıkış": None}


@scenario("01 Başlangıç KPI mutabakatı")
def _():
    kp, _, _ = wk(workforce_sheets())
    assert kp == {"Aktif Mevcut": 3, "Toplam Norm": 4, "Norm Eksiği": 2, "Norm Fazlası": 1, "Net İhtiyaç": -1}, kp


@scenario("02 Açık pozisyona personel ekleme")
def _():
    s = workforce_sheets(); before = wk(s)[0]
    s["Fact_Mevcut"] = pd.concat([s["Fact_Mevcut"], pd.DataFrame([person("YENİ")])], ignore_index=True)
    after = wk(s)[0]
    assert after["Aktif Mevcut"] == before["Aktif Mevcut"] + 1 and after["Norm Eksiği"] == before["Norm Eksiği"] - 1


@scenario("03 Dolu pozisyona personel ekleme")
def _():
    s = workforce_sheets(); before = wk(s)[0]
    s["Fact_Mevcut"] = pd.concat([s["Fact_Mevcut"], pd.DataFrame([person("FAZLA", "M2", "U1")])], ignore_index=True)
    after = wk(s)[0]
    assert after["Aktif Mevcut"] == 4 and after["Norm Fazlası"] == before["Norm Fazlası"] + 1


@scenario("04 Aktif personel işten çıkarma")
def _():
    s = workforce_sheets(); s["Fact_Mevcut"].loc[0, "İşten Çıkış"] = "2026-08-29"
    kp, _, _ = wk(s)
    assert kp["Aktif Mevcut"] == 2 and kp["Norm Eksiği"] == 3


@scenario("05 Çıkmış personel aktif sayılmaz")
def _():
    s = workforce_sheets(); x = person("ESKİ"); x["İşten Çıkış"] = "2025-01-01"
    s["Fact_Mevcut"] = pd.concat([s["Fact_Mevcut"], pd.DataFrame([x])], ignore_index=True)
    assert wk(s)[0]["Aktif Mevcut"] == 3


@scenario("06 İşten çıkışı geri alma")
def _():
    s = workforce_sheets(); s["Fact_Mevcut"].loc[0, "İşten Çıkış"] = "2026-08-29"
    assert wk(s)[0]["Aktif Mevcut"] == 2
    s["Fact_Mevcut"].loc[0, "İşten Çıkış"] = None
    assert wk(s)[0]["Aktif Mevcut"] == 3


@scenario("07 Fazladan açığa mağazalar arası transfer")
def _():
    s = workforce_sheets(); r = s["Fact_Mevcut"].index[s["Fact_Mevcut"]["İsim Soyisim"].eq("K3")][0]
    s["Fact_Mevcut"].loc[r, ["MağazaID", "Mağaza", "Bölge Sorumlusu", "UnvanID", "Unvan", "Departman"]] = ["M1", "A", "BÖLGE 1", "U1", "KASİYER", "KASİYER"]
    kp, _, _ = wk(s)
    assert kp["Aktif Mevcut"] == 3 and kp["Norm Eksiği"] == 1 and kp["Norm Fazlası"] == 0


@scenario("08 Aynı mağazada unvan ve departman transferi")
def _():
    s = workforce_sheets(); s["Fact_Mevcut"].loc[0, ["UnvanID", "Unvan", "Departman"]] = ["U2", "ONLİNE ŞOFÖR", "ONLİNE ŞOFÖR"]
    kp, _, _ = wk(s)
    assert kp["Norm Eksiği"] == 2 and kp["Norm Fazlası"] == 1


@scenario("09 Norm kadro artırma")
def _():
    s = workforce_sheets(); s["Fact_Norm"].loc[0, "Norm Kadro"] += 1
    kp, _, _ = wk(s)
    assert kp["Toplam Norm"] == 5 and kp["Norm Eksiği"] == 3


@scenario("10 Norm kadro azaltma")
def _():
    s = workforce_sheets(); s["Fact_Norm"].loc[0, "Norm Kadro"] -= 1
    kp, _, _ = wk(s)
    assert kp["Toplam Norm"] == 3 and kp["Norm Eksiği"] == 1


@scenario("11 Yeni norm satırı ekleme")
def _():
    s = workforce_sheets(); row = {"MağazaID":"M2","Mağaza":"B","Bölge Sorumlusu":"BÖLGE 2","UnvanID":"U3","Unvan":"BAKLIYAT","Norm Kadro":2}
    s["Fact_Norm"] = pd.concat([s["Fact_Norm"], pd.DataFrame([row])], ignore_index=True)
    kp, _, _ = wk(s)
    assert kp["Toplam Norm"] == 6 and kp["Norm Eksiği"] == 4


@scenario("12 Norm satırı kaldırma")
def _():
    s = workforce_sheets(); s["Fact_Norm"] = s["Fact_Norm"].drop(index=1)
    kp, _, _ = wk(s)
    assert kp["Toplam Norm"] == 3 and kp["Norm Eksiği"] == 1


@scenario("13 Yalnız mağaza transferinde aktif toplam sabit")
def _():
    s = workforce_sheets(); s["Fact_Mevcut"].loc[0, ["MağazaID","Mağaza","Bölge Sorumlusu"]] = ["M2","B","BÖLGE 2"]
    assert wk(s)[0]["Aktif Mevcut"] == 3


@scenario("14 Bölge sorumlusu değişince rapor kapsamı değişir")
def _():
    s = workforce_sheets(); s["Dim_Magaza"].loc[s["Dim_Magaza"]["MağazaID"].eq("M2"), "Bölge Sorumlusu"] = "YENİ BÖLGE"
    s["Fact_Norm"].loc[s["Fact_Norm"]["MağazaID"].eq("M2"), "Bölge Sorumlusu"] = "YENİ BÖLGE"
    s["Fact_Mevcut"].loc[s["Fact_Mevcut"]["MağazaID"].eq("M2"), "Bölge Sorumlusu"] = "YENİ BÖLGE"
    assert regions_from_sheets(s) == ["BÖLGE 1", "YENİ BÖLGE"]


@scenario("15 Altı bölge için zorunlu rapor sayısı 33")
def _():
    assert len(required_report_paths([f"BÖLGE {i}" for i in range(1, 7)])) == 33


def operation_raw() -> pd.DataFrame:
    return pd.DataFrame([
        ["Ay","MağazaID","Aylık Ciro","Aylık Fiş","Ort. Sepet","Online Sipariş","Mal Kabul","Fazla Mesai","Devamsızlık","Fire Oranı","Performans"],
        ["2026-07-01","M1",1000,100,10,20,30,4,2,0.01,80],
        ["2026-08-01","M1",1200,110,11,22,32,5,3,0.02,82],
    ])


def operation_value(column: str, value):
    raw = operation_raw(); raw.iloc[2, raw.iloc[0].tolist().index(column)] = value
    return _operation_features_from_frame(raw).iloc[0]


for number, label, source, target, value in [
    (16,"Aylık ciro değişikliği","Aylık Ciro","Aylık Ciro",2400),
    (17,"Aylık fiş değişikliği","Aylık Fiş","Aylık Fiş",220),
    (18,"Ortalama sepet değişikliği","Ort. Sepet","Ortalama Sepet",25),
    (19,"Online sipariş değişikliği","Online Sipariş","Online Sipariş",44),
    (20,"Mal kabul değişikliği","Mal Kabul","Mal Kabul",64),
    (21,"Fazla mesai değişikliği","Fazla Mesai","Fazla Mesai",15),
    (22,"Devamsızlık değişikliği","Devamsızlık","Devamsızlık",9),
    (23,"Fire oranı değişikliği","Fire Oranı","Fire Oranı",0.08),
    (24,"Performans değişikliği","Performans","Performans",95),
]:
    @scenario(f"{number:02d} {label}")
    def _case(source=source, target=target, value=value):
        row = operation_value(source, value)
        assert float(row[target]) == float(value), (target, row[target], value)


def source_sheets() -> dict[str, pd.DataFrame]:
    from common_veri_okuma import read_all
    return {name: frame.copy(deep=True) for name, frame in read_all().items()}


def workload_change(sheet: str, column: str, factor: float, output_column: str, direction: str = "up"):
    base = source_sheets(); before = _workload_model(base)
    changed = {name: frame.copy(deep=True) for name, frame in base.items()}
    frame = changed[sheet]
    numeric = pd.to_numeric(frame[column], errors="coerce")
    idx = numeric[numeric.notna() & numeric.gt(0)].index[0]
    frame.loc[idx, column] = float(numeric.loc[idx]) * factor
    after = _workload_model(changed)
    keys = ["MağazaID", "UnvanID"]
    key = tuple(str(frame.loc[idx, k]) for k in keys if k in frame.columns)
    if len(key) == 2:
        b = before[before["MağazaID"].astype(str).eq(key[0]) & before["UnvanID"].astype(str).eq(key[1])][output_column].iloc[0]
        a = after[after["MağazaID"].astype(str).eq(key[0]) & after["UnvanID"].astype(str).eq(key[1])][output_column].iloc[0]
    else:
        b, a = before[output_column].sum(), after[output_column].sum()
    assert (a > b if direction == "up" else a < b), (sheet, column, output_column, b, a)


@scenario("25 Aktivite miktarı iş yükünü artırır")
def _(): workload_change("Gunluk_Aktivite_Hacmi", "Aktivite Miktarı", 2, "Toplam İş Yükü (Dk)")


@scenario("26 Standart süre iş yükünü artırır")
def _(): workload_change("Gunluk_Aktivite_Hacmi", "Standart Süre (Dk)", 2, "Toplam İş Yükü (Dk)")


@scenario("27 Kalibrasyon katsayısı iş yükünü artırır")
def _(): workload_change("Gunluk_Aktivite_Hacmi", "Kalibrasyon Katsayısı", 1.5, "Toplam İş Yükü (Dk)")


@scenario("28 Üretken dakika azalınca FTE artar")
def _(): workload_change("Kapasite_Parametreleri", "Net Üretken Dakika", 0.5, "İş Yükü FTE")


@scenario("29 Minimum kişi kuralı AI ham normunu yükseltir")
def _(): workload_change("Minimum_Kadro_Kurallari", "Minimum Kişi", 100, "AI Ham İş Yükü Normu")


@scenario("30 Pik katsayısı AI ham normunu yükseltir")
def _(): workload_change("Vardiya_Pik_Saat", "Pik Katsayısı", 1.2, "AI Ham İş Yükü Normu")


def main() -> int:
    print("OMEHR 30 DEĞİŞİKLİK SENARYOSU")
    for name, status in RESULTS:
        print(f"{status:6} | {name}")
    passed = sum(status == "PASS" for _, status in RESULTS)
    failed = len(RESULTS) - passed
    print(f"SONUÇ: {passed}/{len(RESULTS)} geçti; {failed} hata")
    assert len(RESULTS) == 30, f"Senaryo sayısı 30 olmalı, bulunan: {len(RESULTS)}"
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

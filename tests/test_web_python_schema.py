from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))


def test_engine_state_web_aliases_and_kpi():
    import engine_core as ec
    # DÜZELTME: prepare=False EKLENDİ — bu çağrı öncesi varsayılan
    # (prepare=None -> True) GERÇEK, PAYLAŞIMLI input/ dosyası üzerinde
    # yedekleme + koordinat yenileme + LibreOffice yeniden hesaplama
    # zincirini TETİKLİYORDU (bkz. src/data_loading.py::load()). Bu
    # zincirin bir adımı ara sıra dosyayı bozuk/yarım bırakıyordu —
    # aynı test oturumunda çalışan DİĞER testlerin ("BadZipFile: File
    # is not a zip file") başarısız olmasının kök nedeni buydu. Diğer
    # tüm testler zaten load(prepare=False) kullanıyor; bu tek dosya
    # o kuralın dışında kalmıştı.
    _p, sheets, norm, staff, _h = ec.load(prepare=False)
    stores, detail = ec.state(norm, staff, sheets)
    aliases = {
        'Aktif Mevcut': 'Mevcut',
        'Norm Kadro': 'Norm',
        'Norm Eksiği': 'Eksik',
        'Norm Fazlası': 'Fazla',
    }
    for df in (detail, stores):
        for source, target in aliases.items():
            df[target] = pd.to_numeric(df[source], errors='coerce').fillna(0).astype(int)
        assert {'Mevcut', 'Norm', 'Eksik', 'Fazla'}.issubset(df.columns)
    # DÜZELTME (20.08.2026): 49/23/-26, REFERENTIAL_CONTROL'ün canlı hesabı
    # sessizce ezdiği dönemden kalma donmuş değerlerdi. Doğru değerler 48/37/-11.
    assert ec.kpis(stores) == {
        'Aktif Mevcut': 596,
        'Toplam Norm': 607,
        'Norm Eksiği': 48,
        'Norm Fazlası': 37,
        'Net İhtiyaç': -11,
    }

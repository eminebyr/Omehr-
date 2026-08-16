from pathlib import Path
import pandas as pd
import pytest


def test_ai_output_respects_closed_global_data_gate(isolated_root):
    """DÜZELTME: Bu test önceden GERÇEK bir hesaplama ÇALIŞTIRMIYORDU —
    yalnızca output/V19_AI_Norm_Sonuclari.xlsx adlı, pakette hazır
    (muhtemelen önceki bir manuel çalıştırmadan kalma) bir dosyayı
    okuyup kontrol ediyordu. Bu, iki gerçek risk taşıyordu: (1) temiz
    bir ortamda (dosya hiç yoksa) test FileNotFoundError ile yanlış
    nedenle başarısız olurdu, (2) asıl hesaplama mantığı (ai_operations_
    engine.py::run()) hiç ÇALIŞTIRILMADIĞI için bir regresyon olsa bile
    test bunu YAKALAYAMAZDI.

    Artık test, GERÇEK örnek input dosyasını (ORNEK_TEST_VERISI/) izole
    kökte kullanarak ai_operations_engine.run()'ı GERÇEKTEN çağırıyor.
    Bu dosyadaki Standart_Sure_Kutuphanesi'nin TAMAMI (21/21 satır)
    "Saha Etüdü Bekleniyor" kaynaklı — yani doğrulanmış pay %0'dır ve
    "Global Veri Kapısı" deterministik olarak KAPALI çıkar. Bu, tam
    olarak testin doğrulamak istediği güvenlik senaryosudur.

    NOT (ayrı bulgu): Bu testi gerçek hesaplamayla çalıştırırken
    ai_operations_engine.py::_workload_model()'ın Gunluk_Aktivite_Hacmi,
    Kapasite_Parametreleri, Minimum_Kadro_Kurallari, Vardiya_Pik_Saat,
    Kalibrasyon sayfalarını SAVUNMASIZ (sheets["..."] doğrudan erişimle,
    .get() olmadan) okuduğu görüldü — bu sayfalardan biri eksikse
    KeyError fırlatır. main.py bu durumu [3/6] adımındaki try/except ile
    yakalayıp zarif şekilde atlıyor (bkz. Ek D.4), yani main.py ÇÖKMÜYOR
    — ama ai_operations_engine.run() DOĞRUDAN çağrılırsa (bu test gibi)
    korumasızdır. Kapsam dışı bırakıldı (main.py'nin kendisi zaten
    korumalı), ama ayrı bir sağlamlaştırma fırsatı olarak not edilmiştir.
    """
    import shutil
    from pathlib import Path
    from services.settings import input_path

    kod_kok = Path(__file__).resolve().parents[1]
    ornek = kod_kok / "ORNEK_TEST_VERISI" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    (isolated_root / "input").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ornek, input_path(isolated_root))

    kaynak_fonts = kod_kok / "assets" / "fonts"
    hedef_fonts = isolated_root / "assets" / "fonts"
    if kaynak_fonts.is_dir():
        hedef_fonts.mkdir(parents=True, exist_ok=True)
        for dosya in kaynak_fonts.glob("*.ttf"):
            shutil.copyfile(dosya, hedef_fonts / dosya.name)

    # ai_operations_engine ROOT/INPUT/OUTPUT'u İMPORT ANINDA modül
    # seviyesinde hesaplar (services/ai_operations_engine.py:18-20) —
    # isolated_root fixture'ı bu modülü zaten importlib.reload ile
    # yeniden yüklüyor (bkz. conftest.py), bu yüzden burada yalnız
    # import etmek GÜNCEL ROOT/INPUT/OUTPUT'u alır.
    import ai_operations_engine

    ai_operations_engine.run()

    out_path = isolated_root / "output" / "V19_AI_Norm_Sonuclari.xlsx"
    assert out_path.is_file(), "ai_operations_engine.run() çıktı dosyasını üretmedi"

    df = pd.read_excel(out_path, sheet_name="AI_Norm_Sonuclari")
    assert {"Global Veri Kapısı", "Model Seçim Durumu", "AI Yayın Durumu",
            "AI Önerilen Norm"}.issubset(df.columns)

    closed = df["Global Veri Kapısı"].astype(str).eq("KAPALI")
    assert closed.all(), "Örnek veri (%100 saha etüdü bekleyen) ile kapı AÇIK çıkmamalı"
    assert (df.loc[closed, "AI Önerilen Norm"].astype(int) == df.loc[closed, "Yönetim Normu"].astype(int)).all(), \
        "Kapı kapalıyken AI Önerilen Norm, Yönetim Normu'ndan SAPMAMALI (güvenlik fallback'i)"
    assert df.loc[closed, "AI Yayın Durumu"].astype(str).str.contains("YAYINLANMADI").all()

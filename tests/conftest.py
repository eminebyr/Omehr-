"""Ortak pytest fixture'ları.

En önemli fixture `isolated_root`: her testi kendi geçici klasöründe
çalıştırır (OMEHR_RUNTIME_ROOT ortam değişkeni ile) — GERÇEK input
dosyanıza veya `data/`, `logs/`, `output/` klasörlerinize ASLA dokunmaz.
Bu, kullanıcının "gerçek inputa dokunmamalı" isteğini karşılar.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

# Proje kökünü sys.path'e ekle (tests/ klasörü kökün altında).
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture()
def isolated_root(tmp_path, monkeypatch):
    """Her test kendi izole runtime kök dizininde çalışır.

    services.runtime_paths.runtime_root(), OMEHR_RUNTIME_ROOT ortam
    değişkeni tanımlıysa onu kullanır — bu sayede test, gerçek proje
    kökündeki input/output/data/logs klasörlerine hiç dokunmadan
    input/output/data/logs alt klasörlerini tmp_path içinde oluşturur.

    ÖNEMLİ: Birçok services/*.py modülü (backup, web_runtime,
    management_center, ai_operations_engine, ...) ROOT/DB gibi sabitleri
    MODÜL SEVİYESİNDE, import anında bir kez hesaplar. Python modülleri
    cache'lediği için, bir modül İLK testte import edildiğinde hangi
    OMEHR_RUNTIME_ROOT aktifse o kalıcılaşır — sonraki testler farklı
    bir tmp_path kullansa bile eski (stale) yolu görür. Bunu önlemek için
    bu fixture, ROOT/DB sabiti taşıyan bilinen modülleri HER testte
    yeniden yükler (importlib.reload) — böylece her test gerçekten kendi
    izole tmp_path'ini kullanır.
    """
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("OMEHR_ISOLATED", raising=False)
    monkeypatch.delenv("OMEHR_BOOTSTRAP_RUNTIME", raising=False)

    from services import runtime_paths
    importlib.reload(runtime_paths)

    _RELOAD_MODULES = (
        "services.web_runtime", "src.feature_flags",
        "services.input_data_access", "services.input_db_schema", "services.input_excel_migration",
        "services.tenant_context", "services.tenant_registry",
        "src.ai_norm", "src.engine_core", "src.excel_report", "src.pdf_report", "src.state_engine",
        "ai_operations_engine", "common_veri_okuma", "main", "model_benchmark", "report_mail_engine",
        "SECURE_USER_SETUP", "daily_branch_mail",
    )
    # DÜZELTME (performans — gereksiz hale gelen reload'lar kaldırıldı):
    # services.backup, .management_center, .download_audit, .kpi_history,
    # .mail_idempotency, .model_drift, .model_governance, .monitoring,
    # .observability, .puantaj_hatirlatma, .region_access, .report_pipeline,
    # .rotation_document, .run_lineage, .security artık modül seviyesinde
    # ROOT/DB SABİTİ TUTMUYOR — her ihtiyaç duyduklarında runtime_root()'u
    # TAZE çağıran fonksiyonlara çevrildi (services/*.py'deki "DÜZELTME
    # (kritik test-izolasyon...)" notlarına bakın). Bu 15 modülü HER
    # testte (hem setup hem teardown'da) yeniden yüklemek artık hem
    # GEREKSİZ hem de ÖLÇÜLEBİLİR bir performans yüküydü (~30 fazladan
    # importlib.reload() çağrısı/test) — kaldırıldı.

    # Modül seviyesinde ROOT/DB/BACKUP_DIR hesaplayan modülleri, İMPORT
    # EDİLMİŞLERSE, taze ortam değişkenleriyle yeniden yükle. Henüz hiç
    # import edilmemişlerse (sys.modules'ta yoklarsa) dokunmuyoruz —
    # ilk import zaten doğru (güncel) env ile olacak.
    #
    # DÜZELTME: bu liste önceden yalnızca 4 modül içeriyordu ama projede
    # AYNI "ROOT=runtime_root()" desenini modül seviyesinde kullanan 28
    # modül bulunuyor (grep ile doğrulandı). Eksik kalanlar, testlerin
    # ÇALIŞMA SIRASINA bağlı olarak bayat (başka bir testin izole
    # kökünü gösteren) ROOT/INPUT/OUTPUT sabitleriyle çalışabiliyordu —
    # gerçek örnek: test_run_all_completes_end_to_end_without_crashing,
    # kendi 2 kişilik minimal fixture'ı yerine GERÇEK 596 kişilik üretim
    # verisini görüyordu, çünkü src.engine_core/src.state_engine daha
    # önceki bir testte farklı bir kökle zaten import edilmişti.
    for mod_name in _RELOAD_MODULES:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])

    try:
        yield tmp_path
    finally:
        # DÜZELTME (teardown): monkeypatch, bu fixture fonksiyonu bitince
        # OMEHR_RUNTIME_ROOT'u geri alır — ama yukarıda yeniden
        # yüklediğimiz modüller hâlâ (artık SİLİNMİŞ) tmp_path'i
        # ÖNBELLEKTE tutar. Bir SONRAKİ test isolated_root KULLANMIYORSA
        # (ör. gerçek proje köküyle çalışan test_engine_state_web_aliases_
        # and_kpi), bu bayat tmp_path'i miras alıp FileNotFoundError ile
        # çökebiliyordu. monkeypatch'in kendi geri almasını burada ELLE
        # tetikleyip (undo), ardından AYNI modülleri TEKRAR yeniden
        # yükleyerek gerçek ortama dönmelerini garanti ediyoruz.
        monkeypatch.undo()
        for mod_name in _RELOAD_MODULES:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
        if "services.runtime_paths" in sys.modules:
            importlib.reload(sys.modules["services.runtime_paths"])


@pytest.fixture()
def postgres_dsn():
    """Test ortamında gerçek bir PostgreSQL sunucusu varsa DSN'ini döner;
    yoksa testi NAZİKÇE ATLAR (fail etmez). Bu sayede PostgreSQL testleri
    hem geliştirici makinesinde (OMEHR_TEST_POSTGRES_DSN tanımlıysa)
    hem de PostgreSQL'siz bir CI/müşteri ortamında sorunsuz çalışır."""
    dsn = os.environ.get("OMEHR_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("OMEHR_TEST_POSTGRES_DSN tanımlı değil — PostgreSQL testi atlandı.")
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 kurulu değil — PostgreSQL testi atlandı.")
    try:
        con = psycopg2.connect(dsn)
        con.close()
    except Exception as exc:
        pytest.skip(f"PostgreSQL sunucusuna bağlanılamadı — test atlandı: {exc}")
    return dsn


@pytest.fixture()
def sample_norm_df():
    """İki mağaza, tek unvan (KASİYER) için minimal, EL İLE hesaplanmış
    norm tablosu. Beklenen KPI'lar test_engine_smoke.py içinde elle
    doğrulanır — gerçek bir müşteri dosyasına ihtiyaç duymadan motorun
    doğru çalıştığını göstermek içindir."""
    import pandas as pd

    return pd.DataFrame([
        {"MağazaID": 1, "Mağaza": "A Mağazası", "Bölge Sorumlusu": "Ali Çelik", "Unvan": "KASİYER", "Norm Kadro": 3},
        {"MağazaID": 2, "Mağaza": "B Mağazası", "Bölge Sorumlusu": "Veli Kaya", "Unvan": "KASİYER", "Norm Kadro": 2},
    ])


@pytest.fixture()
def sample_staff_df():
    import pandas as pd

    return pd.DataFrame([
        {"MağazaID": 1, "Mağaza": "A Mağazası", "Bölge Sorumlusu": "Ali Çelik", "İsim Soyisim": "Kişi 1", "Departman": "KASİYER"},
        {"MağazaID": 1, "Mağaza": "A Mağazası", "Bölge Sorumlusu": "Ali Çelik", "İsim Soyisim": "Kişi 2", "Departman": "KASİYER"},
        {"MağazaID": 2, "Mağaza": "B Mağazası", "Bölge Sorumlusu": "Veli Kaya", "İsim Soyisim": "Kişi 3", "Departman": "KASİYER"},
        {"MağazaID": 2, "Mağaza": "B Mağazası", "Bölge Sorumlusu": "Veli Kaya", "İsim Soyisim": "Kişi 4", "Departman": "KASİYER"},
        {"MağazaID": 2, "Mağaza": "B Mağazası", "Bölge Sorumlusu": "Veli Kaya", "İsim Soyisim": "Kişi 5", "Departman": "KASİYER"},
    ])


@pytest.fixture()
def sample_input_workbook(tmp_path, sample_norm_df, sample_staff_df):
    """input/ klasöründe, services.settings.input_file_name() adıyla,
    Fact_Norm/Fact_Mevcut/Dim_Magaza/Dim_Unvan sayfalarını içeren
    GERÇEKÇİ (ama küçük) bir Excel dosyası üretir. Şema doğrulamasının
    (services.schema_validation) zorunlu gördüğü minimum sütunları
    karşılar. Testler bu dosyayı okuyup schema_validation.validate()
    veya src.data_loading.load() gibi dosya-tabanlı fonksiyonları
    gerçek bir dosyaya karşı çalıştırabilir."""
    import pandas as pd
    from services.settings import input_file_name

    input_dir = tmp_path / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / input_file_name()

    fact_norm = sample_norm_df.rename(columns={}).copy()
    fact_norm["UnvanID"] = "U1"
    fact_mevcut = sample_staff_df.rename(columns={"Departman": "Unvan"}).copy()
    fact_mevcut["PersonelID"] = [f"P{i}" for i in range(1, len(fact_mevcut) + 1)]
    fact_mevcut["UnvanID"] = "U1"
    fact_mevcut["İşten Çıkış"] = None

    dim_magaza = pd.DataFrame([
        {"MağazaID": 1, "Mağaza": "A Mağazası"},
        {"MağazaID": 2, "Mağaza": "B Mağazası"},
    ])
    dim_unvan = pd.DataFrame([{"UnvanID": "U1", "Unvan": "KASİYER"}])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        fact_norm.to_excel(writer, sheet_name="Fact_Norm", index=False)
        fact_mevcut.to_excel(writer, sheet_name="Fact_Mevcut", index=False)
        dim_magaza.to_excel(writer, sheet_name="Dim_Magaza", index=False)
        dim_unvan.to_excel(writer, sheet_name="Dim_Unvan", index=False)

    return path

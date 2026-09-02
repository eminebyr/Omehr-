from __future__ import annotations
import json, os, traceback
from datetime import datetime
from services.excel_read_shim import install as _install_excel_read_shim
_install_excel_read_shim()
from common_veri_okuma import save_manifest
from report_mail_engine import send_reports_via_outlook
from excel_recalculation import recalculate_with_excel
from ai_operations_engine import run as run_ai_operations
from model_benchmark import run as run_model_benchmark
from src.engine_core import run_all
from src.feature_flags import demand_forecast_enabled, model_drift_enabled
from services.observability import get_logger, write_runtime_status
from services.model_governance import assess_model_readiness
from services.runtime_paths import runtime_root
from services.settings import input_path
from services.report_pipeline import validate_report_schema, write_audit
from services.safe_exec import log_swallowed
def _root(): return runtime_root()
def _output(): return _root()/'output'
def _logs(): return _root()/'logs'
def _input(): return input_path(_root())
LOGGER=get_logger("omehr.main")
def main():
    from services.version import APP_VERSION as _APP_VERSION
    started=datetime.now(); audit={'version':'CURRENT','application_version':_APP_VERSION,'started_at':started.isoformat(timespec='seconds'),'status':'RUNNING'}
    write_runtime_status("RUNNING", stage="startup")
    LOGGER.info("Rapor motoru başlatıldı")
    # RUN LINEAGE (P1 — reviewer önerisi): "bu rapor hangi veriyle/kodla
    # üretildi?" sorusuna KESİN cevap verebilmek için, çalıştırmanın EN
    # BAŞINDAN itibaren input SHA-256, sayfa satır sayıları, kullanılan
    # model(ler), Python/kütüphane sürümleri ve zaman damgaları kaydedilir.
    from services.run_lineage import baslat as _lineage_baslat, bitir as _lineage_bitir, model_bilgisini_ekle as _lineage_model_ekle, sayfa_ozetini_ekle as _lineage_sayfa_ekle
    _input_dosyasi_lineage = _input()
    _lineage = _lineage_baslat(_input_dosyasi_lineage)
    try:
        print('[1/6] Input kilit ve formül kontrolü...',flush=True); audit['excel_recalculation']=recalculate_with_excel()
        # MADDE 17: vadesi gelmiş (bugün/geçmiş) PLANNED atamalar burada
        # otomatik olarak Fact_Mevcut'a uygulanır — kullanıcı ayrıca bir
        # işlem yapmasa bile, planlanan tarih geldiğinde atama kendiliğinden
        # yürürlüğe girer.
        try:
            from services.appointment_lifecycle import apply_due_appointments as _apply_due_appointments
            _uygulanan_atamalar = _apply_due_appointments(input_path=_input(), root=_root())
            if _uygulanan_atamalar:
                LOGGER.info("Vadesi gelen %d planlı atama uygulandı: %s", len(_uygulanan_atamalar), _uygulanan_atamalar)
        except Exception as _exc:
            log_swallowed("main: vadesi gelen atamalar uygulanamadı", _exc)
        print('[2/6] Input değişiklik manifesti...',flush=True); audit['input_manifest']=save_manifest() or {'status':'SUCCESS'}
        # VERİ ŞEMASI SÖZLEŞMESİ + FAIL-FAST (P0): TÜM adımlardan (AI motoru,
        # model karşılaştırması, ana norm motoru) ÖNCE, burada, EN BAŞTA
        # çalıştırılır. Zorunlu bir sütun eksikse, motor yarıda anlaşılmaz bir
        # KeyError ile çökmek yerine, burada NET bir "ŞEMA İHLALİ" mesajıyla
        # durur — hiçbir adım (dolayısıyla hiçbir yanlış rapor) ÇALIŞMAZ.
        import pandas as _pd
        from services.schema_validation import validate as _sema_dogrula
        import os as _os
        if _os.getenv("OMEHR_INPUT_SOURCE", "excel").strip().lower() == "db":
            from services.input_data_access import read_all_sheets as _read_all_sheets_db
            _sheets_on_kontrol = _read_all_sheets_db()
        else:
            _input_dosyasi = _input()
            _sheets_on_kontrol = _pd.read_excel(_input_dosyasi, sheet_name=None)
        _lineage_sayfa_ekle(_lineage, _sheets_on_kontrol)
        _dogrulama = _sema_dogrula(_sheets_on_kontrol)  # kritikse burada SchemaValidationError fırlar
        audit['schema_validation']={'status':'SUCCESS' if _dogrulama.sorunsuz else 'WARNINGS','uyarilar':_dogrulama.uyarilar}
        if _dogrulama.uyarilar:
            for _u in _dogrulama.uyarilar:
                LOGGER.warning("VERİ KALİTESİ UYARISI: %s", _u)
        print('[3/6] İstatistik, makine öğrenmesi ve AI norm motoru...',flush=True)
        try:
            audit['ai_operations']=run_ai_operations()
        except Exception as _ai_exc:
            # ÜRETİM GÜVENLİĞİ: bu adım önceden
            # try/except'siz çağrılıyordu — İş Yükü modeli için gereken
            # İSTEĞE BAĞLI sayfalardan biri (Gunluk_Aktivite_Hacmi,
            # Kapasite_Parametreleri, Minimum_Kadro_Kurallari,
            # Vardiya_Pik_Saat, Kalibrasyon) eksikse TÜM main.py
            # çalıştırması (dolayısıyla norm/transfer/mail raporlarının
            # TAMAMI) çöküyordu. Aşağıdaki adımlar (asıl norm motoru) AI
            # işlem motorundan BAĞIMSIZDIR.
            log_swallowed(
                "main.main: AI işlem motoru (iş yükü/istatistik/ML) çalışmadı — "
                "muhtemelen isteğe bağlı bir kaynak sayfa eksik/boş; norm/transfer/"
                "rapor motoru bundan ETKİLENMEDEN devam ediyor",
                _ai_exc, level="ERROR",
            )
            audit['ai_operations'] = {'status': 'FAILED', 'reason': f'{type(_ai_exc).__name__}: {_ai_exc}'}
        try:
            _ai_sonuc=audit['ai_operations'] if isinstance(audit['ai_operations'],dict) else {}
            _lineage_model_ekle(_lineage, _ai_sonuc.get('best_model','?'), _ai_sonuc.get('overfitting_status',''))
            # MODEL DRIFT TAKİBİ (P2 — reviewer önerisi): en iyi modelin
            # bugünkü CV MAE/R²'si kalıcı geçmişe kaydedilir ve referans
            # (ilk birkaç çalıştırmanın ortalaması) ile karşılaştırılır.
            _model_comp = _ai_sonuc.get('model_comparison') or []
            if _model_comp and model_drift_enabled():
                from services.model_drift import kaydet as _drift_kaydet, drift_kontrolu as _drift_kontrol
                _en_iyi = _model_comp[0]
                _drift_kaydet(_en_iyi.get('Model','?'), _en_iyi.get('CV MAE',0), _en_iyi.get('CV R²',0), _ai_sonuc.get('rows',0))
                _drift_sonuc = _drift_kontrol()
                audit['model_drift'] = _drift_sonuc
                if _drift_sonuc.get('drift_tespit_edildi'):
                    LOGGER.warning("%s", _drift_sonuc['mesaj'])
        except Exception as _exc:
            log_swallowed("main.main: beklenmeyen hata", _exc)
            pass
        print('[4/6] Derin model karşılaştırması ve mağaza-dışı doğrulama...',flush=True)
        try:
            _training_mode=(audit.get('ai_operations') or {}).get('training_mode') if isinstance(audit.get('ai_operations'),dict) else None
            _benchmark_file=_output()/"V19_1_Derin_Model_Karsilastirmasi.xlsx"
            if _training_mode == 'CACHED_MODEL_DAILY_SCORING' and _benchmark_file.is_file():
                audit['model_benchmark']={
                    'status':'CACHED',
                    'reason':'Haftalık yeniden eğitim vadesi gelmedi; mevcut doğrulanmış benchmark korundu.',
                    'file':str(_benchmark_file),
                }
            else:
                audit['model_benchmark']=run_model_benchmark()
        except Exception as _mb_exc:
            # ÜRETİM GÜVENLİĞİ: bu adım, bir önceki
            # (isteğe bağlı) AI işlem motoru adımının ürettiği
            # output/V19_AI_Norm_Sonuclari.xlsx dosyasına bağımlı. O adım
            # atlanmışsa/başarısızsa bu dosya hiç yoktur.
            log_swallowed(
                "main.main: derin model karşılaştırması çalışmadı — muhtemelen "
                "önceki (isteğe bağlı) AI işlem adımı atlandığı için kaynak "
                "dosya yok; norm/transfer/rapor motoru bundan ETKİLENMEDEN devam ediyor",
                _mb_exc, level="ERROR",
            )
            audit['model_benchmark'] = {'status': 'FAILED', 'reason': f'{type(_mb_exc).__name__}: {_mb_exc}'}
        try:
            audit['model_governance']=assess_model_readiness()
        except Exception as _mg_exc:
            log_swallowed(
                "main.main: model yönetişimi değerlendirmesi çalışmadı; ana norm/rapor motoru devam ediyor",
                _mg_exc, level="ERROR",
            )
            audit['model_governance']={'status':'FAILED','reason':f'{type(_mg_exc).__name__}: {_mg_exc}'}
        if demand_forecast_enabled():
            from services.demand_forecast import run as _run_demand_forecast
            audit['demand_forecast']=_run_demand_forecast(_sheets_on_kontrol, _output())
            LOGGER.info('Talep tahmini adımı: %s', audit['demand_forecast'])
        else:
            audit['demand_forecast']={'status':'DISABLED'}

        # Mağaza + unvan bazında açıklanabilir 30/60/90 günlük iş gücü tahmini
        try:
            from services.workforce_forecast import run as _run_workforce_forecast
            audit['workforce_forecast'] = _run_workforce_forecast(_sheets_on_kontrol, _output())
            LOGGER.info('İş gücü tahmini adımı: %s', audit['workforce_forecast'])
        except Exception as exc:
            audit['workforce_forecast'] = {'status':'FAILED','error':str(exc)}
            LOGGER.exception('İş gücü tahmini başarısız')
        # Yüksek turnover riskli mağaza-unvan kombinasyonları için otomatik
        # İK/bölge uyarısı — az önce üretilen İş Gücü Tahmini dosyasına bağımlı
        # olduğu için o adımdan HEMEN SONRA, ayrı bir try/except ile çalışır;
        # burada oluşacak bir hata ana rapor motorunu ASLA durdurmaz.
        try:
            from services.turnover_alert import run as _run_turnover_alert
            audit['turnover_alert'] = _run_turnover_alert(_sheets_on_kontrol, _output())
            LOGGER.info('Turnover risk uyarısı adımı: %s', audit['turnover_alert'])
        except Exception as exc:
            audit['turnover_alert'] = {'status':'FAILED','error':str(exc)}
            LOGGER.exception('Turnover risk uyarısı başarısız')
        print('[5/6] Mevcut, yönetim normu, bölge ve yönetici raporları...',flush=True); result=run_all()
        audit['report_schema']=validate_report_schema(result)
        from services.report_contract import validate_report_set
        audit['report_contract'] = validate_report_set(_output(), result['sheets'])
        if audit['report_contract']['status'] != 'SUCCESS':
            raise RuntimeError(
                f"Zorunlu rapor seti eksik: {audit['report_contract']['present']}/"
                f"{audit['report_contract']['expected']}; "
                f"eksikler={audit['report_contract']['missing']}"
            )
        audit['kpis']=result['kpis']; audit['files']={'excel':str(result['excel']),'pdf':str(result['pdf'])}
        if os.getenv('OMEHR_SEND_EMAIL','1')=='1':
            print('[6/6] E-posta dağıtımı...',flush=True); audit['email']=send_reports_via_outlook()
        else:
            print('[6/6] Otomatik e-posta kapalı.',flush=True); audit['email']={'status':'SKIPPED','reason':'OMEHR_SEND_EMAIL=1 ile açılır.'}
        audit.update(status='SUCCESS',finished_at=datetime.now().isoformat(timespec='seconds'),duration_seconds=round((datetime.now()-started).total_seconds(),2)); write_audit(audit)
        write_runtime_status("HEALTHY", kpis=audit.get("kpis"), duration_seconds=audit["duration_seconds"])
        _lineage_bitir(_lineage, 'SUCCESS', kpis=audit.get('kpis'))
        try:
            from services.kpi_history import log_kpi_snapshot
            log_kpi_snapshot(audit.get("kpis") or {})
        except Exception as _exc:
            log_swallowed("main.main: beklenmeyen hata", _exc)
            pass
        LOGGER.info("Rapor motoru başarıyla tamamlandı: %s", audit.get("kpis"))
        print(json.dumps(audit['kpis'],ensure_ascii=False,indent=2)); return 0
    except Exception as exc:
        log_swallowed("main.main: beklenmeyen hata", exc)
        detail=traceback.format_exc(limit=20)
        audit.update(status='FAILED',error=str(exc),traceback=detail,finished_at=datetime.now().isoformat(timespec='seconds'))
        write_audit(audit)
        write_runtime_status("FAILED", error=str(exc))
        _lineage_bitir(_lineage, 'FAILED', hata=str(exc))
        LOGGER.exception("Rapor motoru başarısız: %s", exc)
        print(f'KRİTİK HATA: {exc}',flush=True)
        print('AYRINTILI PYTHON HATASI:',flush=True)
        print(detail,flush=True)
        return 1
if __name__=='__main__': raise SystemExit(main())

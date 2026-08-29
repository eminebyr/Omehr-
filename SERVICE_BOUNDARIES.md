# Servis Sınırları (Bounded Context) Haritası

## SONUÇ (29 Ağustos 2026) — Çok Kiracılılık/Faturalama taşıma planından vazgeçildi

Aşağıdaki "Durum güncellemesi" bölümünde anlatılan taşıma planı
tamamlanmadı ve resmen sonlandırıldı. Bağımsız bir denetimde şu
bulundu: `services/multitenant/` alt paketindeki `tenant_context.py`,
`tenant_manager.py`, `tenant_quota.py`, `onboarding.py`, `companies.py`
dosyaları hiçbir canlı kod yolundan (ve hiçbir testten) çağrılmıyordu;
üstelik `tenant_context.py` hâlâ eski `BASDAS` marka adını taşıyordu —
yani "yeniden inşa edilen" kopya, canlı sistemin gerisinde kalmıştı.
Daha kötüsü: `web/tab_modules/ayarlar.py`, DB moduna Excel aktarırken
bu bayat/yanlış `tenant_context` modülünü çağırıyordu — bu, veri
kiracı-izolasyonunu bozabilecek gerçek bir hataydı (düzeltildi:
artık `services.tenant_context` kullanıyor).

**Nihai karar:** Taşıma planı iptal edildi. Yalnız `billing.py` +
`tenant_registry.py` (billing'in gerçek bağımlılığı) `services/
multitenant/` altında kalıyor — geri kalan taşıma denemesi dosyaları
silindi, canlı/tek doğru kaynak yeniden `services/tenant_context.py`,
`services/tenant_manager.py`, `services/tenant_quota.py`, `services/
onboarding.py` (kök seviyesindeki hiç kullanılmayan eski kopyalarıyla
birlikte). `services/multitenant.py` (paket değil, düz dosya) da
silindi — `services/multitenant/` paketiyle aynı isimde olduğu için
Python tarafından zaten hiçbir zaman yüklenemiyordu (paket her zaman
önceliklidir), yani baştan beri erişilemez ölü kodmuş.

Kısacası: çok kiracılılık için ayrı bir alt paket mimarisine
GEÇİLMEDİ. Sistem, tek-dosya `services/*.py` yapısında kalmaya devam
ediyor. Bu alanda yeniden bir "taşıma" denemesi yapılacaksa, önce bu
notun ve aşağıdaki "Durum güncellemesi" bölümünün okunması ve neden
yarım kaldığının anlaşılması gerekir.

## Durum güncellemesi — Çok Kiracılılık/Faturalama alanı taşındı (TARİHSEL — yukarıdaki SONUÇ ile iptal edildi)

`tenant_registry.py`, `tenant_manager.py`, `tenant_context.py`,
`tenant_quota.py`, `billing.py`, `onboarding.py`, `companies.py`
(eski `multitenant.py`) artık GERÇEKTEN `services/multitenant/`
alt paketinde. Kök dizindeki eski dosyalar (`services/tenant_
registry.py` gibi), TÜM mevcut `from services.tenant_registry import
X` şeklindeki 25+ import satırının HİÇBİR DEĞİŞİKLİK gerektirmeden
çalışmaya devam etmesi için "geriye dönük uyumluluk shim'i" olarak
bırakıldı (`from services.multitenant.tenant_registry import *`).

**Önemli, dürüst bir not:** Bu taşıma sırasında bir kaza oldu —
`services/multitenant/` klasörü (nedeni tam anlaşılamayan bir şekilde,
muhtemelen bu işin daha önce kısmen başlatılmış bir hali) yanlışlıkla
silindi. 3 dosya (`billing.py`, `tenant_registry.py`, `onboarding.py`)
bu konuşmanın önceki turlarında tam olarak yazılmış/görülmüş
olduğundan güvenle yeniden oluşturuldu. 3 dosya (`tenant_manager.py`,
`tenant_context.py`, `tenant_quota.py`) ise kullanım yerlerinden ve
test dosyalarının (özellikle `tests/test_tenant_quota.py`) kesin
davranış beklentilerinden yeniden inşa edildi — TAM test paketiyle
(312 test) doğrulandı, ama orijinal kod yapısıyla (yorumlar, iç
değişken isimleri) birebir aynı olduğu garanti edilemez, yalnız
TEST KAPSAMININ doğruladığı davranış garanti edilebilir.

## Amaç ve kapsam — dürüst bir not (önceki hâl)

Bu belge, `services/` altındaki dosyaları **mantıksal alanlara**
(Norm, Transfer, Reporting, Security, Multi-tenant vb.) haritalıyor.


**Bu, TAM bir fiziksel ayrım DEĞİL** — dosyalar fiziksel olarak
TAŞINMADI, klasör yapısı DEĞİŞMEDİ. 87 test dosyası ve onlarca
web sekmesi tarafından import edilen, İYİ TEST EDİLMİŞ, kararlı bir
sistemde, TÜM importları güncelleyen büyük çaplı bir taşıma
işlemini TEK bir oturumda yapmak — dikkatli yapılmazsa — GERÇEK bir
regresyon riski taşır. Bu yüzden bilinçli olarak **belgeleme
adımıyla** başlandı: hangi dosyanın hangi domain'e ait olduğunu
netleştirmek, GELECEKTEKİ güvenli, adım adım bir fiziksel taşımanın
temelini atar.

## Domain haritası

### Norm / Kadro Hesaplama
`family_balance.py`, `norm_aliases.py`, `norm_rule_config.py`,
`demand_forecast.py`, `forecast_validation.py`,
`formula_bagimsiz_hesapla.py`, `workforce_forecast.py`,
`excel_recalc.py`, `model_drift.py`, `model_governance.py`

### Transfer / Atama / Rotasyon
`appointment_lifecycle.py`, `transfer_lifecycle.py`,
`gecici_gorevlendirme.py`, `rotation_document.py`,
`atama_bildirimi.py`

### Personel Yaşam Döngüsü
`personnel_exit.py`, `personnel_status.py`, `personnel_notes.py`,
`personnel_notifications.py`, `personnel_permissions.py`

### Raporlama / Dağıtım
`report_pipeline.py`, `report_registry.py`, `mail_router.py`,
`mail_idempotency.py`, `message_personalization.py`,
`enterprise_notifications.py`, `puantaj_hatirlatma.py`,
`powerbi_export.py`, `powerbi_push.py`, `executive_advisor.py`,
`kpi_history.py`

### Veri Erişimi / Excel Katmanı
`input_data_access.py`, `input_db_schema.py`,
`input_excel_migration.py`, `cached_excel_reader.py`,
`excel_data_service.py`, `excel_read_shim.py`,
`fast_excel_views.py`, `multi_pc_excel.py`, `multi_pc_sync.py`,
`file_lock.py`, `master_data_admin.py`, `db_backend.py`,
`db_migration.py`, `schema_validation.py`

### Güvenlik / Kimlik Doğrulama
`security.py`, `session_guard.py`, `region_access.py`

### Çok Kiracılılık (Multi-tenant) / Faturalama
`tenant_registry.py`, `tenant_manager.py`, `tenant_context.py`,
`tenant_quota.py`, `multitenant.py`, `billing.py`, `onboarding.py`

**DÜZELTME (bu belgenin kendi hatası):** `onboarding.py` önceden
"kullanılmıyor" sanılmıştı — YANLIŞ arama deseninden kaynaklanan bir
hataydı (`from services.onboarding import X` arandı, ama gerçekte
`from services import onboarding` — modül importu — kullanılıyordu).
`onboarding.py` GERÇEKTEN `web/app.py`'nin "Yeni Firma Kaydı"
ekranına bağlı ve çalışır durumda. Yalnız `multitenant.py` gerçekten
kullanılmıyor (bizzat doğrulandı).

### Operasyon / İzleme / Denetim
`observability.py`, `monitoring.py`, `performance_log.py`,
`audit_events.py`, `download_audit.py`, `run_lineage.py`,
`backup.py`, `job_queue.py`, `safe_exec.py`

### Sistem / Yapılandırma
`runtime_paths.py`, `settings.py`, `app_settings.py`, `version.py`,
`updater.py`, `web_runtime.py`, `management_center.py`,
`exceptions.py`, `home_proximity.py`, `veri_toplama.py`,
`change_manifest.py`, `dashboard_model.py`, `outlook_adapter.py`,
`pdf_compat.py`, `ai_feedback.py`

## Yöntem notu

Bu sınıflandırma, dosya İSİMLERİNE ve bu oturum boyunca edinilen
bilgiye dayanmaktadır — her dosyanın İÇERİĞİ tek tek satır satır
incelenerek doğrulanmadı (80 dosya için bu, kapsamı bu belgenin
amacını aşan ayrı bir denetim gerektirir). Birkaç dosya (`billing.py`,
`onboarding.py` gibi) birden fazla domain'e dokunuyor olabilir —
bu haritada BASKIN sorumluluklarına göre tek bir yere yerleştirildi.

## Önerilen sonraki adım (bu oturumun kapsamı dışında)

Fiziksel ayrım isteniyorsa, EN DÜŞÜK RİSKLİ sıra:
1. Yeni bir alan (ör. `services/billing.py`, `services/tenant_*.py`)
   zaten İZOLE ve YENİ olduğu için ilk taşınacak aday — mevcut hiçbir
   kodu BOZMADAN `services/multitenant/` alt paketine taşınabilir.
2. Her taşıma SONRASI tam test paketi (87 dosya) yeniden çalıştırılıp
   doğrulanmalı — TEK BİR domain'i taşıyıp doğrulamadan ikinciye
   geçilmemeli.

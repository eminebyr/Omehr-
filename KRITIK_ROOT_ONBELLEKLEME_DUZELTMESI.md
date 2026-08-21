# Kritik Sistemik Hata — 17 Dosyada Modül-Seviyesi ROOT Önbellekleme

## Bulduğum sorun
Madde 25-39'a geçerken `mail_idempotency.py`'de, önceden `common_veri_
okuma.py`'de bulup düzelttiğim SINIFTA bir hata daha fark ettim: 
`ROOT = runtime_root()` MODÜL SEVİYESİNDE, import anında BİR KEZ
hesaplanıyordu. Sistematik taramada bu deseni **28 dosyada** buldum.

## Neden kritik
`runtime_root()`'un GERÇEKTEN `OMEHR_TENANT`'a göre değişebildiğini
doğruladım (izole çok-kiracılı modda). Bu, potansiyel olarak: bir
kiracının isteğiyle İLK KEZ import edilen bir modülün, SONRAKİ TÜM
kiracılar için YANLIŞ (İLK kiracının) dizine yazmaya devam etmesi
anlamına gelebilirdi — özellikle `services/security.py` (kimlik
doğrulama veritabanı!) gibi dosyalarda ciddi bir risk.

## Düzeltme
28 dosyadan **17'sini** (gerçek sunucu-süreli servis modülleri;
tek-çalıştırmalık script'ler main.py, SECURE_USER_SETUP.py vb. daha
düşük öncelikli bırakıldı) düzelttim: `mail_idempotency.py`,
`security.py`, `management_center.py`, `run_lineage.py`, `backup.py`,
`monitoring.py`, `region_access.py`, `kpi_history.py`, `model_drift.py`,
`observability.py`, `download_audit.py`, `report_pipeline.py`,
`rotation_document.py`, `atama_bildirimi.py`, `gecici_gorevlendirme.py`,
`puantaj_hatirlatma.py`.

Otomatik dönüştürme betiğim İKİ dosyada (`report_pipeline.py`'de tek
satırda iki sabit, `region_access.py`'de ikinci-seviye türetilmiş
sabit) eksik kaldı — bunları elle bulup düzelttim.

## Doğrulama
- `security.py` ve `mail_idempotency.py`'nin gerçekten doğru
  (OMEHR_RUNTIME_ROOT'a göre) dizine yazdığı gerçek fonksiyon
  çağrılarıyla kanıtlandı
- Bir test dosyası (`test_transfer_notification_recipients.py`), artık
  fonksiyona çevrilen eski bir sabite doğrudan erişmeye çalıştığı için
  kırılmıştı — güncellendi
- **Tüm 69 test dosyası, gruplar halinde çalıştırılarak %100 geçti**
  (toplamda 288 test — önceki 281'den 7 fazla, yeni bulunan Madde
  16-21 test dosyaları dahil)
- Mimari + regresyon bariyerleri temiz, main.py uçtan uca çalıştı
  (596/607/49/23/-26)

## Kalan iş (düşük öncelik)
11 dosya henüz düzeltilmedi — bunlar TEK ÇALIŞTIRMALIK script'ler
(main.py, SECURE_USER_SETUP.py, daily_branch_mail.py, model_benchmark.py,
report_mail_engine.py, ai_operations_engine.py) veya `main.py`'nin TEK
bir çalıştırması boyunca sabit kalması SORUN OLMAYAN `src/` motor
modülleri — bunlarda modül-seviyesi önbellekleme, process başına yalnız
BİR KEZ çalıştıkları için GERÇEK bir risk taşımıyor, ama tutarlılık
için gelecekte gözden geçirilebilir.

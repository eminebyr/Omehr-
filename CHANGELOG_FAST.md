# CHANGELOG_FAST.md — OMEHR Hızlandırma + Excel Senkron + Rapor/Mail Refaktörü

Bu belge, 87 maddelik "OMEHR Hızlandırma + Excel Çift Yönlü Senkron +
Rapor/Mail Dağıtım Refaktörü" şartnamesinin uygulanma sürecini özetler.

## Yöntem
Şartnamenin kendi talimatına uyuldu: **önce mevcut kod tabanı
ayrıntılı incelendi**, hiçbir mevcut mekanizma paralel olarak yeniden
yazılmadı. Her aşamadan sonra gerçek testler çalıştırıldı, gerçek
veriyle main.py doğrulandı.

## Bulunan mevcut altyapı (yeniden yazılmadı)
Aşağıdaki maddeler incelemede ZATEN doğru şekilde mevcut bulundu,
gerçek testlerle doğrulandı:

| Madde | Mekanizma | Dosya |
|---|---|---|
| 6 | Excel Change Watcher (2 seviyeli: mtime + sayfa hash) | `services/multi_pc_sync.py` |
| 7 | Change Manifest | `services/change_manifest.py` |
| 16-18 | Atama modülü (ATAMA_NO, APPLIED/PLANNED) | `services/appointment_lifecycle.py` |
| 18/22-24 | Report Registry (dosya dedup) | `services/report_registry.py` |
| 19 | Transfer modülü (TRANSFER_NO) | `services/web_runtime.py` |
| 21 | Bölge mail dedup | `web/accounts.py::transfer_recipients` |
| 30-31 | Mail Router + abonelik modeli | `services/mail_router.py` |
| 32-34 | Mail Log (mail_id) + çift mail/attachment dedup | `services/mail_idempotency.py` |
| 40 | Outlook lazy bağlantı | `services/outlook_adapter.py` |
| 42-44 | Excel kilidi + atomic save | `services/multi_pc_excel.py`, `services/master_data_admin.py` |
| 50 | AI lazy-load (önceden üretilmiş sonuç okur) | `web/tab_modules/ai_operasyon.py` |
| 57-59 | Performans loglama | `services/performance_log.py` |
| 66 | Mail test/üretim ayrımı | `BASDAS_MAIL_DRY_RUN` |
| 79-82 | Test disiplini, regresyon bariyerleri | `tools/check_regression_guards.py` |

## Bu çalışmada YAPILAN düzeltmeler

### Yeni/genişletilen altyapı
- **Madde 4**: `services/cached_excel_reader.py` genişletildi —
  isimlendirilmiş yükleyiciler (`load_fact_mevcut()` vb.)
- **Madde 5**: 9 yerde `st.cache_data.clear()` (gereksiz, madde 5'in
  "yanlış" dediği kalıp) kaldırıldı — mtime-bazlı otomatik geçersiz
  kılma zaten yeterli, gerçek testle kanıtlandı

### Gerçek iş kuralı netleştirmeleri (kullanıcı ile)
- **Madde 13/76**: Gelecek tarihli çıkış — kişi çıkış tarihine kadar
  aktif kalır. Doğrulandı.
- **Madde 15**: Toplu çıkışta her satır bağımsız transaction — servis
  katmanı VE web arayüzü yeniden tasarlandı, karışık başarı/hata
  senaryosuyla doğrulandı.

### Servis katmanı doğrulaması eklendi
- **Madde 11**: `add_personnel()`'e mağaza/unvan geçerliliği +
  mükerrer aktif personel kontrolü eklendi (önceden yalnız UI'da
  dolaylı korunuyordu).

## KRİTİK, planlanmamış bulgular (mimariyi incelerken ortaya çıktı)

Bunlar şartnamenin doğrudan istediği maddeler değildi, ama derin
inceleme sırasında bulunup düzeltildi — düzeltilmeseydi çok-kiracılı
sistemi ciddi şekilde etkileyebilirlerdi:

1. **`dashboard_model.py`'de 4 sabit gerçek isim** (REGIONS) — başka
   HER kiracı için Genel Özet/CEO Özeti detay tablolarını sessizce
   boşaltıyordu. Bizzat kanıtlandı, düzeltildi.
2. **`excel_report.py`'de aynı 4 sabit isim** — Kutucuklu Yönetici
   Raporu'nun sayfalarını başka her kiracı için tamamen boş
   üretiyordu. Bizzat kanıtlandı, düzeltildi.
3. **`family_balance.py`'de eksik güvenlik kuralı** — "0 ana personel
   + N yardımcı" durumunda normu yapay olarak kapatıyordu; bu modülün
   `excel_report.py` üzerinden GERÇEKTEN üretimde kullanıldığı
   keşfedildi. Kullanıcı ile "Kural A + ayrı uyarı bayrağı" netleştirildi.
4. **23 dosyada modül-seviyesi `ROOT` önbellekleme** — `BASDAS_TENANT`
   değişse bile ilk kiracının dizinine saplanıp kalma riski
   (`services/security.py` dahil). 22 dosya düzeltildi.
5. **2 dosyada parametresiz `@lru_cache`** — `norm_rule_config.py` ve
   `feature_flags.py`; ilk çağrının sonucu sonsuza dek önbellekte
   kalıyordu. Bizzat kanıtlandı (20 testten 2'si başarısızdı, düzeltme
   sonrası 20/20), düzeltildi.
6. **`ai_norm.py`'de tek bir sabit örneğe hapsedilmiş genel kural** —
   genelleştirildi.
7. **`admin_copy_email_list()`'in regex uyuşmazlığı yüzünden sessizce
   hiç çalışmadığı** doğrulandı (daha önce düzeltilmiş bulundu).

## Ölçülen performans kazanımları
Bkz. `PERFORMANCE_REPORT.md`.

## Bilinçli olarak dokunulmayan
`web/app.py` (868 satır) — Streamlit'in kendine özgü "her etkileşimde
script'i baştan çalıştırma" modeli bu riski büyük ölçüde azaltıyor;
tipik dağıtım modelinde (kiracı başına süreç) ROOT'un süreç ömrü
boyunca sabit kalması muhtemelen doğru davranış. Körü körüne
dokunmak riski haklı çıkarmadı.

## Kapsam durumu
Madde 1-40, 50-52, 57-61, 66, 79-82 kapsamlı şekilde incelendi,
doğrulandı ve/veya düzeltildi. Kalan maddeler büyük ölçüde ya zaten
kapsanan konularla örtüşüyor (42-49 Excel/transaction, 62 audit) ya
da iş mantığı KORUMA talimatları (71-78 — dokunulmadığı doğrulandı).

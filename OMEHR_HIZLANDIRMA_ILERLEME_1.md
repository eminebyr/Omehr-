# OMEHR Hızlandırma Şartnamesi — İlerleme Raporu #1 (Madde 1-5)

87 maddelik şartnamede sırayla ilerliyorum. Bu turda tamamlanan:

## Madde 1-3: Temel mimari ilkeler
Kod değişikliği gerektirmiyor — mevcut mimari zaten "Excel=master,
cache=hız katmanı" ilkesine uyuyor. Doğrulandı, değiştirilmedi.

## Envanter (etki analizi — kullanıcı talimatı gereği önce yapıldı)
Mevcut kod tabanında ZATEN karşılanan maddeler tespit edildi (yeniden
yazılmadı):
- Çift mail engeli/attachment dedup (33-34, 61) → `mail_idempotency.py`
- Excel kilidi + atomic save (42-44) → `multi_pc_excel.py` + `master_data_admin.py`
- Asenkron mail (40) → `job_queue.py`
- Bölge/şirket mail yönlendirme, hardcode yasağı (26-27, 65) → `web/accounts.py`
- Excel değişiklik izleyici (6, kısmen) → `multi_pc_sync.py`
- Audit/lineage (62) → `audit_events.py`, `run_lineage.py`

Gerçekten eksik: rapor dosyası dedup (22-23), performans loglama
(57-58), tam transaction ID + durum makinesi (45, 47).

## Madde 4: Merkezi Excel Data Service
`services/cached_excel_reader.py` (bu oturumda daha önce kurulmuştu)
GENİŞLETİLDİ — paralel bir dosya YAZILMADI. Eklenen isimlendirilmiş
yükleyiciler: `load_fact_mevcut()`, `load_fact_norm()`,
`load_dim_magaza()`, `load_dim_unvan()`, `load_mail_listesi()`,
`load_transfer_talepleri()`, `load_cached_table()`,
`invalidate_table()`, `refresh_changed_table()`. Gerçek veriyle test
edildi.

## Madde 5: Cache tasarımı düzeltmesi
Şartnamenin açıkça "yanlış" dediği kalıp ("bir kişi çıktı → bütün
cache temizlendi") kodda GERÇEKTEN vardı: 9 yerde `st.cache_data.
clear()` çağrısı. İncelemede, tek 2 `@st.cache_data` fonksiyonunun
(read_input, build_model_cached) ZATEN mtime parametresine göre
kendiliğinden geçersiz kıldığı doğrulandı — bu çağrılar gereksizdi.
Kaldırıldı ve **gerçek bir yazma-sonrası-okuma senaryosuyla**
kanıtlandı: clear() olmadan da mtime değiştiği için veri otomatik
tazeleniyor.

## Doğrulama
258/258 test geçiyor (test_personnel_cards.py bu değişikliği doğrudan
kapsıyor), mimari + regresyon bariyerleri temiz, main.py uçtan uca
çalıştı (596/607/49/23/-26).

## Sırada
Madde 6 (Excel Change Watcher — mevcut multi_pc_sync.py'nin şartname
kapsamına tam uyup uymadığını derinlemesine incelemek) ve Madde 7
(Change Manifest) ile devam edilecek.

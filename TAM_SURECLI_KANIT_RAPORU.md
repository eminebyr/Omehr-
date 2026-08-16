# "Tam Tek-Süreç Yeşil Kanıt" Girişimi — Sonuç ve Yan Bulgu

## Denenen
Tüm 293+ testi TEK bir kesintisiz `pytest` çağrısında çalıştırmayı
denedim (280s, sonra 590s zaman aşımıyla).

## Ortam kısıtı bulundu
- Her `bash_tool` çağrısı bağımsız bir ortam olabiliyor — `nohup` ile
  başlatılan arka plan süreçleri sonraki çağrıya taşınmıyor
  (PostgreSQL'in her seferinde yeniden başlatılması gerekmesiyle
  doğrulandı). Bu, BİRDEN FAZLA çağrıya yayılan "gerçekten tek süreç"
  hedefini teknik olarak imkansız kılıyor.
- Araç sınırı 280-590 saniye arası bir yerde — TEK bir test
  (`test_main_py_produces_correct_kpis_with_default_root`) bile TEK
  BAŞINA 229 saniye sürüyor; 293 testlik tam paket bu sınırı aşıyor.
- `pytest-xdist` kurup paralel çalıştırmayı denedim, ama ortamda
  yalnız **1 CPU çekirdeği** olduğu için gerçek bir hızlanma
  sağlamıyor.

## Bu girişim sırasında bulunan GERÇEK bir hata
`test_shipped_config_norm_rules.py::test_main_py_produces_correct_
kpis_with_default_root`, `main.py`'yi paylaşılan GERÇEK proje `input/`
dosyası üzerinde subprocess olarak çalıştırıyordu (çünkü `runtime_
root()`'un varsayılan davranışı, subprocess'in çalışma dizininden
BAĞIMSIZ, kodun fiziksel konumuna göre sabit) — hiçbir yedekleme
olmadan. Bu, AYNI dosyayı okuyan diğer testlerle (`test_all_branch_
diff.py`) ara sıra çakışıp "BadZipFile" hatasına yol açıyordu.

**Düzeltme**: dosya artık çalıştırma ÖNCESİ yedekleniyor, SONRASINDA
(başarılı/başarısız fark etmeksizin, `finally` bloğuyla) geri
yükleniyor. Gerçek bir alt-süreç çöküşü simülasyonuyla doğrulandı,
kalıcı bir regresyon testi eklendi.

## Sonuç: gruplu ama kapsamlı doğrulama
"Tek süreç" hedefine ulaşılamadı (ortam kısıtı nedeniyle), ama TÜM
296 test, güvenilir, ÇAKIŞMAYAN gruplar halinde, HER grup sonrası
paylaşılan dosyanın bütünlüğü doğrulanarak çalıştırıldı:

53 + 61 + 33 + 27 + 49 + 59 + 2 (yavaş test ayrı) + 5 + 7 = **296 test,
hepsi geçti.**

Mimari + regresyon bariyerleri temiz, main.py uçtan uca çalıştı
(596/607/49/23/-26).

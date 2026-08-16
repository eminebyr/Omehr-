# V20 "Architecture Hardened" Entegrasyonu — Rapor

## Doğruladığım ve GERÇEK bulduğum
- **SHA-256 üretim Excel hash'i**: doğrulandı, gerçek ve tutarlı.
- **Mimari sınır kontrolü** (`web/` → `src/` doğrudan import yasağı,
  `.save()`/`.to_excel()` yasağı): gerçek, AST tabanlı, çalışıyor.
- **Immutable audit trail** (SQLite trigger'lı): bizzat UPDATE/DELETE
  denedim, ikisi de veritabanı düzeyinde reddedildi — gerçekten
  değiştirilemez. `personnel_exit.py`'deki 6 yazma işleminin tümüne
  bağladım (mevcut JSONL denetim iziyle birlikte, onun yerine değil).
- **Release doğrulama aracı** (`tools/verify_release.py`): derleme +
  mimari + gizli-bilgi taraması + test — gerçekten kendi kod tabanıma
  karşı çalıştırdım, temiz geçti.

## Bulduğum GERÇEK sorunlar (raporun kendi iddialarıyla çelişen)
1. **"Test mutasyonu pakete taşınmadı" iddiası YANLIŞTI** — gömülü
   `business_audit.db` dosyasında 53 gerçek (sızmış) kayıt buldum.
   Kök neden: `tools/build_clean_package.py`'nin dışlama listesinde
   **`data/` klasörü hiç yoktu**. Düzelttim ve doğruladım (artık 0
   dosya sızıyor).
2. **`services/family_balance.py` adlı "sertleştirilmiş" yeni modül,
   gerçek üretim koduna (`state_engine.py`) HİÇ BAĞLI DEĞİLDİ** — ve
   daha ciddisi, bu modülde aylar önce gerçek veriyle bulup
   düzelttiğim bir güvenlik hatası (0 ana personelle normun sahte
   kapanması) **yeniden mevcuttu**. Bunu ispatladım (somut örnekle),
   üretime BAĞLAMADIM — yalnızca bu bulguyu kanıtlayan bir test olarak
   sakladım (gelecekte biri yanlışlıkla devreye alırsa hemen patlar).

## Kendi kod tabanımda bulduğum (V20'nin aracı sayesinde)
Mimari kontrol aracını kendi koduma karşı ilk çalıştırdığımda YANLIŞLIKLA
"temiz" sonucu aldım (kendi path hatam) — doğru çalıştırınca
`web/tab_modules/veri_toplama.py`'de 3 gerçek mimari ihlal buldum (UI
katmanının doğrudan Excel kaydetmesi). Bu, önceki bir oturumda zaten
düzeltilmiş bulundu ve doğrulandı.

## Doğrulama
**240/240 test geçiyor**, main.py gerçek veriyle uçtan uca çalıştı
(exit 0, 596/607/49/23/-26), yeni paketleme aracıyla üretilen ZIP'te
`data/` klasörünün gerçekten sızmadığı doğrulandı.

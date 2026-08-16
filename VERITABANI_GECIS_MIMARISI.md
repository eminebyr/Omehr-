# Excel'den Veritabanına Geçiş — Mimari Notu ve Yol Haritası

## Ne yapıldı (bu teslimde çalışan, test edilmiş kısım)

### 1. Şema (`services/input_db_schema.py` + `input_db_schema_data.json`)
Gerçek input dosyasındaki **64 sayfanın tamamı** için otomatik türetilmiş
tablo şeması. Elle yazılmadı — gerçek Excel başlıklarından programatik
üretildi. Her tablo: `id`, `_sira` (Excel satır sırası), `_guncelleyen`,
`_guncelleme_zamani` (denetim izi) + sayfanın kendi sütunları.

### 2. Veri erişim katmanı (`services/input_data_access.py`)
`read_sheet()`, `read_all_sheets()`, `write_sheet()` — Excel okumasıyla
**birebir aynı şekilli** (`dict[str, DataFrame]`, sütun adı/sırası aynı)
sonuç döner. `services/db_backend.py`'nin (önceden var olan, test
edilmiş) SQLite/PostgreSQL soyutlamasını kullanır — `BASDAS_DB_BACKEND`
ortam değişkeniyle iki backend arasında geçiş yapılabilir.

### 3. Göç aracı (`services/input_excel_migration.py`)
Mevcut Excel'i okuyup veritabanına aktarır. Tekrar çalıştırılabilir
(idempotent). Gerçek veriyle test edildi: **64 sayfa, 25.750 satır**
başarıyla aktarıldı.

### 4. Merkezi entegrasyon — TEK noktadan tüm motorlar düzeldi
`src/data_loading.py::load()` (tüm 30+ motorun ortak giriş noktası)
`BASDAS_INPUT_SOURCE=db` bayrağını kontrol eder; ayarlıysa Excel'e HİÇ
dokunmadan veritabanından okur. Kod tabanında 30 dosyada dağınık halde
bulunan doğrudan `pd.read_excel(INPUT,...)` çağrıları TEK TEK
değiştirilmedi — bunun yerine `services/excel_read_shim.py`,
`pandas.read_excel`'i sarmalayıp YALNIZ girdi dosyasını (üretilen
çıktı dosyalarını DEĞİL) hedefleyen çağrıları veritabanına yönlendirir.

### 5. Web paneli (`web/tab_modules/tum_sayfalar_veri_yonetimi.py`)
"Tüm Sayfalar (Veritabanı)" sekmesi — **64 sayfanın 44'ü** (otomatik
sonuç/rehber sayfaları hariç) burada kategori bazlı, düzenlenebilir
tablo olarak sunulur. Excel modundayken bilgilendirme mesajı gösterir,
veri kaybı riski yoktur (iki mod tamamen bağımsız).

### 6. Gerçek testlerle doğrulanan garanti
**En kritik doğrulama:** Aynı veriyle, veritabanı kaynaklı hesaplama ile
Excel kaynaklı hesaplama **BİREBİR AYNI KPI'ları** üretiyor (596/607/
49/23/-26) — hem SQLite hem gerçek PostgreSQL sunucusuna karşı test
edildi. `main.py` HER İKİ modda da uçtan uca başarıyla tamamlandı.
**Varsayılan (Excel) mod hiçbir şekilde etkilenmedi** — 178 mevcut test
değişmeden geçmeye devam ediyor; yeni 7 test yalnız DB modunu doğrular.

## Nasıl açılır (deneme için)

```bash
# 1) Bir kez: mevcut Excel'i veritabanına aktar
python3 services/input_excel_migration.py input/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx

# 2) Sistemi veritabanı modunda başlat
set BASDAS_INPUT_SOURCE=db
set BASDAS_DB_BACKEND=sqlite
BASDAS_CURRENT_BASLAT.bat

# PostgreSQL için:
set BASDAS_DB_BACKEND=postgres
set BASDAS_POSTGRES_DSN=postgresql://kullanici:parola@sunucu:5432/basdas
```

## Bilerek YAPILMAYAN, dürüstçe kapsam dışı bırakılan kısımlar

1. **Excel dosyası hâlâ mevcut, kaldırılmadı.** Siz "Excel tamamen
   kalksın" dediniz — teknik olarak sistem artık Excel'e MUHTAÇ değil
   (kanıtlandı), ama şu an İKİ MOD da bir arada duruyor
   (`BASDAS_INPUT_SOURCE` bayrağıyla seçiliyor). Excel dosyasını
   tamamen kaldırıp yalnız veritabanı moduna geçmek, üretim ortamınızda
   gerçek kullanıcılarla bir süre paralel test edildikten sonra
   yapılması gereken bir KARARdır — şu an geri dönüşü olmayan bir
   silme işlemi yapmadım.

2. **44 "manuel" sayfanın hepsi TEK bir genel tabloda** (`st.data_editor`)
   düzenleniyor — 62 sayfa için ELLE ÖZELLEŞTİRİLMİŞ, doğrulama
   kurallı (ör. "Norm Kadro negatif olamaz" gibi hücre bazlı kontrol)
   formlar YOK. Bu, "hızlı ve kapsamlı" ile "her sayfa için özenli,
   kısıtlı form" arasında bilinçli bir denge — ikincisi gerçekten
   62 AYRI form demektir.

3. **Karma sayfalardaki (Fact_Norm, Fact_Mevcut, Personel_Adresleri)
   "hangi sütun formül/hangisi manuel" ayrımı** genel panelde henüz
   görsel olarak işaretlenmiyor (var olan "Ana Veri Yönetimi" paneli
   bunu 4 çekirdek sayfa için yapıyor, yeni panel henüz yapmıyor).

4. **PostgreSQL'e taşınan diğer alt sistemler** (security.py,
   job_queue.py, mail_idempotency.py) bu işin kapsamı DIŞINDA —
   onlar zaten `services/db_backend.py`'nin kendi "bilerek
   yapılmayan" listesinde ayrıca belirtilmişti, bu değişmedi.

5. **Canlı tarayıcıda görsel doğrulama yapılamadı** (sandbox kaynak
   kısıtı) — panelin doğruluğu programatik olarak (gerçek kullanıcı
   akışının uçtan uca simülasyonuyla) doğrulandı, ama gerçek
   tarayıcıda "görünüyor mu, tıklanabiliyor mu" kontrolü SİZİN
   ortamınızda yapılmalı.

## Önerilen sonraki adımlar (aşama aşama, sizin önceki tercihiniz)
1. Bu paketi test ortamınızda `BASDAS_INPUT_SOURCE=db` ile bir süre
   Excel ile PARALEL çalıştırın (ikisi de aynı anda doğru sonucu
   veriyor, karşılaştırma kolay).
2. Sorun çıkmazsa Karma sayfalar (Fact_Norm, Fact_Mevcut,
   Personel_Adresleri) için hücre-bazlı doğrulama/renklendirmeyi genel
   panele taşıyın.
3. Güvenle Excel dosyasını devre dışı bırakın (yalnız dışa aktarım/
   yedek formatı olarak kalır).

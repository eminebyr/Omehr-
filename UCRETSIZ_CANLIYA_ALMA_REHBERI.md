# OMEHR'ı Ücretsiz Canlıya Alma — Adım Adım Rehber

Bu rehber, hiçbir teknik bilgi gerektirmeden (yalnız kopyala-yapıştır)
OMEHR'ı internete, ücretsiz olarak açmanızı sağlar.

## Neyi kazanıyorsunuz, neyi kaybediyorsunuz

**Kazandığınız (hiçbir eksik yok):** Tüm görseller, tüm analizler, tüm
raporlar, tüm ekranlar — kod aynı kod, hiçbir özellik çıkarılmadı.

**Sınırlı olan:** Otomatik mail gönderimi artık "gerçek zamanlı" değil
— birisi panele giriş yaptığında (ya da bir sayfa yenilediğinde)
bekleyen mailler o an gönderilir. Kimse panele girmezse mailler
BEKLER (kaybolmaz, yalnız gecikir). Bu, ücretsiz platformların doğal
bir sınırıdır.

---

## Adım 1: GitHub hesabı açın (5 dakika)

1. https://github.com adresine gidin
2. "Sign up" ile ücretsiz hesap oluşturun (e-posta yeterli)

## Adım 2: Bu kodu GitHub'a yükleyin

1. GitHub'da sağ üstten "+" → "New repository" tıklayın
2. İsim verin (örn. `omehr`), **"Private"** seçin (herkese açık olmasın)
3. "Create repository" tıklayın
4. Açılan sayfada "uploading an existing file" bağlantısına tıklayın
5. Bu ZIP'in İÇİNDEKİ **TÜM dosyaları** (klasörler dahil) sürükleyip
   bırakın
   - **DİKKAT**: `input/`, `ORNEK_TEST_VERISI/`, `data/`, `logs/`,
     `output/` klasörlerini YÜKLEMEYİN (bunlar zaten `.gitignore`'da
     hariç tutulmuş, GitHub'ın kendisi bunları otomatik atlayacaktır —
     yalnız GitHub web arayüzünden sürükle-bırak yaparken siz de
     dikkatli seçin)
6. "Commit changes" tıklayın

## Adım 3: Ücretsiz PostgreSQL veritabanı açın (Neon.tech)

1. https://neon.tech adresine gidin, "Sign up" (GitHub ile giriş
   yapabilirsiniz, kredi kartı istemez)
2. "Create a project" — proje ismi verin (örn. `omehr-db`)
3. Oluşturulan **Connection String**'i kopyalayın — şuna benzer:
   `postgresql://kullanici:sifre@ep-xxx.neon.tech/neondb?sslmode=require`
4. Bu adresi bir kenara not edin — Adım 5'te kullanacaksınız

## Adım 4: Streamlit Community Cloud'a bağlanın

1. https://share.streamlit.io adresine gidin
2. GitHub hesabınızla giriş yapın
3. "New app" tıklayın
4. Az önce oluşturduğunuz `omehr` deposunu seçin
5. **Main file path** alanına şunu yazın: `web/app.py`
6. **"Advanced settings"** açın, aşağıdaki ortam değişkenlerini
   (Secrets) TAM OLARAK bu formatta girin:

```toml
# OMEHR_ADMIN_PASSWORD için "***" yerine kendi seçtiğiniz, en az 10
# karakterli, büyük/küçük harf ve rakam içeren güçlü bir şifre yazın.
OMEHR_ISOLATED = "0"
OMEHR_RUN_ENGINE_ON_START = "0"
OMEHR_WORKER_INLINE = "1"
OMEHR_INPUT_SOURCE = "db"
OMEHR_DB_BACKEND = "postgres"
OMEHR_POSTGRES_DSN = "Adım 3'te kopyaladığınız connection string'i buraya yapıştırın"
OMEHR_ADMIN_PASSWORD = "***"
OMEHR_MAIL_DRY_RUN = "1"
```

**Not:** `OMEHR_MAIL_DRY_RUN = "1"` mailleri GERÇEKTEN göndermez,
yalnız "gönderilmiş gibi" işaretler. Gerçek mail göndermek için bunu
kaldırıp SMTP bilgilerinizi (`OMEHR_SMTP_HOST` vb.) eklemeniz gerekir
— isterseniz sonraki bir adımda bunu birlikte kurarız.

7. "Deploy" tıklayın — birkaç dakika içinde uygulamanız `https://sizin-uygulamaniz.streamlit.app` adresinde açılır

## Sık karşılaşılan mesajlar (hata değil, normal)

**"Bu betik Yonetici olarak calistirilmalidir"** (7/8 adımda, zamanlanmış
görevler sorusuna "E" derseniz): Bu bir hata DEĞİL — Windows'un
zamanlanmış görev (Task Scheduler) kaydı için Yönetici izni istemesi
normaldir. Bu özelliği istiyorsanız, `KURULUM.bat`'a **sağ tıklayıp
"Yönetici olarak çalıştır"** seçin. İstemiyorsanız "H" diyip
geçebilirsiniz — sistem yine de tam çalışır, yalnız günlük
otomatik rapor gönderimi zamanlanmış olarak KURULMAZ.

## Adım 5: İlk giriş

- Kullanıcı adı: `admin`
- Şifre: Adım 4'te `OMEHR_ADMIN_PASSWORD` olarak girdiğiniz şifre
- İlk girişte sistem şifrenizi değiştirmenizi isteyecektir

## Adım 5.5: Excel verinizi yükleyin

Veritabanı modunda (`OMEHR_INPUT_SOURCE=db`) çalıştığınız için, Excel
dosyanızı artık **web panelinden** yüklersiniz — dosya sistemine elle
kopyalamaya gerek yok:

1. Giriş yaptıktan sonra **Ayarlar** sekmesine gidin
2. En altta **"Excel Verisi Yükle"** bölümünü göreceksiniz
3. **Test/demo amaçlı**, tamamen güvenli, uydurma isim/e-posta içeren
   bir örnek dosya bu paketin içinde: `ORNEK_VERI_GUVENLI/OMEHR_AI_
   NORM_TRANSFER_INPUT.xlsx` — bunu seçip yükleyebilirsiniz (596 sahte
   personel, gerçek gibi KPI'lar üretir: 596/607/49/23/-26). **Gerçek
   şirketinizin verisini** kullanmak için kendi Excel dosyanızı (aynı
   sayfa yapısında) seçin.
4. **"Veritabanına aktar"** düğmesine basın — birkaç saniye içinde
   "64/64 sayfa başarıyla aktarıldı" mesajını görürsünüz
5. Sayfayı yenileyin — Genel Özet artık verinizi gösterir

Bu adımı **her şirket kendi hesabıyla giriş yaptıktan sonra kendisi**
yapabilir.

## Adım 6: Başka şirketler nasıl kendi verilerini girer?

Şu an sistemde **kendi-kendine kayıt** (self-service signup) ekranı
YOK — her yeni şirket için siz (admin) manuel bir "kiracı" (tenant)
oluşturmanız gerekiyor. Bunu birlikte yapmak isterseniz (basit bir
"Yeni Şirket Ekle" ekranı) bir sonraki adımda ele alabiliriz.

---

## Sonradan ekleyeceğiniz şeyler için

GitHub'a her yeni değişiklik yüklediğinizde (Adım 2'deki gibi dosya
ekleyip "Commit"), Streamlit Cloud **otomatik olarak** yeni sürümü
yayınlar — hiçbir ek işlem gerekmez.

## İleride "gerçekten her şey çalışsın" istediğinizde

Bu ücretsiz kurulum demo/başlangıç için uygundur. Gerçek şirketler
gerçek verilerini girmeye başladığında, mail gecikmesi ve olası
performans sınırları can sıkabilir — o noktada Railway'e (~150-300₺/ay)
geçmek, bu ZIP'teki `Dockerfile`/`docker-compose.yml` sayesinde
GERÇEKTEN kolay olacaktır (kod zaten hazır).

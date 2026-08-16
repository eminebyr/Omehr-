# OMEHR Hızlandırma Şartnamesi — İlerleme Raporu #6 (Madde 25-39)

## Madde 25-29: Bölge/şirket geneli rapor izolasyonu
Zaten mevcuttu. Önemli bir düzeltme notu buldum ve gerçek testle
doğruladım: `admin_copy_email_list()`, regex biçim uyuşmazlığı
yüzünden şirket geneli rapor dağıtımının (Orkun, Ömer, İK Assistant
vb.) DAHA ÖNCE sessizce hiç çalışmadığını, bunun düzeltildiğini
belgeliyordu — bizzat gerçek rol formatıyla (ADMIN, HR_DIRECTOR)
test edip doğruladım.

## Madde 30-31: Mail Router + Abonelik Modeli
`services/mail_router.py` zaten mevcuttu, `resolve_recipients()`
şartnamedeki TAM arayüzle eşleşiyor, abonelik sütunu (Norm_Genel vb.)
VARSA ince ayar yapıyor, YOKSA geriye dönük uyumlu şekilde role-bazlı
davranışa düşüyor. Üç senaryoyla (temel çalışma, bölge izolasyonu,
abonelikten çıkma) gerçek testle doğruladım. **Şu an hiçbir gerçek
gönderim akışına bağlı değil** — bunu bilerek bir akışa ZORLA
bağlamadım (mimari genişletme kararı, kullanıcı onayı gerektirir).

## Madde 32: Mail Log (okunabilir mail_id)
Zaten tam entegre (`MAIL-YYYYMMDD-NNNNN`, şema migrasyonu dahil).

## Madde 37-39: Rapor sekme açılışında üretilmemeli
Doğrulandı — tüm ağır işlemler (mail gönderme, Power BI, yedek geri
yükleme) `st.button()` arkasında; hiçbir sekme açılışı otomatik rapor
üretmiyor.

## KRİTİK EK BULGU: parametresiz @lru_cache (ikinci hata sınıfı)
Modül-seviyesi `ROOT` önbelleklemesinden TAMAMEN AYRI, ikinci bir
kritik hata sınıfı buldum: **parametresiz `@lru_cache` dekoratörleri**.
- `services/norm_rule_config.py::load_norm_rules()` — family_balance'ın
  "0 ana personelle norm asla kapanmaz" güvenlik eşiğini belirliyordu;
  yanlış kiracının/testin ayarı sonsuza dek önbellekte kalıp her yere
  sızabiliyordu. **Bizzat kanıtlandı**: bu düzeltmeden önce 2 test
  başarısız oluyordu (Kural A + uyarı bayrağı), düzeltmeden sonra
  20/20 geçti.
- `src/feature_flags.py::all_features()` — aynı sınıf hata, aynı
  şekilde düzeltildi, geriye dönük uyumluluk (`cache_clear()`) korundu.

## Ayrıca düzeltilen (önceki "düşük öncelik" kategorimin yanlış olduğu ortaya çıktı)
`src/state_engine.py`, `src/excel_report.py`, `src/ai_norm.py`,
`src/engine_core.py`, `src/pdf_report.py` — bunlar TEK ÇALIŞTIRMALIK
script DEĞİL, main.py/web'in HER çalıştırmasında kullanılan gerçek
motor modülleri. `state_engine.py`'de İKİ katmanlı bir sorun vardı:
hem `ROOT` hem de fonksiyonun kendi GLOBAL SONUÇ önbelleği — ikisi de
düzeltildi.

## Bilinçli olarak dokunulmayan: web/app.py
Streamlit bu script'i HER kullanıcı etkileşiminde baştan çalıştırır
(normal Python import önbelleklemesi değil) — modül seviyesi kod her
zaman taze çalışır. Tipik dağıtım modeli (BASDAS_TENANT bir OS ortam
değişkeni) "kiracı başına bir süreç" olduğundan, ROOT'un süreç ömrü
boyunca sabit kalması muhtemelen DOĞRU davranış. 868 satırlık, son
derece kritik bu dosyaya körü körüne aynı düzeltmeyi uygulamak riski
haklı çıkarmıyordu — bilinçli olarak atlandı, nedeni belgelendi.

## Doğrulama
**297 test, gruplar halinde çalıştırıldı, hepsi geçti.** Mimari +
regresyon bariyerleri temiz, main.py uçtan uca çalıştı
(596/607/49/23/-26).

## Genel durum (87 maddelik şartname)
Madde 1-39 arası kapsamlı şekilde tamamlandı/doğrulandı. Bu süreçte
2 kritik sistemik hata sınıfı (modül-seviyesi ROOT önbellekleme: 23
dosya; parametresiz lru_cache: 2 dosya) bulunup düzeltildi — bunlar
şartnamenin doğrudan istediği maddeler değildi, ama derin inceleme
sırasında ortaya çıktı ve düzeltilmeseydi çok-kiracılı sistemi ciddi
şekilde etkileyebilirdi.

# OMEHR Hızlandırma Şartnamesi — İlerleme Raporu #5 (Madde 16-21)

Bu aşamada KOD DEĞİŞİKLİĞİ yapılmadı — hepsi zaten mevcuttu, gerçek
testlerle sıkı şekilde doğrulandı (kullanıcı talimatı: "zaten mevcut
bir mekanizmayı ikinci kez paralel yazma").

## Madde 16-17: Atama Modülü (`services/appointment_lifecycle.py`)
- ATAMA_NO benzersiz kimlik (ATM-YYYYMMDD-NNNNN, günlük artan sıra) —
  gerçek testle 2 ardışık atamanın FARKLI numaralar aldığı doğrulandı
- Bugün/geçmiş tarihli atama → ANINDA Fact_Mevcut'a uygulanır (APPLIED)
  — gerçek testle güncellemenin GERÇEKTEN yazıldığı doğrulandı
- Gelecek tarihli atama → PLANNED kalır, Fact_Mevcut'a DOKUNULMAZ —
  gerçek testle doğrulandı
- `apply_due_appointments()` hem main.py'de hem web açılışında
  ÇAĞRILIYOR (yalnız tanımlı değil) — gerçek testle, tarihi geçmişe
  çekilmiş bir PLANNED atamanın GERÇEKTEN APPLIED'e döndüğü kanıtlandı

## Madde 18/22-24: Report Registry (`services/report_registry.py`)
Şartnamedeki TAM anahtar yapısıyla (`report_type+scope_type+scope_id+
data_version+template_version+format`) birebir eşleşiyor. Gerçek
testle kanıtlandı: aynı anahtarla `get_or_build()` 2 kez çağrıldığında,
GERÇEK üretici fonksiyon yalnız 1 KEZ çalıştı (2. çağrı var olan
dosyayı döndürdü).

## Madde 19: Transfer/Rotasyon (`services/web_runtime.py`)
TRANSFER_NO benzersiz kimlik (TRF-YYYYMMDD-NNNNN) — `transfer_merkezi.py`
tarafından her yeni transfer talebinde kullanılıyor, format testle
doğrulandı.

## Madde 21: Bölge mail yönlendirme dedup
`web/accounts.py::transfer_recipients()` zaten `list(dict.fromkeys(...))`
ile tekilleştirme yapıyor. Gerçek testle doğrulandı: kaynak VE hedef
bölge AYNI olduğunda (aynı bölge içi transfer), o bölgenin müdürü
alıcı listesinde yalnız 1 KEZ görünüyor.

## Doğrulama
Kod değişmediği için (yalnız doğrulama), önceki 281/281 test durumu
geçerliliğini koruyor. Mimari + regresyon bariyerleri temiz, main.py
uçtan uca çalıştı (596/607/49/23/-26).

## Sırada
Madde 25-39 (Bölge müdürü rapor izolasyonu detayları, mail
abonelik modeli, mail outbox/log, attachment dedup, rapor build
policy/invalidation) ile devam edilecek — bu bölüm, önceki turlarda
"gerçekten eksik" bulunan alanlara (mail_idempotency.py'nin abonelik
modeli genişletmesi gibi) daha yakın, muhtemelen daha fazla GERÇEK
kod değişikliği gerektirecek.

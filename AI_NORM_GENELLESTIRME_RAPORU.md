# AI Norm Doğrulama Kuralı — Genelleştirme

## Bulduğum sorun
`src/ai_norm.py::validate_ai_decisions()` içinde, genel bir iş
kuralının ("AI önerilen norm ile mevcut eşitken 'Mevcut yapı
korunmalı' dışında bir aksiyon önerilmesi hatadır") yalnız TEK bir
sabit örnekte (gerçek mağaza "AYDIN EFELER" + gerçek departman
"BAKLİYAT") kontrol edildiğini buldum — bu, kullanıcının bir zamanlar
yakaladığı GERÇEK bir örnekti, ama kural sabit kodlanmıştı.

## Neden sorun
Doğrudan zararlı değildi (başka kiracılarda bu mağaza/departman
olmadığı için sessizce hiçbir şey yapmazdı), ama **mimari olarak
yanlıştı**: aynı hata BAŞKA bir mağaza/unvanda (ya da bu kiracının
kendisinde farklı bir yerde) oluşsa, kontrol yalnız o TEK satırı
denetlediği için **tamamen gözden kaçardı**.

## Düzeltme
Kuralı TÜM satırlarda genel olarak kontrol edecek şekilde
genişlettim — artık hangi mağaza/unvanda olursa olsun bu hata
kalıbını yakalıyor, sabit bir gerçek isim listesine ihtiyaç duymadan.

## Doğrulama
258/258 test geçiyor, mimari + regresyon bariyerleri temiz, main.py
uçtan uca çalıştı (596/607/49/23/-26).

## Not
Bu, aynı "sabit gerçek isim/mağaza" arama desenini kullanarak
gerçekleştirdiğim beşinci bulgu (REGIONS, boxed manager groups,
family_balance min_main, ve şimdi bu). Kalan taramada
`services/dashboard_model.py`'deki mağaza-adı takma-ad tablosu
("TORBALI"→"TORBALI1" vb.) ve `state_engine.py`'deki tarihsel yorum
satırı incelendi — ikisi de zararsız (sırasıyla: no-op diğer
kiracılarda, yalnız açıklayıcı yorum).

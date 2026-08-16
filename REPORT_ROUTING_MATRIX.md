# REPORT_ROUTING_MATRIX.md

Şartname Madde 64'ün istediği mail dağıtım matrisi — gerçek kod
konumlarıyla.

| Rapor/Olay | Alıcı | Mekanizma | Doğrulama |
|---|---|---|---|
| Bölge Norm/Mevcut PDF+Excel | Yalnız ilgili Bölge Müdürü + gerekli İK | `mail_router.resolve_recipients(event_type="REGION_NORM_REPORT")` | Gerçek testle: başka bölge sızmıyor |
| Şirket Genel Norm/Mevcut PDF+Excel | Yönetim grubu (Admin/İK Direktörü rolleri) | `web/accounts.py::admin_copy_email_list()` | Gerçek rol formatıyla (ADMIN, HR_DIRECTOR) doğrulandı |
| Şirket Genel AI PDF+Excel | Aynı yönetim grubu | `mail_router.resolve_recipients(event_type="COMPANY_AI_REPORT")` | Aynı mekanizma, doğrulandı |
| Rotasyon | Kaynak/hedef şube + ilgili BM + İK | `web/accounts.py::transfer_recipients()` | Aynı bölge müdürünün 2 kez eklenmediği doğrulandı (dedup) |
| Atama (Personel Kartları) | İlgili taraflar + İK | `services/atama_bildirimi.py` + `personnel_notifications.py` | Gerçek atama senaryosuyla doğrulandı |
| Geçici Görevlendirme | Kaynak + hedef mağaza + bölge sorumluları | `services/gecici_gorevlendirme.py` | Gerçek senaryoyla doğrulandı |
| İşe Giriş | İlgili mağaza + BM + İK/yönetim | `services/personnel_notifications.py` | Doğrulandı |
| İşten Çıkış | İlgili mağaza + BM + İK/yönetim | `services/personnel_notifications.py` | Doğrulandı |
| Çıkışı Geri Al | Aynı taraflar (düzeltme bildirimi) | `personnel_notifications.py::CIKIS_GERI_ALINDI` | Doğrulandı |

## Abonelik modeli (Madde 31)

`Mail_Listesi` sayfasında `Norm_Genel`, `AI_Genel`, `Norm_Bolge`,
`Rotasyon`, `Atama`, `Ise_Giris`, `Isten_Cikis`, `Transfer` gibi
boolean sütunlar VARSA, `mail_router.py` bunlara göre ince ayar yapar
(bir kullanıcı "Hayır" derse o türden mail almaz). Sütunlar YOKSA
(mevcut çoğu kurulumda olduğu gibi) mevcut role-bazlı davranışa
sorunsuzca düşülür — Excel şeması değiştirilmeden çalışır. Gerçek
testle doğrulandı: abonelikten çıkan kişi listeden gerçekten çıkarılıyor.

## Not
`mail_router.py` şu an hiçbir gerçek gönderim akışına bağlı DEĞİL —
her fonksiyonu (region_email_list, admin_copy_email_list,
transfer_recipients) ayrı ayrı, ZATEN çalışan akışlarda (personnel_
notifications.py, worker.py'nin rotasyon akışı) doğrudan kullanılıyor.
mail_router.py, bunları TEK bir arayüz altında toplayan, doğrulanmış
ama henüz hiçbir akışa entegre edilmemiş bir kolaylaştırıcıdır —
bilinçli olarak bir akışa zorla bağlanmadı (mimari genişletme kararı).

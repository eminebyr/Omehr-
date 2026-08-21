# FAST V10-V14 Entegrasyonu + Kritik Kurulum Hatası Düzeltmesi

## ÖNCELİKLİ: Gerçek kurulum hatanız düzeltildi
Yüklediğiniz kurulum logunda şu hata vardı:
```
HATA: Şifre taşıma sırasında sorun oluştu: OperationalError:
table credentials has 9 columns but 8 values were supplied
```
**Kök neden:** `services/security.py::migrate_legacy_input()` içindeki
bir INSERT ifadesi, `credentials` tablosuna `tenant_id` sütunu
eklendiğinde (çok kiracılı SaaS dönüşümü) güncellenmemiş, hâlâ eski
8 sütunluk konumsal `VALUES(...)` sözdizimini kullanıyordu. Bu hata
kurulumun 5/8 adımını (`INITIAL_PASSWORD_IMPORT.py`) BLOKE ediyordu —
her `OMEHR_CURRENT_BASLAT.bat` çalıştırmasında da tekrarlanırdı.

**Düzeltme:** Açık sütun adlarıyla INSERT'e çevrildi, `tenant_id`
doğru şekilde ekleniyor. **Sizin attığınız GERÇEK kurulum adımını
(`INITIAL_PASSWORD_IMPORT.py`) bizzat çalıştırıp doğruladım**: artık
"OK: 12 kullanıcının geçici şifresi güvenli kasaya taşındı" ile
exit kod 0 veriyor.

## FAST V10-V14'ten entegre ettiklerim
| Sürüm | Ne | Durum |
|---|---|---|
| V10 | Toplu İşten Çıkış'ta Streamlit'in ayırdığı `_index` sütun adı kullanılıyordu — bu GERÇEKTEN çökerdi (`StreamlitAPIException`). `Kayıt Satırı` olarak değiştirildi. | **Benim son teslimimde de bu hata vardı, düzeltildi** |
| V11 | Tekli işten çıkışa ayrı Çıkış Kodu alanı + grup uyumluluk kontrolü eklendi; aynı isim+mağaza kombinasyonunda birden fazla kayıt varsa artık `staff_index` ile KESİN satır hedefleniyor (belirsizlikte reddediliyor). | Entegre edildi |
| V13 | Panelden Excel kaydetmede Windows dosya kilidi (kullanıcı Excel'i açık bırakmışsa) artık otomatik yeniden deneniyor; kalıcı kilitte ham WinError yerine anlaşılır mesaj. | Entegre edildi |
| V14 | Üst yönetim şeridi artık gerçekten tam ekran genişliğinde (`100vw` + pozisyon sıfırlama) — önceki `width:100%` bazı durumlarda üst kapsayıcıdan miras kalan kısıtlamayla sağda boş şerit bırakıyordu. Kapanma oku gizleme Streamlit sürümünden bağımsız hale getirildi. | Entegre edildi |

## Doğrulama
- **233/233 test geçiyor**
- `main.py` gerçek veriyle uçtan uca çalıştı (exit 0, 596/607/49/23/-26)
- **Kritik kurulum hatası, sizin attığınız GERÇEK betik çalıştırılarak doğrulandı** (mock değil)

# OMEHR — KVKK Aydınlatma Metni (TASLAK — Hukuki İnceleme Gereklidir)

**Bu belge bir hukuk danışmanı tarafından hazırlanmamıştır. Yasal olarak
kullanıma sunulmadan önce bir avukat/KVKK uzmanı tarafından incelenmesi
ZORUNLUDUR. Bu, yalnızca sizin ekibinizin başlangıç noktası olarak
kullanabileceği bir taslaktır.**

---

## 1. Veri Sorumlusu

**[FİRMA UNVANI]** ("Şirket"), 6698 sayılı Kişisel Verilerin Korunması
Kanunu ("KVKK") uyarınca veri sorumlusu sıfatıyla, OMEHR platformu
("Platform") üzerinden işlediği kişisel verilere ilişkin olarak aşağıda
açıklanan hususlarda sizi bilgilendirmek ister.

## 2. İşlenen Kişisel Veri Kategorileri

Platform, aşağıdaki kişisel veri kategorilerini işler:

| Kategori | Örnek Veri | Kaynak |
|---|---|---|
| Kimlik | Ad, soyad | Fact_Mevcut, Fact_Norm |
| İletişim | E-posta | Mail_Listesi, Sube_Mail_Listesi |
| Özlük | İşe giriş/çıkış tarihi, unvan, departman, çıkış nedeni | Fact_Mevcut |
| Lokasyon | Ev adresi, GPS koordinatı | Personel_Adresleri (KVKK'da özel önemi olan bir alan — bkz. Madde 5) |
| Performans (proxy) | Mağaza bazlı operasyon göstergeleri | Personel_Performans_Endeksi |
| İşlem güvenliği | Kullanıcı adı, şifrelenmiş parola özeti, giriş kayıtları | services/security.py (credentials, security_audit) |

## 3. İşleme Amaçları

- İnsan kaynakları planlaması ve norm kadro optimizasyonu
- Personel transfer/rotasyon süreçlerinin yürütülmesi
- Yasal ve sözleşmesel yükümlülüklerin (bordro, izin, devamsızlık takibi) yerine getirilmesi
- Sistem güvenliğinin sağlanması (giriş denemeleri, denetim izi)

## 4. Hukuki Sebep

KVKK m.5/2 kapsamında: (a) bir sözleşmenin kurulması veya ifasıyla
doğrudan ilgili olması, (b) veri sorumlusunun hukuki yükümlülüğünü
yerine getirebilmesi için zorunlu olması, (c) ilgili kişinin temel hak
ve özgürlüklerine zarar vermemek kaydıyla veri sorumlusunun meşru
menfaati için veri işlenmesinin zorunlu olması.

**[HUKUKİ İNCELEME NOTU: Adres/GPS verisi gibi hassas sayılabilecek
konum verileri için ayrıca AÇIK RIZA alınması gerekip gerekmediği bir
uzman tarafından değerlendirilmelidir.]**

## 5. Özel Nitelikli / Hassas Veriler

Personel_Adresleri sayfasındaki ev adresi ve GPS koordinatı, KVKK
kapsamında özel bir hassasiyet taşır. Platform bu veriye erişimi:
- Yalnızca yetkili İK rolüyle sınırlar (bkz. Bölge Erişim Kontrolü)
- Denetim izi (kim, ne zaman erişti/değiştirdi) tutar

**[HUKUKİ İNCELEME NOTU: Bu verinin KVKK m.6 anlamında "özel nitelikli
kişisel veri" sayılıp sayılmadığı ve ek koruma tedbiri gerekip
gerekmediği değerlendirilmelidir.]**

## 6. Veri Aktarımı

- Kiracı (firma) verisi, aynı Platform'u kullanan BAŞKA firmalarla
  PAYLAŞILMAZ — teknik izolasyon `tenant_id` ile satır düzeyinde
  uygulanır (bkz. `services/input_data_access.py`, `services/tenant_context.py`).
- E-posta bildirimleri (transfer onayı, rotasyon evrakı) Outlook/SMTP
  üzerinden ilgili şube ve bölge sorumlularına gönderilir.
- Power BI entegrasyonu açıksa (`services/powerbi_push.py`), veri
  Microsoft Power BI bulut hizmetine aktarılır.

**[HUKUKİ İNCELEME NOTU: Yurt dışı sunucu kullanılıyorsa (Power BI,
bulut barındırma) KVKK m.9 kapsamında yurt dışına aktarım hükümleri
ayrıca değerlendirilmelidir.]**

## 7. Saklama Süresi

**[DOLDURULACAK: Firma politikanıza ve ilgili mevzuata (İş Kanunu,
Vergi Usul Kanunu vb.) göre saklama süreleri belirlenmelidir. Örnek:
işten ayrılan personelin özlük verisi, ilgili mevzuatta öngörülen süre
kadar saklanır.]**

## 8. İlgili Kişinin Hakları (KVKK m.11)

Kişisel verisi işlenen personel; verisinin işlenip işlenmediğini
öğrenme, işlenmişse buna ilişkin bilgi talep etme, düzeltilmesini veya
silinmesini isteme haklarına sahiptir. Talepler **[İLETİŞİM KANALI —
DOLDURULACAK]** üzerinden iletilebilir.

## 9. Veri Güvenliği Tedbirleri (Teknik Özet)

- Parolalar PBKDF2-HMAC-SHA256 (600.000 iterasyon) ile tuzlanarak saklanır, düz metin hiçbir yerde tutulmaz.
- Başarısız giriş denemeleri sınırlanır, hesap geçici kilitlenir.
- Firma verisi arasında satır bazlı erişim izolasyonu (tenant_id) uygulanır.
- Tüm güvenlik olayları (giriş, şifre değişikliği, kilitlenme) denetim izine (security_audit) kaydedilir.

---
*Bu taslak [TARİH] itibarıyla hazırlanmıştır. Hukuki geçerliliği için avukat onayı gereklidir.*

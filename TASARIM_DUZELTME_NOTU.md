# Web Tasarımı — Profesyonel Yenileme

## Ne değişti
`web/styles.py` sıfırdan, tutarlı bir tasarım sistemi olarak yeniden
yazıldı. Önceki dosya, aylar süren birbirini ezen "yama üstüne yama"
CSS kurallarından oluşuyordu (ör. aynı seçici için 3 farklı yükseklik
kuralı, "yukarıdaki kural bunu eziyordu, burada tekrar zorluyoruz" gibi
yorumlar). Artık:

- **Gerçek bir jeton (design token) sistemi**: renk, boşluk, gölge,
  köşe yuvarlaklığı, tipografi tek bir `:root` bloğunda tanımlı.
- **İmza öge**: KPI kartları artık kalın renkli sol şerit yerine ince
  amber üst çizgi + tablosal (mono) rakamlarla bir "mutabakat
  kartı/hesap özeti" hissi veriyor — bu uygulamanın özü zaten norm
  vs mevcut mutabakatı.
- **Gölge/yükselti sistemi**: kartlar, formlar, tablolar artık tutarlı,
  hafif gölgelerle "kağıttan kalkmış" hissi veriyor.
- **Etkileşim durumları**: buton hover/active/focus-visible (klavye
  odağı görünür — erişilebilirlik), form alanı odaklanma rengi eklendi.
- **Ölü kod temizlendi**: `.omehr-page-tab*` sınıfları hiçbir Python
  dosyasında kullanılmıyordu (navigasyon `st.radio`'ya taşınmış),
  kaldırıldı; gerçek `st.radio` widget'ı artık pill-sekme gibi
  giydiriliyor.

## Palet KORUNDU, değiştirilmedi
Koyu çam yeşili (#143C36) + amber (#C68A33) paleti bilinçli olarak
aynı kaldı — bu renkler zaten PDF raporlarında, Excel çıktılarında ve
SVG başlıkta kullanılıyor; değiştirmek ürün genelinde tutarsızlık
yaratırdı. Yenilenen şey PALET değil, o paletin UYGULANMA KALİTESİ.

## Doğrulama
- **Statik HTML maket + gerçek CSS ile GÖRSEL olarak inceledim**
  (ekte `TASARIM_ONIZLEME.png`) — sandbox'ta canlı Streamlit
  başlatamadığım için bu, mevcut en güvenilir görsel doğrulama yöntemi.
- Tüm daha önce doğrulanmış davranışlar (ikon fontu istisnası, buton/
  kenar çubuğu kontrast sırası, kenar çubuğu üstte yatay şerit, tek
  kaydırma alanı) KORUNDU.
- 188/188 test geçiyor, main.py gerçek veriyle uçtan uca çalıştı.

## Dürüst sınır
Gerçek tarayıcıda canlı görüntü alamadım (sandbox kısıtı) — ekteki
görsel, gerçek CSS'i statik bir DOM maketine uygulayarak üretildi,
gerçek Streamlit widget'larının bazı iç detayları (ör. st.radio'nun
tam DOM yapısı) birebir aynı olmayabilir. Sizin ortamınızda son bir
görsel kontrol öneririm.

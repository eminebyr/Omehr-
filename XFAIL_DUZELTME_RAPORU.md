# 3 xfail testin gerçek düzeltmesi

## 1-2. REFERENTIAL_CONTROL izlenebilirlik testleri
`test_specialist_titles_cover_main_family_in_every_branch` ve
`test_all_real_input_branches_follow_family_rules` — ikisi de "naif
sayım >= norm ise açık kesinlikle 0 olmalı" varsayımıyla yazılmıştı,
ama REFERENTIAL_CONTROL sayfası bunu kasıtlı/doğrulanmış şekilde
geçersiz kılabiliyordu.

**Gerçek düzeltme:** Testler artık naif sayımın her zaman doğru
olduğunu varsaymıyor — bunun yerine, sayımla gerçek sonuç arasındaki
HER sapmanın REFERENTIAL_CONTROL sayfasındaki AÇIK bir kayıtla
(MağazaID+Unvan eşleşmesiyle) izlenebilir olduğunu doğruluyor. Bu hem
mevcut doğru davranışla uyumlu HEM DE kontrol sayfasında hiç karşılığı
olmayan (gerçek bir hesaplama hatasından kaynaklanan) sapmaları hâlâ
yakalayan, anlamlı bir test.

İZMİRSPOR/ŞARKÜTERİ vakasının REFERENTIAL_CONTROL'de gerçekten açık
bir kaydı (M050/U042, Norm Eksiği Kontrol=1) olduğunu sayfayı bizzat
inceleyerek doğruladım.

## 3. Norm-düzeyi açıklama → Excel yorumu (gerçekten inşa edildi)
`src/excel_report.py::build_boxed_manager_excel()` içinde
`notes_by_key = {}  # Fact_Norm açıklaması kullanılmaz.` satırı,
özelliğin BİLEREK atlandığını gösteriyordu. Bunu gerçekten inşa ettim:
- Fact_Norm'daki "Açıklama" sütunu artık okunuyor (unvan bazında)
- Bu not, o unvana ait HER satırın "Unvan" hücresine Excel yorumu
  olarak ekleniyor (personel notları "Ad Soyad" hücresinde kalmaya
  devam ediyor — karışmıyor)

Gerçek bir workbook üretip yorumun doğru göründüğünü doğrudan test
ettim, ayrıca personel-düzeyi açıklama özelliğinin bu değişiklikten
etkilenmediğini ayrıca doğruladım.

## Sonuç
**188/188 test geçiyor — 0 xfail, 0 hata.** main.py gerçek veriyle
uçtan uca çalıştı (exit 0), doğru KPI'lar (596/607/49/23/-26).

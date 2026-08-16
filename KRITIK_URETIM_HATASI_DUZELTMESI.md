# Kritik, Canlı Üretim Hatası — Kutucuklu Yönetici Raporu

## Bulduğum hata (kendi önceki değerlendirmemi düzeltiyorum)
Bir önceki turda "family_balance.py üretime hiç bağlı değil, orphan
bir modül" demiştim — bu YANLIŞTI. Daha derin bir mimari taramada
gerçeği buldum: **bu modül, `src/excel_report.py::build_boxed_
manager_excel()` üzerinden "Kutucuklu Yönetici Raporu"nun GERÇEK
üretiminde kullanılıyordu.**

Bu, önceden bulduğum "0 ana personel + N yardımcı" güvenlik açığının
yalnız teorik bir risk değil, **gerçekten üretimde çalışan bir hata**
olduğu anlamına geliyordu. Kanıtladım: kurulmuş, doğrulanmış test
senaryosunda (MANAV normu 2, 0 gerçek MANAV, 2 MANAV YARDIMCISI)
rapor **Norm Eksiği=0** üretiyordu — doğrusu **2**. Yani bir mağazada
o rolde HİÇ nitelikli personel olmasa bile rapor "tam kadrolu"
gösterebiliyordu.

## Düzeltme
`services/family_balance.py::balance_store_title_rows()`'a,
`src/state_engine.py`'nin zaten doğrulanmış güvenlik kuralını
(ana unvanda en az 1 gerçek kişi yoksa dengeleme tamamen atlanır)
ekledim. **Kesin son kanıt**: aynı senaryoyu `state_engine.py`'ye
(yetkili referans) sorduğumda AYNI "kapatmama" davranışını verdi.

## Ek bulgu: 2 eski test de aynı hatalı varsayımı taşıyordu
Düzeltmemi uyguladıktan sonra `test_family_balance_all_stores.py`'deki
2 test kırıldı — incelemede bu testlerin de "0 ana personelle bile
norm kapanmalı" gibi YANLIŞ bir beklenti kodladığı ortaya çıktı
(`state_engine.py`'ye TAM aynı senaryoyu sorup kanıtladım). Bu 2 testi
doğru davranışı yansıtacak şekilde güncelledim, ayrıca meşru mahsup
senaryosunu (ana unvan yeterince personelliyken) doğrulayan yeni bir
test ekledim.

## Doğrulama
- Gerçek üretim verisiyle kutucuklu raporu yeniden ürettim, hatasız
  çalıştı
- **255/255 test geçiyor** (5 yeni/düzeltilmiş test)
- Mimari + regresyon bariyerleri temiz
- main.py uçtan uca çalıştı (596/607/49/23/-26)

## Ders
Bu, "mimariyi incele" göreviyle başlayıp gerçek bir üretim hatası
bulmakla sonuçlanan ikinci örnek. İlk seferki "orphan modül" kararımı
ROSDA doğrulamadan (yalnız state_engine.py'de arayıp excel_report.py'yi
kontrol etmeden) vermiştim — bu, "körü körüne güvenme, doğrula" ilkesinin
kendi çalışmamda bile ne kadar önemli olduğunu gösteriyor.

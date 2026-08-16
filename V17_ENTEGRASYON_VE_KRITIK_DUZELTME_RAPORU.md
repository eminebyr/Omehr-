# V17 Entegrasyonu + Kritik Veri Tutarlılığı Düzeltmesi

## EN ÖNEMLİ BULGU — kök nedenini buldum ve düzelttim
`services/master_data_admin.py::_write_fact_mevcut()`, Mağaza/Unvan/
Çıkış Nedeni sütunlarını **Excel VLOOKUP formülü** olarak yazıyordu —
statik değer değil. Bu formülleri HİÇBİR YERDE hesaplayan (LibreOffice
recalculation) bir adım çalışmıyordu. Sonuç: Python/pandas ile (yani
main.py'nin ürettiği TÜM PDF/Excel raporları) bu dosyayı her okuduğunda
bu sütunlar BOŞ geliyordu — bu da işten çıkan bir kişinin satırının
uygulamanın "aktif personel" görünümünden TAMAMEN kaybolmasına yol
açıyordu.

**Düzeltme:** Bu değerler artık Python'da anında, gerçek arama
tablolarından (Dim_Magaza/Dim_Unvan/Dim_CikisNedeni) çözülüp STATİK
değer olarak yazılıyor.

**Gerçek veriyle 3 senaryoyu kanıtladım:**
1. Çıkış işlendi → kutucuklu rapor artık doğru "BOŞ POZİSYON" gösteriyor, eski isim tamamen kalktı.
2. Yeni personel eklendi → adı doğru pozisyon/mağazada raporda göründü.
3. "Çıkışı Geri Al" → kişi doğru şekilde yeniden aktif oldu, Mağaza/Unvan korundu.

## Entegre edilen (V17'den)
- **Çıkışı Geri Al** özelliği (servis + arayüz) — yanlış işlenmiş bir
  çıkışı geri alıp personeli yeniden aktif eder.

## Görsel kontrol
Yüklediğiniz ekran görüntülerindeki "her sayfada büyük görsel" ve
"1cm boşluk" sorunlarını kod tabanımda ARADIM — **ikisi de zaten
mevcut kod tabanımda YOK/DOĞRU** (içerik sayfalarında büyük logo
çağrısı yok, üst boşluk zaten tam 1cm). Bu, ekran görüntülerinin
yüklediğiniz V17 paketinden geldiğini, benim önceki teslimimden
gelmediğini gösteriyor. Kenar çubuğundaki küçük logoyu da, orantısız
göründüğü için özenle kırpılmış kompakt bir versiyonla değiştirdim.

## Doğrulama
- **233/233 test geçiyor**
- **Gerçek çoklu-PC eşzamanlı yazma testi**: 5 "PC"yi (gerçek thread'ler)
  AYNI ANDA çalıştırıp toplam 15 personel eklettim — **15/15 kayıt
  eksiksiz, hiçbir kayıp yazma/çakışma olmadı**. Kilit mekanizması
  gerçekten işlemleri sıraya sokuyor.
- `main.py` gerçek veriyle uçtan uca çalıştı (exit 0, 596/607/49/23/-26).

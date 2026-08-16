# OMEHR Hızlandırma Şartnamesi — İlerleme Raporu #2 (Madde 6-7)

## Madde 6: Excel Change Watcher
`services/multi_pc_sync.py` ZATEN tam şartname kapsamında (dosya
mtime/boyut BİRİNCİ seviye + sayfa içerik hash'i İKİNCİ seviye,
`detect_changed_sheets()`) — muhtemelen bu oturumun önceki bir
bölümünde kurulmuş. Gerçek bir testte İLK ÇAĞRIDA beklenmedik bir
"yanlış pozitif" (Fact_Norm + Dim_Magaza da değişti göründü)
gördüm — araştırmada bunun HATA olmadığı, `master_data_admin.py`'nin
yazma sürecinin kirli veriyi (sondaki boşluklu "BUCA ") TEMİZLEDİĞİ
(TEK SEFERLİK) ortaya çıktı. İkinci testte, veri temizken yalnız
GERÇEKTEN değişen sayfanın doğru tespit edildiği kanıtlandı.

## Madde 7: Change Manifest
`services/change_manifest.py` ZATEN mevcuttu ve `personnel_exit.py`'nin
çıkış akışına bağlıydı — şartnamedeki örnek formatla birebir eşleşiyor.
Ama gerçek veriyle test ederken **iki gerçek hata** buldum:

1. **613 sahte kayıt**: Fact_Mevcut'ta hâlâ Excel formülü olan 3 sütun
   (Norm fazlası Norm eksiği, Kıdem Gün/Yıl) her okunduğunda boş/None
   döndüğü için HER yazma işleminde "değişti" görünüyordu. Bu sütunların
   uygulamanın başka hiçbir yerinde okunmadığını doğruladıktan sonra,
   manifest karşılaştırmasından güvenle hariç tutuldu.
2. **Sahte silindi+eklendi çiftleri**: anahtar sütunundaki (İsim
   Soyisim) boşluk farkı, aynı kişinin YANLIŞLIKLA "silindi + yeniden
   eklendi" görünmesine yol açıyordu. Anahtar karşılaştırması artık
   normalleştirilmiş (strip edilmiş) metinle yapılıyor.

**Sonuç: 613 → 13 anlamlı kayıt** (gerçek veri değişikliğiyle test
edildi).

## Doğrulama
270/270 test geçiyor (4 yeni test eklendi), mimari + regresyon
bariyerleri temiz, main.py uçtan uca çalıştı (596/607/49/23/-26).

## Sırada
Madde 8-10 (Genel Özet, CEO Özeti, Personel Kartları hız hedefleri —
gerçek cold/warm ölçümü) ile devam edilecek.

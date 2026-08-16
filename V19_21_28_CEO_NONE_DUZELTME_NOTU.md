# CEO Özeti `None` Norm Alanları Düzeltmesi

CEO Özeti > Mağaza KPI Skor Kartı > Tüm mağazalar ve bileşen puanları tablosunda Excel formülleri henüz hesaplanmadığında `None` görünen şu alanlar düzeltildi:

- Norm Kadro
- Norm Eksiği
- Norm Fazlası
- Norm Uyumu Puanı

Bu alanlar artık Excel formül önbelleğine bağımlı değildir. Eksik değerler Python motorunun güncel mağaza-unvan detay tablosundan mağaza bazında tamamlanır. Norm Uyumu Puanı, gerektiğinde `(1 - (Eksik + Fazla) / Norm) × 100` formülüyle 0-100 aralığında hesaplanır.

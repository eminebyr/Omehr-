# AI model seçimi ve veri kapısı düzeltmesi

- Ciro, fiş/müşteri yoğunluğu, ortalama sepet, online sipariş, mal kabul, fazla mesai, devamsızlık, fire, performans, pik katsayısı ve kapasite metrikleri model girdisi olarak korunmuştur.
- Regresyon adayları mağaza bazlı GroupKFold ile karşılaştırılır; en düşük CV MAE ve RMSE değerine sahip model seçilir.
- Seçilen model, formül tabanlı iş yükü FTE ile birlikte kullanılır; yönetim normu resmî ankrajdır.
- Standart sürelerin en az %70'i saha etüdüyle doğrulanmadan AI kadro önerisi yayımlanmaz.
- Veri kapısı kapalıysa model karşılaştırması ve simülasyon sonuçları görülebilir, fakat `AI Önerilen Norm` doğrudan `Fact_Norm` değerini korur.
- Yönetim normu 0 olan yeni pozisyon, yalnız yüksek güvenli ve doğrulanmış gerçek veriyle en fazla 1 kişi olarak önerilebilir.
- AI sonucu hiçbir zaman Fact_Norm'u otomatik değiştirmez.

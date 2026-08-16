# Tüm Şubeler Ana/Yardımcı Aile Denge Düzeltmesi

Bu sürümde aşağıdaki aileler tüm mağazalarda aynı kuralla kontrol edilir:

- Yönetici / Yönetici Yardımcısı
- Manav / Manav Yardımcısı
- Şarküteri / Şarküteri Yardımcısı
- Kasap / Kasap Yardımcısı

Ana ve yardımcı unvan satırları raporda ayrı kalır. Ancak aynı ailedeki toplam aktif personel, toplam normu karşılıyorsa görev dağılımından doğan yapay eksik ve fazla KPI toplamına dahil edilmez. Mevcut Durum Açıklaması bölümünde kadronun aile içinde dengelenebileceği yazılır.

Örnek: Yönetici normu 1, Yönetici Yardımcısı normu 1 ve mevcutta 2 Yönetici Yardımcısı varsa eksik 0, fazla 0 kabul edilir; açıklamada aile içi denge belirtilir.

## Güncelleme: niteliksel uyarı artık panelde görünüyor
Ana unvanda hiç (veya asgari eşiğin altında) gerçek personel yokken
aile dengesiyle Eksik/Fazla 0'a çekilen satırlar için, bu bilgi KPI
sayısını bozmadan **Unvan Analizi** ekranında "Yetkinlik Uyarısı"
sütunuyla ayrıca gösterilir: "⚠ Ana unvanda doğrudan görevli personel
yok". Böylece mağazada bu rolde kimsenin doğrudan görevli olmadığı
bilgisi, KPI dengelemesi sırasında kaybolmaz.

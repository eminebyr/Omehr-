"""OMEHR özel hata sınıfları.

Amaç: "except Exception" ile her şeyi tek bir çatı altında yakalamak yerine,
kod tabanının önemli sınır noktalarında (dosya/Excel işlemleri, mail
gönderimi, transfer onay akışı, yapılandırma okuma, yetkilendirme) NEYİN
başarısız olduğunu türünden anlaşılır kılmak. Bu, hem loglarda hem de (ileride)
web panelinde kullanıcıya "bir şeyler ters gitti" yerine "input dosyası
kilitli" gibi anlamlı bir mesaj göstermeyi mümkün kılar.

Kullanım ilkesi:
  - Beklenmeyen/programlama hatalarını (AttributeError, KeyError, TypeError
    gibi gerçek bug'ları) BU sınıflara SARMALAMAYIN — onlar olduğu gibi
    yükselmeli ki fark edilsin.
  - Bu sınıflar, "bu türden bir başarısızlık OLABİLİR ve normal karşılanır"
    dediğiniz noktalarda, dış kütüphanelerin (openpyxl, smtplib, sqlite3 vb.)
    fırlattığı çeşitli hataları TEK, öngörülebilir bir tipe indirgemek için
    kullanılır.
"""
from __future__ import annotations


class BasdasError(Exception):
    """Tüm OMEHR'e özel hataların ortak temel sınıfı.

    `except BasdasError` ile "bilinen/beklenen" hata türlerinin tamamı tek
    seferde yakalanabilir; gerçekten beklenmeyen (programlama) hatalar bu
    sınıfın dışında kalıp yükselmeye devam eder.
    """


class WorkbookError(BasdasError):
    """Input/rapor Excel dosyasının okunması, kilitlenmesi, yedeklenmesi
    veya geri yüklenmesiyle ilgili hatalar (bozuk dosya, kilitli dosya,
    beklenmeyen sayfa/sütun eksikliği vb.)."""


class MailDeliveryError(BasdasError):
    """Outlook COM veya SMTP üzerinden e-posta gönderiminin başarısız
    olduğu durumlar (sunucu erişilemez, kimlik doğrulama hatası, geçersiz
    alıcı/ek dosya vb.)."""


class TransferConflictError(BasdasError):
    """Bir transfer talebinin normal iş kurallarına göre işlenemediği
    durumlar (örn. hedef mağazada artık norm eksiği kalmamış, personel
    zaten başka bir bekleyen transferde, kaynak kayıt bulunamadı vb.)."""


class ConfigurationError(BasdasError):
    """Yapılandırma dosyalarının (config_*.json, .env, tenants.json)
    okunamadığı, eksik/geçersiz olduğu durumlar."""


class AuthorizationError(BasdasError):
    """Bir kullanıcının rolü/yetki kapsamı, istediği işlem için yeterli
    olmadığında (örn. onay yetkisi olmayan kullanıcının transferi
    onaylamaya çalışması) fırlatılır."""

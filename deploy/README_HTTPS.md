# HTTPS Kurulumu

## Neden zorunlu
Kullanıcı adı/şifre ve firma verisi düz metin HTTP üzerinden ASLA
gönderilmemelidir. `docker-compose.yml` artık yalnız nginx'i (80/443)
dışa açar; uygulama servisi (`app`) yalnız Docker iç ağından erişilebilir.

## Yerel/deneme kurulumu (öz-imzalı sertifika)
```bash
./deploy/gecici_sertifika_uret.sh
docker compose up -d
```
Tarayıcı "güvensiz bağlantı" uyarısı verir — bu YEREL TEST için normaldir,
gerçek müşteriye bu şekilde gösterilmemelidir.

## Üretim kurulumu (Let's Encrypt / certbot)
1. Alan adınızı (ör. `omehr.sizinfirmaniz.com`) sunucunuzun IP'sine yönlendirin.
2. certbot ile gerçek sertifika alın (webroot yöntemi, `certbot_webroot`
   volume'u zaten `docker-compose.yml`'de nginx'e bağlı):
   ```bash
   docker run --rm -v omehr_certbot_webroot:/var/www/certbot \
     -v $(pwd)/deploy/certs:/etc/letsencrypt \
     certbot/certbot certonly --webroot -w /var/www/certbot \
     -d omehr.sizinfirmaniz.com --email destek@sizinfirmaniz.com --agree-tos
   ```
3. `deploy/certs/fullchain.pem` ve `deploy/certs/privkey.pem` dosyalarının
   certbot'un ürettiği gerçek sertifikaya işaret ettiğinden emin olun.
4. Sertifika 90 günde bir yenilenmelidir — bir cron/systemd timer ile
   `certbot renew` otomatikleştirilmelidir (bu paket bunu OTOMATİKLEŞTİRMEZ,
   üretim dağıtımını yapan ekip kurmalıdır).

## Dürüst sınır
Bu paket size çalışan bir nginx+TLS iskeleti verir; GERÇEK bir sertifika
tedariki ve alan adı yönlendirmesi sizin altyapı ekibinizin yapması
gereken, dış bağımlılığı olan adımlardır — burada simüle edilemez.

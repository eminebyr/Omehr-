#!/bin/sh
# YALNIZCA yerel/deneme kullanımı için ÖZ-İMZALI sertifika üretir.
# GERÇEK/ÜRETİM kullanımı için Let's Encrypt (certbot) veya kurumsal bir
# CA'dan gerçek sertifika alınmalıdır — tarayıcılar öz-imzalı sertifikayı
# "güvensiz" olarak işaretler, müşteri firmalara bu şekilde gösterilmemelidir.
set -e
cd "$(dirname "$0")/certs"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem -out fullchain.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost"
echo "Öz-imzalı sertifika üretildi: deploy/certs/fullchain.pem, deploy/certs/privkey.pem"
echo "UYARI: bu sertifika yalnız YEREL TEST için kullanılmalıdır."

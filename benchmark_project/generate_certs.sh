#!/bin/bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -nodes -out certs/server.crt -keyout certs/server.key -days 365 \
-subj "/C=ID/ST=Jakarta/L=Jakarta/O=TestOrg/OU=TestUnit/CN=localhost"
echo "Sertifikat dan kunci telah dibuat di direktori certs/"
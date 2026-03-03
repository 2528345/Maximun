#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="${1:-$ROOT_DIR/gateway-mqtt/certs}"
DAYS="${MQTT_TLS_CERT_DAYS:-3650}"
CN="${MQTT_TLS_CN:-gateway-mqtt}"

mkdir -p "$CERT_DIR"

if ! command -v openssl >/dev/null 2>&1; then
  echo "[FATAL] openssl no encontrado"
  exit 2
fi

echo "[INFO] Generando CA..."
openssl genrsa -out "$CERT_DIR/ca.key" 4096
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days "$DAYS" \
  -subj "/CN=MAXIMUN-MQTT-CA" -out "$CERT_DIR/ca.crt"

echo "[INFO] Generando certificado servidor..."
openssl genrsa -out "$CERT_DIR/server.key" 4096
openssl req -new -key "$CERT_DIR/server.key" -subj "/CN=${CN}" -out "$CERT_DIR/server.csr"
openssl x509 -req -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
  -CAcreateserial -out "$CERT_DIR/server.crt" -days "$DAYS" -sha256

rm -f "$CERT_DIR/server.csr"
chmod 600 "$CERT_DIR/"*.key

echo "[OK] Certificados generados en: $CERT_DIR"
echo "     - ca.crt"
echo "     - server.crt"
echo "     - server.key"


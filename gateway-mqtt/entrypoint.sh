#!/bin/sh
set -eu

CONF_FILE="${MQTT_CONFIG_FILE:-/mosquitto/config/mosquitto.conf}"
PASS_FILE="${MQTT_PASSWORD_FILE:-/mosquitto/config/passwd}"
CERTS_DIR="${MQTT_CERTS_DIR:-/mosquitto/config/certs}"

MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_WS_PORT="${MQTT_WS_PORT:-9001}"
MQTT_TLS_PORT="${MQTT_TLS_PORT:-8883}"

MQTT_USERNAME="${MQTT_USERNAME:-maximun}"
MQTT_PASSWORD="${MQTT_PASSWORD:-maximun_local_change_me}"

MQTT_ALLOW_ANONYMOUS="${MQTT_ALLOW_ANONYMOUS:-false}"
MQTT_WS_ALLOW_ANONYMOUS="${MQTT_WS_ALLOW_ANONYMOUS:-false}"
MQTT_TLS_ENABLE="${MQTT_TLS_ENABLE:-false}"
MQTT_TLS_ALLOW_ANONYMOUS="${MQTT_TLS_ALLOW_ANONYMOUS:-false}"

MQTT_TLS_CA_FILE="${MQTT_TLS_CA_FILE:-${CERTS_DIR}/ca.crt}"
MQTT_TLS_CERT_FILE="${MQTT_TLS_CERT_FILE:-${CERTS_DIR}/server.crt}"
MQTT_TLS_KEY_FILE="${MQTT_TLS_KEY_FILE:-${CERTS_DIR}/server.key}"

need_password_file="false"
if [ "${MQTT_ALLOW_ANONYMOUS}" != "true" ] || [ "${MQTT_WS_ALLOW_ANONYMOUS}" != "true" ]; then
  need_password_file="true"
fi
if [ "${MQTT_TLS_ENABLE}" = "true" ] && [ "${MQTT_TLS_ALLOW_ANONYMOUS}" != "true" ]; then
  need_password_file="true"
fi

if [ "${need_password_file}" = "true" ]; then
  mosquitto_passwd -b -c "${PASS_FILE}" "${MQTT_USERNAME}" "${MQTT_PASSWORD}"
  chmod 600 "${PASS_FILE}"
fi

cat > "${CONF_FILE}" <<EOF
persistence false
per_listener_settings true

listener ${MQTT_PORT} 0.0.0.0
protocol mqtt
allow_anonymous ${MQTT_ALLOW_ANONYMOUS}
EOF

if [ "${MQTT_ALLOW_ANONYMOUS}" != "true" ]; then
  printf "password_file %s\n" "${PASS_FILE}" >> "${CONF_FILE}"
fi

cat >> "${CONF_FILE}" <<EOF

listener ${MQTT_WS_PORT} 0.0.0.0
protocol websockets
allow_anonymous ${MQTT_WS_ALLOW_ANONYMOUS}
EOF

if [ "${MQTT_WS_ALLOW_ANONYMOUS}" != "true" ]; then
  printf "password_file %s\n" "${PASS_FILE}" >> "${CONF_FILE}"
fi

if [ "${MQTT_TLS_ENABLE}" = "true" ]; then
  if [ -f "${MQTT_TLS_CA_FILE}" ] && [ -f "${MQTT_TLS_CERT_FILE}" ] && [ -f "${MQTT_TLS_KEY_FILE}" ]; then
    cat >> "${CONF_FILE}" <<EOF

listener ${MQTT_TLS_PORT} 0.0.0.0
protocol mqtt
allow_anonymous ${MQTT_TLS_ALLOW_ANONYMOUS}
cafile ${MQTT_TLS_CA_FILE}
certfile ${MQTT_TLS_CERT_FILE}
keyfile ${MQTT_TLS_KEY_FILE}
require_certificate false
tls_version tlsv1.2
EOF
    if [ "${MQTT_TLS_ALLOW_ANONYMOUS}" != "true" ]; then
      printf "password_file %s\n" "${PASS_FILE}" >> "${CONF_FILE}"
    fi
  else
    echo "[gateway-mqtt] MQTT_TLS_ENABLE=true pero faltan certificados. TLS deshabilitado." >&2
  fi
fi

exec /usr/sbin/mosquitto -c "${CONF_FILE}"


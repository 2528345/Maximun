#!/bin/sh
set -eu

CONF_FILE="${MQTT_CONFIG_FILE:-/mosquitto/config/mosquitto.conf}"
PASS_FILE="${MQTT_PASSWORD_FILE:-/mosquitto/config/passwd}"
ACL_FILE="${MQTT_ACL_FILE:-/mosquitto/config/acl}"
CERTS_DIR="${MQTT_CERTS_DIR:-/mosquitto/config/certs}"

MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_WS_PORT="${MQTT_WS_PORT:-9001}"
MQTT_TLS_PORT="${MQTT_TLS_PORT:-8883}"

MQTT_USERNAME="${MQTT_USERNAME:-maximun}"
MQTT_PASSWORD="${MQTT_PASSWORD:-maximun_local_change_me}"

MQTT_CORE_USERNAME="${MQTT_CORE_USERNAME:-core}"
MQTT_CORE_PASSWORD="${MQTT_CORE_PASSWORD:-$MQTT_PASSWORD}"
MQTT_AUDIO_USERNAME="${MQTT_AUDIO_USERNAME:-audio}"
MQTT_AUDIO_PASSWORD="${MQTT_AUDIO_PASSWORD:-$MQTT_PASSWORD}"
MQTT_VISION_USERNAME="${MQTT_VISION_USERNAME:-vision}"
MQTT_VISION_PASSWORD="${MQTT_VISION_PASSWORD:-$MQTT_PASSWORD}"
MQTT_RAG_USERNAME="${MQTT_RAG_USERNAME:-rag}"
MQTT_RAG_PASSWORD="${MQTT_RAG_PASSWORD:-$MQTT_PASSWORD}"
MQTT_IOT_USERNAME="${MQTT_IOT_USERNAME:-iot}"
MQTT_IOT_PASSWORD="${MQTT_IOT_PASSWORD:-$MQTT_PASSWORD}"
MQTT_DASHBOARD_USERNAME="${MQTT_DASHBOARD_USERNAME:-dashboard}"
MQTT_DASHBOARD_PASSWORD="${MQTT_DASHBOARD_PASSWORD:-$MQTT_PASSWORD}"
MQTT_OPS_USERNAME="${MQTT_OPS_USERNAME:-ops}"
MQTT_OPS_PASSWORD="${MQTT_OPS_PASSWORD:-$MQTT_PASSWORD}"

MQTT_ENABLE_ACL="${MQTT_ENABLE_ACL:-true}"
MQTT_ENABLE_ADMIN_FALLBACK="${MQTT_ENABLE_ADMIN_FALLBACK:-false}"

MQTT_ALLOW_ANONYMOUS="${MQTT_ALLOW_ANONYMOUS:-false}"
MQTT_WS_ALLOW_ANONYMOUS="${MQTT_WS_ALLOW_ANONYMOUS:-false}"
MQTT_TLS_ENABLE="${MQTT_TLS_ENABLE:-false}"
MQTT_TLS_ALLOW_ANONYMOUS="${MQTT_TLS_ALLOW_ANONYMOUS:-false}"

MQTT_TLS_CA_FILE="${MQTT_TLS_CA_FILE:-${CERTS_DIR}/ca.crt}"
MQTT_TLS_CERT_FILE="${MQTT_TLS_CERT_FILE:-${CERTS_DIR}/server.crt}"
MQTT_TLS_KEY_FILE="${MQTT_TLS_KEY_FILE:-${CERTS_DIR}/server.key}"
MQTT_ENFORCE_STRONG_PASSWORD="${MQTT_ENFORCE_STRONG_PASSWORD:-false}"

normalize_role_password() {
  value="$1"
  if [ "$value" = "maximun_local_change_me" ] || [ "$value" = "CAMBIAR_ESTA_CLAVE_SEGURA" ] || [ -z "$value" ]; then
    echo "$MQTT_PASSWORD"
    return 0
  fi
  echo "$value"
}

MQTT_CORE_PASSWORD="$(normalize_role_password "${MQTT_CORE_PASSWORD}")"
MQTT_AUDIO_PASSWORD="$(normalize_role_password "${MQTT_AUDIO_PASSWORD}")"
MQTT_VISION_PASSWORD="$(normalize_role_password "${MQTT_VISION_PASSWORD}")"
MQTT_RAG_PASSWORD="$(normalize_role_password "${MQTT_RAG_PASSWORD}")"
MQTT_IOT_PASSWORD="$(normalize_role_password "${MQTT_IOT_PASSWORD}")"
MQTT_DASHBOARD_PASSWORD="$(normalize_role_password "${MQTT_DASHBOARD_PASSWORD}")"
MQTT_OPS_PASSWORD="$(normalize_role_password "${MQTT_OPS_PASSWORD}")"

need_password_file="false"
if [ "${MQTT_ALLOW_ANONYMOUS}" != "true" ] || [ "${MQTT_WS_ALLOW_ANONYMOUS}" != "true" ]; then
  need_password_file="true"
fi
if [ "${MQTT_TLS_ENABLE}" = "true" ] && [ "${MQTT_TLS_ALLOW_ANONYMOUS}" != "true" ]; then
  need_password_file="true"
fi

check_password_strength() {
  value="$1"
  if [ "${MQTT_ENFORCE_STRONG_PASSWORD}" != "true" ]; then
    return 0
  fi
  if [ "$value" = "maximun_local_change_me" ] || [ "$value" = "CAMBIAR_ESTA_CLAVE_SEGURA" ]; then
    echo "[gateway-mqtt] Password por defecto detectada con MQTT_ENFORCE_STRONG_PASSWORD=true." >&2
    exit 2
  fi
  if [ "${#value}" -lt 16 ]; then
    echo "[gateway-mqtt] Password demasiado corta (minimo 16) con MQTT_ENFORCE_STRONG_PASSWORD=true." >&2
    exit 2
  fi
}

append_user() {
  user="$1"
  pass="$2"
  [ -n "$user" ] || return 0
  check_password_strength "$pass"
  if [ ! -f "${PASS_FILE}" ]; then
    mosquitto_passwd -b -c "${PASS_FILE}" "${user}" "${pass}"
  else
    mosquitto_passwd -b "${PASS_FILE}" "${user}" "${pass}"
  fi
}

if [ "${need_password_file}" = "true" ]; then
  rm -f "${PASS_FILE}"
  append_user "${MQTT_CORE_USERNAME}" "${MQTT_CORE_PASSWORD}"
  append_user "${MQTT_AUDIO_USERNAME}" "${MQTT_AUDIO_PASSWORD}"
  append_user "${MQTT_VISION_USERNAME}" "${MQTT_VISION_PASSWORD}"
  append_user "${MQTT_RAG_USERNAME}" "${MQTT_RAG_PASSWORD}"
  append_user "${MQTT_IOT_USERNAME}" "${MQTT_IOT_PASSWORD}"
  append_user "${MQTT_DASHBOARD_USERNAME}" "${MQTT_DASHBOARD_PASSWORD}"
  append_user "${MQTT_OPS_USERNAME}" "${MQTT_OPS_PASSWORD}"

  if [ "${MQTT_ENABLE_ADMIN_FALLBACK}" = "true" ]; then
    append_user "${MQTT_USERNAME}" "${MQTT_PASSWORD}"
  fi
  chmod 600 "${PASS_FILE}"
fi

if [ "${MQTT_ENABLE_ACL}" = "true" ] && [ "${need_password_file}" = "true" ]; then
  cat > "${ACL_FILE}" <<EOF
user ${MQTT_CORE_USERNAME}
topic read perception/audio/transcription
topic read perception/vision/analysis_result
topic read cognition/rag/result
topic read action/engineering/approval
topic read cognition/engineering/feedback
topic read system/integrity/self_test
topic read system/brain/load
topic read system/brain/load/#
topic read system/audit/override
topic write system/#
topic write action/#
topic write project/#
topic write cognition/#

user ${MQTT_AUDIO_USERNAME}
topic read action/speech/request
topic read system/resource/pause
topic write perception/audio/transcription
topic write action/speech/played
topic write system/audio/#
topic write system/error

user ${MQTT_VISION_USERNAME}
topic read system/resource/status
topic read perception/vision/request_analysis
topic write perception/vision/#
topic write system/vision/#
topic write system/error

user ${MQTT_RAG_USERNAME}
topic read cognition/rag/query
topic read cognition/rag/upsert
topic read cognition/rag/delete
topic read cognition/rag/index/rebuild
topic read cognition/rag/feedback
topic read cognition/rag/ingest_path
topic read cognition/rag/stats/get
topic read system/integrity/self_test
topic write cognition/rag/result
topic write cognition/rag/status
topic write cognition/rag/index/status
topic write system/rag/#
topic write system/integrity/report
topic write system/error

user ${MQTT_IOT_USERNAME}
topic read iot/gateway/command
topic read iot/bluetooth/scan/request
topic read iot/zigbee/scan/request
topic read iot/industrial/request
topic read system/resource/pause
topic write system/iot/#
topic write iot/gateway/response
topic write perception/iot/#
topic write system/error

user ${MQTT_DASHBOARD_USERNAME}
topic read system/#
topic read cognition/#
topic read project/#
topic read action/#
topic write system/resource/pause
topic write system/brain/load/qwen
topic write system/audit/override
topic write perception/vision/request_analysis
topic write cognition/engineering/feedback
topic write cognition/rag/feedback
topic write action/engineering/approval

user ${MQTT_OPS_USERNAME}
topic read #
topic write health/#
topic write perception/audio/transcription
topic write perception/vision/request_analysis
topic write iot/bluetooth/scan/request
topic write iot/zigbee/scan/request
topic write iot/industrial/request
topic write cognition/rag/query
topic write cognition/rag/ingest_path
topic write cognition/rag/stats/get
topic write system/integrity/self_test
EOF

  if [ "${MQTT_ENABLE_ADMIN_FALLBACK}" = "true" ]; then
    cat >> "${ACL_FILE}" <<EOF

user ${MQTT_USERNAME}
topic readwrite #
EOF
  fi
  chmod 600 "${ACL_FILE}"
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
  if [ "${MQTT_ENABLE_ACL}" = "true" ]; then
    printf "acl_file %s\n" "${ACL_FILE}" >> "${CONF_FILE}"
  fi
fi

cat >> "${CONF_FILE}" <<EOF

listener ${MQTT_WS_PORT} 0.0.0.0
protocol websockets
allow_anonymous ${MQTT_WS_ALLOW_ANONYMOUS}
EOF

if [ "${MQTT_WS_ALLOW_ANONYMOUS}" != "true" ]; then
  printf "password_file %s\n" "${PASS_FILE}" >> "${CONF_FILE}"
  if [ "${MQTT_ENABLE_ACL}" = "true" ]; then
    printf "acl_file %s\n" "${ACL_FILE}" >> "${CONF_FILE}"
  fi
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
      if [ "${MQTT_ENABLE_ACL}" = "true" ]; then
        printf "acl_file %s\n" "${ACL_FILE}" >> "${CONF_FILE}"
      fi
    fi
  else
    echo "[gateway-mqtt] MQTT_TLS_ENABLE=true pero faltan certificados. TLS deshabilitado." >&2
  fi
fi

exec /usr/sbin/mosquitto -c "${CONF_FILE}"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
BROKER_CONTAINER="${BROKER_CONTAINER:-gateway-mqtt}"

AUTOCHECK_INTERVAL_SEC="${AUTOCHECK_INTERVAL_SEC:-25}"
AUTOCHECK_AUTOSTART="${AUTOCHECK_AUTOSTART:-true}"

MQTT_PORT="1883"
MQTT_USERNAME=""
MQTT_PASSWORD=""
ENABLE_UI="false"
ENABLE_VISION="false"
ENABLE_IOT="false"

usage() {
  cat <<USAGE
Uso:
  ./ops/autocheck_modules.sh --once
  ./ops/autocheck_modules.sh --daemon

Opciones:
  --once    Ejecuta un ciclo de verificacion y autocorreccion, luego termina.
  --daemon  Ejecuta ciclos continuos cada AUTOCHECK_INTERVAL_SEC.
USAGE
}

is_true() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

env_get() {
  local key="$1"
  local default="${2:-}"
  local value=""
  if [[ -f "$ENV_FILE" ]]; then
    value="$(grep "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
  fi
  if [[ -n "$value" ]]; then
    echo "$value"
  else
    echo "$default"
  fi
}

load_config() {
  ENABLE_UI="$(env_get ENABLE_UI "$ENABLE_UI")"
  ENABLE_VISION="$(env_get ENABLE_VISION "$ENABLE_VISION")"
  ENABLE_IOT="$(env_get ENABLE_IOT "$ENABLE_IOT")"

  MQTT_PORT="$(env_get MQTT_PORT "$MQTT_PORT")"
  MQTT_USERNAME="$(env_get MQTT_USERNAME "$MQTT_USERNAME")"
  MQTT_PASSWORD="$(env_get MQTT_PASSWORD "$MQTT_PASSWORD")"

  AUTOCHECK_INTERVAL_SEC="$(env_get AUTOCHECK_INTERVAL_SEC "$AUTOCHECK_INTERVAL_SEC")"
  AUTOCHECK_AUTOSTART="$(env_get AUTOCHECK_AUTOSTART "$AUTOCHECK_AUTOSTART")"
}

expected_modules() {
  local modules=(gateway-mqtt rag-core cognitive-core audio-interface)
  if is_true "$ENABLE_UI"; then
    modules+=(dashboard)
  fi
  if is_true "$ENABLE_VISION"; then
    modules+=(vision-cortex)
  fi
  if is_true "$ENABLE_IOT"; then
    modules+=(iot-gateway)
  fi
  printf '%s\n' "${modules[@]}"
}

module_container_name() {
  local module="$1"
  if [[ "$module" == "dashboard" ]]; then
    echo "maximun-dashboard"
  else
    echo "$module"
  fi
}

service_running() {
  local container_name="$1"
  podman ps --format '{{.Names}}' | grep -qx "$container_name"
}

start_module() {
  local module="$1"
  echo "[INFO] Levantando modulo: $module"
  "${ROOT_DIR}/ops/module_control.sh" up "$module" >/dev/null
}

check_broker_auth() {
  if ! service_running "$BROKER_CONTAINER"; then
    echo "[WARN] Broker no disponible para validar auth MQTT"
    return 1
  fi

  local cmd=(podman exec "$BROKER_CONTAINER" mosquitto_pub -h localhost -p "$MQTT_PORT" -t health/ping -m "autocheck")
  if [[ -n "$MQTT_USERNAME" ]]; then
    cmd+=(-u "$MQTT_USERNAME")
  fi
  if [[ -n "$MQTT_PASSWORD" ]]; then
    cmd+=(-P "$MQTT_PASSWORD")
  fi

  if "${cmd[@]}" >/dev/null 2>&1; then
    echo "[OK]   Validacion de credenciales MQTT correcta"
    return 0
  fi

  echo "[WARN] Validacion de credenciales MQTT fallida"
  return 1
}

run_cycle() {
  local missing_before=0
  local missing_after=0

  echo "== AUTOCHECK $(date -Iseconds) =="
  if ! command -v podman >/dev/null 2>&1; then
    echo "[FATAL] podman no encontrado en PATH"
    return 2
  fi
  load_config

  while IFS= read -r module; do
    [[ -n "$module" ]] || continue
    container_name="$(module_container_name "$module")"
    if service_running "$container_name"; then
      echo "[OK]   modulo activo: $module"
      continue
    fi

    missing_before=$((missing_before + 1))
    echo "[WARN] modulo caido: $module"
    if is_true "$AUTOCHECK_AUTOSTART"; then
      start_module "$module" || echo "[WARN] No se pudo iniciar $module"
    fi
  done < <(expected_modules)

  sleep 2

  while IFS= read -r module; do
    [[ -n "$module" ]] || continue
    container_name="$(module_container_name "$module")"
    if ! service_running "$container_name"; then
      missing_after=$((missing_after + 1))
    fi
  done < <(expected_modules)

  check_broker_auth || true

  echo "[INFO] missing_before=${missing_before} missing_after=${missing_after}"
  if (( missing_after == 0 )); then
    echo "[OK]   Estado general: saludable"
    return 0
  fi

  echo "[WARN] Estado general: degradado"
  return 1
}

main() {
  if [[ $# -ne 1 ]]; then
    usage
    exit 1
  fi

  case "$1" in
    --once)
      run_cycle
      ;;
    --daemon)
      while true; do
        run_cycle || true
        sleep "${AUTOCHECK_INTERVAL_SEC}"
      done
      ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"

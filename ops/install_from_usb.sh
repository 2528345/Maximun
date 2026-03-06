#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

STATE_FILE_DEFAULT="/var/tmp/maximun_usb_install_state.env"
TARGET_DIR_DEFAULT="/opt/maximun/Maximun_V5.1"
PROFILE_DEFAULT="lenovo330s_stable"

MODE=""
ZIP_PATH=""
TARGET_DIR="$TARGET_DIR_DEFAULT"
PROFILE="$PROFILE_DEFAULT"
STATE_FILE="$STATE_FILE_DEFAULT"
SKIP_BOOTSTRAP=false
SKIP_TESTS=false
KEEP_STATE=false
ZIP_SET=false
TARGET_SET=false
PROFILE_SET=false
MQTT_PASSWORD_OVERRIDE=""
MQTT_PASSWORD_SET=false
STATE_ZIP_PATH=""
STATE_TARGET_DIR=""
STATE_PROFILE=""

usage() {
  cat <<USAGE
Instalador USB para openSUSE MicroOS (2 etapas).

Modo 1 (prepare): instala dependencias base con transactional-update y guarda estado.
  ./ops/install_from_usb.sh --prepare --zip /run/media/\$USER/USB/Maximun_V5.1.zip

Modo 2 (resume): despues del reboot extrae el ZIP y despliega el stack.
  ./ops/install_from_usb.sh --resume

Opciones:
  --zip <path>           Ruta del ZIP del proyecto (si no se pasa, intenta autodetectar)
  --target <dir>         Directorio de instalacion final (default: /opt/maximun/Maximun_V5.1)
  --profile <name>       Perfil runtime (default: lenovo330s_stable)
  --state-file <path>    Archivo de estado entre etapas (default: /var/tmp/maximun_usb_install_state.env)
  --skip-bootstrap       Omite microos_bootstrap.sh en --prepare
  --skip-tests           Omite self_test.sh al final de --resume
  --mqtt-password <val>  Clave MQTT para escribir en .env tras aplicar perfil
  --keep-state           No borra el archivo de estado al terminar --resume
  -h, --help             Muestra esta ayuda
USAGE
}

log() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*"
}

fatal() {
  printf '[FATAL] %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fatal "Falta comando requerido: $1"
  fi
}

resolve_abs() {
  local raw="$1"
  if command -v realpath >/dev/null 2>&1; then
    if realpath --help 2>&1 | grep -q -- '--canonicalize-missing'; then
      realpath --canonicalize-missing "$raw"
    else
      realpath "$raw"
    fi
  else
    case "$raw" in
      /*) echo "$raw" ;;
      *) echo "$(pwd)/$raw" ;;
    esac
  fi
}

detect_usb_zip() {
  local roots=()
  local root
  local candidate

  [[ -d "/run/media/$USER" ]] && roots+=("/run/media/$USER")
  [[ -d "/media/$USER" ]] && roots+=("/media/$USER")
  [[ -d "/mnt" ]] && roots+=("/mnt")

  for root in "${roots[@]}"; do
    candidate="$(find "$root" -maxdepth 4 -type f \( -iname 'Maximun*.zip' -o -iname '*v5*.zip' -o -iname '*.zip' \) | head -n1 || true)"
    if [[ -n "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

write_state() {
  local zip_abs="$1"
  local target_abs="$2"
  local profile_name="$3"

  mkdir -p "$(dirname "$STATE_FILE")"
  {
    printf 'ZIP_PATH=%q\n' "$zip_abs"
    printf 'TARGET_DIR=%q\n' "$target_abs"
    printf 'PROFILE=%q\n' "$profile_name"
    printf 'SAVED_AT=%q\n' "$(date -Iseconds)"
  } >"$STATE_FILE"
  chmod 600 "$STATE_FILE"
}

load_state() {
  if [[ ! -f "$STATE_FILE" ]]; then
    fatal "No existe archivo de estado: $STATE_FILE. Ejecuta primero --prepare."
  fi
  local cli_zip="$ZIP_PATH"
  local cli_target="$TARGET_DIR"
  local cli_profile="$PROFILE"
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  STATE_ZIP_PATH="${ZIP_PATH:-}"
  STATE_TARGET_DIR="${TARGET_DIR:-}"
  STATE_PROFILE="${PROFILE:-}"
  ZIP_PATH="$cli_zip"
  TARGET_DIR="$cli_target"
  PROFILE="$cli_profile"
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  grep "^${key}=" "$env_file" | tail -n1 | cut -d= -f2- || true
}

set_env_value() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  local tmp
  tmp="$(mktemp)"
  grep -v "^${key}=" "$env_file" >"$tmp" || true
  printf "%s=%s\n" "$key" "$value" >>"$tmp"
  mv "$tmp" "$env_file"
}

is_default_mqtt_password() {
  local value="$1"
  [[ -z "$value" || "$value" == "maximun_local_change_me" || "$value" == "CAMBIAR_ESTA_CLAVE_SEGURA" ]]
}

generate_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 24 | tr -d '\n'
    return 0
  fi
  tr -dc 'A-Za-z0-9@#%+=:_-' </dev/urandom | head -c 24
}

ensure_secure_mqtt_password() {
  local env_file="$1"
  local mqtt_username
  local current_password
  local final_password
  local creds_file
  local role_password_keys

  mqtt_username="$(read_env_value "$env_file" "MQTT_USERNAME")"
  current_password="$(read_env_value "$env_file" "MQTT_PASSWORD")"
  final_password="$current_password"

  if [[ "$MQTT_PASSWORD_SET" == true ]]; then
    final_password="$MQTT_PASSWORD_OVERRIDE"
    if [[ "${#final_password}" -lt 16 ]]; then
      fatal "--mqtt-password debe tener al menos 16 caracteres."
    fi
  elif is_default_mqtt_password "$final_password"; then
    final_password="$(generate_password)"
    warn "MQTT_PASSWORD por defecto detectada. Se genero una clave segura automaticamente."
  fi

  set_env_value "$env_file" "MQTT_PASSWORD" "$final_password"
  set_env_value "$env_file" "MQTT_ENFORCE_STRONG_PASSWORD" "true"
  set_env_value "$env_file" "MQTT_ENABLE_ACL" "true"
  set_env_value "$env_file" "MQTT_ENABLE_ADMIN_FALLBACK" "false"

  role_password_keys="MQTT_CORE_PASSWORD MQTT_AUDIO_PASSWORD MQTT_VISION_PASSWORD MQTT_RAG_PASSWORD MQTT_IOT_PASSWORD MQTT_DASHBOARD_PASSWORD MQTT_OPS_PASSWORD"
  for key in $role_password_keys; do
    set_env_value "$env_file" "$key" "$final_password"
  done

  creds_file="$TARGET_DIR/.mqtt_credentials.local"
  {
    printf "MQTT_USERNAME=%s\n" "${mqtt_username:-maximun}"
    printf "MQTT_PASSWORD=%s\n" "$final_password"
    printf "MQTT_OPS_USERNAME=%s\n" "$(read_env_value "$env_file" "MQTT_OPS_USERNAME")"
    printf "MQTT_OPS_PASSWORD=%s\n" "$final_password"
  } >"$creds_file"
  chmod 600 "$creds_file"
  log "Credenciales MQTT guardadas en $creds_file (permisos 600)."
}

run_prepare() {
  if [[ -z "$ZIP_PATH" ]]; then
    if ZIP_PATH="$(detect_usb_zip)"; then
      log "ZIP detectado automaticamente: $ZIP_PATH"
    else
      fatal "No se encontro ZIP automaticamente. Usa --zip <ruta>."
    fi
  fi

  [[ -f "$ZIP_PATH" ]] || fatal "ZIP no encontrado: $ZIP_PATH"
  local zip_abs
  zip_abs="$(resolve_abs "$ZIP_PATH")"
  local target_abs
  target_abs="$(resolve_abs "$TARGET_DIR")"

  if [[ "$SKIP_BOOTSTRAP" == false ]]; then
    [[ -x "$ROOT_DIR/ops/microos_bootstrap.sh" ]] || fatal "No se encontro ops/microos_bootstrap.sh en $ROOT_DIR"
    log "Ejecutando bootstrap de host (transactional-update)..."
    "$ROOT_DIR/ops/microos_bootstrap.sh" --apply
  else
    warn "Bootstrap omitido por --skip-bootstrap"
  fi

  write_state "$zip_abs" "$target_abs" "$PROFILE"
  log "Estado guardado en $STATE_FILE"
  log "Etapa 1 completada."
  echo
  echo "Siguiente paso:"
  echo "  1) Reinicia el host (importante en MicroOS tras transactional-update)."
  echo "  2) Ejecuta:"
  echo "     ./ops/install_from_usb.sh --resume --state-file \"$STATE_FILE\""
}

find_project_root() {
  local unpack_dir="$1"
  local compose_path

  if [[ -f "$unpack_dir/docker-compose.yml" ]]; then
    echo "$unpack_dir"
    return 0
  fi

  compose_path="$(find "$unpack_dir" -maxdepth 5 -type f -name 'docker-compose.yml' | head -n1 || true)"
  if [[ -z "$compose_path" ]]; then
    return 1
  fi
  dirname "$compose_path"
}

run_resume() {
  if [[ "$ZIP_SET" == false || "$TARGET_SET" == false || "$PROFILE_SET" == false ]]; then
    load_state
    if [[ "$ZIP_SET" == false ]]; then
      ZIP_PATH="$STATE_ZIP_PATH"
    fi
    if [[ "$TARGET_SET" == false ]]; then
      TARGET_DIR="${STATE_TARGET_DIR:-$TARGET_DIR_DEFAULT}"
    fi
    if [[ "$PROFILE_SET" == false ]]; then
      PROFILE="${STATE_PROFILE:-$PROFILE_DEFAULT}"
    fi
  fi

  [[ -n "${ZIP_PATH:-}" ]] || fatal "ZIP_PATH vacio."
  [[ -f "$ZIP_PATH" ]] || fatal "No existe ZIP: $ZIP_PATH"

  need_cmd unzip
  need_cmd podman

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT

  local unpack_dir="$tmp_dir/unpack"
  mkdir -p "$unpack_dir"

  log "Extrayendo ZIP..."
  unzip -q "$ZIP_PATH" -d "$unpack_dir"

  local source_root
  if ! source_root="$(find_project_root "$unpack_dir")"; then
    fatal "No se encontro docker-compose.yml dentro del ZIP."
  fi

  mkdir -p "$TARGET_DIR"
  log "Copiando proyecto a $TARGET_DIR"
  cp -a "$source_root"/. "$TARGET_DIR"/

  if [[ ! -f "$TARGET_DIR/.env" && -f "$TARGET_DIR/.env.example" ]]; then
    cp "$TARGET_DIR/.env.example" "$TARGET_DIR/.env"
    log "Se creo .env desde .env.example"
  fi

  log "Aplicando permisos de host (audio/video)..."
  if ! (cd "$TARGET_DIR" && ./ops/host_permissions.sh); then
    warn "No se pudieron aplicar permisos automaticamente. Revisa ops/host_permissions.sh."
  fi

  log "Aplicando perfil runtime: $PROFILE"
  (cd "$TARGET_DIR" && ./ops/apply_runtime_profile.sh "$PROFILE")

  log "Asegurando clave MQTT fuerte en .env..."
  ensure_secure_mqtt_password "$TARGET_DIR/.env"

  log "Configurando tiers SSD/RAM..."
  (cd "$TARGET_DIR" && ./ops/storage_tier_setup.sh)

  log "Chequeando consistencia..."
  set +e
  (cd "$TARGET_DIR" && ./ops/check_system_consistency.sh)
  consistency_status=$?
  set -e
  if [[ "$consistency_status" -eq 2 ]]; then
    fatal "Inconsistencias criticas detectadas."
  fi
  if [[ "$consistency_status" -eq 1 ]]; then
    warn "Consistencia con advertencias. Continuando."
  fi

  log "Ejecutando preflight..."
  if ! (cd "$TARGET_DIR" && ./ops/preflight_host_check.sh); then
    fatal "Preflight fallo. Corrige advertencias y repite --resume."
  fi

  log "Desplegando stack..."
  (cd "$TARGET_DIR" && ./ops/deploy_microos.sh --profile "$PROFILE")

  if [[ "$SKIP_TESTS" == false ]]; then
    log "Ejecutando self_test..."
    (cd "$TARGET_DIR" && ./ops/self_test.sh)
  else
    warn "Self-test omitido por --skip-tests"
  fi

  if [[ "$KEEP_STATE" == false && -f "$STATE_FILE" ]]; then
    rm -f "$STATE_FILE"
    log "Estado temporal eliminado: $STATE_FILE"
  fi

  echo
  echo "[OK] Instalacion USB completada."
  echo "Proyecto desplegado en: $TARGET_DIR"
  echo "Siguientes pruebas recomendadas:"
  echo "  cd \"$TARGET_DIR\""
  echo "  ./ops/mqtt_smoke_test.sh"
  echo "  ./ops/test_by_module.sh"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare)
      MODE="prepare"
      shift
      ;;
    --resume)
      MODE="resume"
      shift
      ;;
    --zip)
      ZIP_PATH="${2:-}"
      ZIP_SET=true
      shift 2
      ;;
    --target)
      TARGET_DIR="${2:-}"
      TARGET_SET=true
      shift 2
      ;;
    --profile)
      PROFILE="${2:-}"
      PROFILE_SET=true
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-}"
      shift 2
      ;;
    --skip-bootstrap)
      SKIP_BOOTSTRAP=true
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --mqtt-password)
      MQTT_PASSWORD_OVERRIDE="${2:-}"
      MQTT_PASSWORD_SET=true
      shift 2
      ;;
    --keep-state)
      KEEP_STATE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fatal "Opcion desconocida: $1"
      ;;
  esac
done

if [[ -z "$MODE" ]]; then
  if [[ -f "$STATE_FILE" ]]; then
    MODE="resume"
    log "Archivo de estado detectado. Continuando en modo --resume."
  else
    usage
    exit 1
  fi
fi

if [[ "$MODE" == "prepare" ]]; then
  run_prepare
else
  run_resume
fi

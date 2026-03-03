#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Uso:
  ./ops/module_control.sh <up|down|logs|status|restart> <module|all>

Modulos validos:
  gateway-mqtt
  cognitive-core
  audio-interface
  vision-cortex
  rag-core
  dashboard
  all
USAGE
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

action="$1"
module="$2"

case "$module" in
  gateway-mqtt|cognitive-core|audio-interface|vision-cortex|rag-core)
    svc="$module"
    ;;
  dashboard)
    svc="maximun-dashboard"
    ;;
  all)
    svc="all"
    ;;
  *)
    echo "[FATAL] modulo invalido: $module"
    usage
    exit 2
    ;;
esac

compose_up_module() {
  local m="$1"
  case "$m" in
    gateway-mqtt)
      podman compose up -d gateway-mqtt
      ;;
    cognitive-core)
      podman compose up -d gateway-mqtt rag-core cognitive-core
      ;;
    audio-interface)
      podman compose up -d gateway-mqtt rag-core cognitive-core audio-interface
      ;;
    vision-cortex)
      podman compose up -d gateway-mqtt rag-core cognitive-core vision-cortex
      ;;
    rag-core)
      podman compose up -d gateway-mqtt rag-core
      ;;
    dashboard)
      podman compose up -d gateway-mqtt dashboard
      ;;
  esac
}

case "$action" in
  up)
    if [[ "$module" == "all" ]]; then
      podman compose up -d
    else
      compose_up_module "$module"
    fi
    ;;
  down)
    if [[ "$module" == "all" ]]; then
      podman compose down
    else
      if [[ "$svc" == "maximun-dashboard" ]]; then
        podman stop maximun-dashboard || true
      else
        podman stop "$svc" || true
      fi
    fi
    ;;
  restart)
    if [[ "$module" == "all" ]]; then
      podman compose restart
    else
      if [[ "$svc" == "maximun-dashboard" ]]; then
        podman restart maximun-dashboard
      else
        podman restart "$svc"
      fi
    fi
    ;;
  logs)
    if [[ "$module" == "all" ]]; then
      podman compose logs -f --tail=100
    else
      if [[ "$svc" == "maximun-dashboard" ]]; then
        podman logs -f --tail=100 maximun-dashboard
      else
        podman logs -f --tail=100 "$svc"
      fi
    fi
    ;;
  status)
    if [[ "$module" == "all" ]]; then
      podman compose ps
    else
      if [[ "$svc" == "maximun-dashboard" ]]; then
        podman ps --filter name=maximun-dashboard
      else
        podman ps --filter name="$svc"
      fi
    fi
    ;;
  *)
    echo "[FATAL] accion invalida: $action"
    usage
    exit 3
    ;;
esac

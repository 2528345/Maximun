# MAXIMUN V5.1 (Repositorio Modular Ordenado)

Stack de asistente personal **offline-first** para openSUSE MicroOS en Lenovo 330s (i5, 8GB RAM), usando arquitectura HMR con intercambio dinámico de modelos según recursos.

## Arquitectura actual

- `gateway-mqtt`: bus central MQTT + WebSocket
- `services/cognitive-core`: orquestación Qwen/DeepSeek/GLM con hot-swap vía llama.cpp
- `services/audio-interface`: STT con Faster-Whisper y TTS con Piper
- `services/vision-cortex`: visión refleja (YOLOv8n) + deliberada (Moondream2)
- `services/rag-core`: memoria contextual local (ChromaDB)
- `services/iot-gateway`: puente IoT para Bluetooth, Zigbee y protocolos industriales (Modbus/OPC UA/CAN)
- `dashboard`: panel de monitoreo y control en tiempo real

## Árbol modular

```bash
.
|-- services/
|   |-- cognitive-core/
|   |-- audio-interface/
|   |-- vision-cortex/
|   |-- rag-core/
|   `-- iot-gateway/
|-- gateway-mqtt/
|-- dashboard/
|-- ops/
|-- docs/
|-- config/
`-- docker-compose.yml
```

## Límites de recursos (compose)

- `cognitive-core`: 6.5GB / 3.5 CPU
- `vision-cortex`: 800MB / 0.5 CPU
- `audio-interface`: 600MB / 0.5 CPU
- `rag-core`: 700MB / 0.5 CPU
- `iot-gateway`: 220MB / 0.35 CPU (opcional)
- `gateway-mqtt`: 100MB / 0.1 CPU

## Seguridad MQTT (autenticación + TLS)

- El broker arranca autenticado por defecto (`MQTT_ALLOW_ANONYMOUS=false`).
- Credenciales en `.env`:
  - `MQTT_USERNAME`
  - `MQTT_PASSWORD`
- TLS opcional en puerto `8883`:
  - `MQTT_TLS_ENABLE=true`
  - `MQTT_TLS_CA_FILE`, `MQTT_TLS_CERT_FILE`, `MQTT_TLS_KEY_FILE`
  - CA para clientes internos: `MQTT_TLS_CA_CERT=/certs/mqtt/ca.crt`

Generar certificados locales:

```bash
./ops/generate_mqtt_tls_certs.sh
```

## Estructura de datos en host

```bash
/opt/maximun/data/
  models_cache/
  projects/
  rag_store/
```

Modelos esperados en `models_cache`:

- `qwen-2.5-1.5b-instruct.gguf`
- `deepseek-r1-distill-qwen-1.5b.gguf`
- `glm-4-9b-chat-iq4_xs.gguf`
- `yolov8n.onnx`
- `moondream2-text-model-f16.gguf`
- `moondream2-mmproj-f16.gguf`
- `es_ES-sharvard-medium.onnx`

## Inicio rápido

```bash
cp .env.example .env
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/storage_tier_setup.sh
./ops/check_system_consistency.sh || true
./ops/preflight_host_check.sh
./ops/deploy_microos.sh
```

Dashboard (si `ENABLE_UI=true`): `http://localhost:5173`

## Perfiles runtime (8GB)

```bash
./ops/apply_runtime_profile.sh --list
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/apply_runtime_profile.sh lenovo330s_engineering
./ops/apply_runtime_profile.sh lenovo330s_mvp_production
```

`deploy_microos.sh` levanta por defecto el núcleo mínimo para mantenerse en 8GB:

- `gateway-mqtt`
- `rag-core`
- `cognitive-core`
- `audio-interface`

Módulos opcionales por `.env`:

- `ENABLE_UI=true` para `dashboard`
- `ENABLE_VISION=true` para `vision-cortex`
- `ENABLE_IOT=true` para `iot-gateway`

## Pruebas recomendadas

```bash
./ops/generate_model_checksums.sh
./ops/self_test.sh
./ops/mqtt_smoke_test.sh
./ops/test_by_module.sh
```

## Documentación clave

- [Runbook openSUSE MicroOS](/root/codex/docs/OPENSUSE_MICROOS_RUNBOOK.md)
- [Hoja de ruta completa instalación/despliegue](/root/codex/docs/INSTALL_DEPLOY_ROADMAP_V5.1.md)
- [Flujo por módulo](/root/codex/docs/FLOW_BY_MODULE.md)
- [Checklist MVP producción](/root/codex/docs/MVP_PRODUCTION_CHECKLIST_ES.md)

## Estado del proyecto

- Repo modular ordenado y ejecutable.
- Integración de IoT gateway ya implementada.
- CI de GitHub Actions funcionando sobre `master`.

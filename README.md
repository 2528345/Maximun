# MAXIMUN V5.1 (Ordered Modular Repo)

Offline-first personal assistant stack for openSUSE MicroOS on Lenovo 330s (i5, 8GB RAM), using HMR with resource-aware model swapping.

## Current architecture (clean)

- `gateway-mqtt`: central MQTT + WebSocket bus
- `services/cognitive-core`: Qwen/DeepSeek/GLM orchestration with hot-swap via llama.cpp
- `services/audio-interface`: Faster-Whisper STT + Piper TTS
- `services/vision-cortex`: YOLOv8n ONNX reflex + Moondream2 deliberate analysis
- `services/rag-core`: ChromaDB offline memory (RAG over local documents)
- `services/iot-gateway`: bridge IoT for Bluetooth, Zigbee and industrial protocols (Modbus/OPC UA/CAN)
- `services/rag-core/app/self_protection.py`: detector multicapa con cifrado (fallback) y contador homomórfico opcional (Paillier)
- `dashboard`: real-time monitor/control UI with RLHF controls (`APROBAR/CORREGIR`, feedback, auditor override)

## What was removed from legacy mix

Legacy `services/*` and `v2_proposal/*` logic from the older repo snapshot was not kept as runtime code because most modules were template/simulated. This repo keeps only the V5.1 runnable core and reusable metadata (`LICENSE`, CI workflow).
See [docs/LEGACY_DISCARDED.md](/root/codex/docs/LEGACY_DISCARDED.md).

## Modular tree

```bash
.
|-- services/
|   |-- cognitive-core/
|   |-- audio-interface/
|   |-- vision-cortex/
|   |-- iot-gateway/
|   `-- rag-core/
|-- gateway-mqtt/
|-- dashboard/
|-- ops/
|-- docs/
|-- config/
`-- docker-compose.yml
```

## Resource limits

- `cognitive-core`: 6.5GB / 3.5 CPU
- `vision-cortex`: 800MB / 0.5 CPU
- `audio-interface`: 600MB / 0.5 CPU
- `rag-core`: 700MB / 0.5 CPU
- `iot-gateway`: 220MB / 0.35 CPU (optional)
- `gateway-mqtt`: 100MB / 0.1 CPU

## MQTT security (auth + TLS)

- Broker now starts with authenticated MQTT by default (`MQTT_ALLOW_ANONYMOUS=false`).
- Credentials are controlled from `.env`:
  - `MQTT_USERNAME`
  - `MQTT_PASSWORD`
- Optional TLS listener (`8883`) can be enabled with:
  - `MQTT_TLS_ENABLE=true`
  - `MQTT_TLS_CA_FILE`, `MQTT_TLS_CERT_FILE`, `MQTT_TLS_KEY_FILE`
  - client CA inside services: `MQTT_TLS_CA_CERT=/certs/mqtt/ca.crt`

Generate self-signed certs for local testing:

```bash
./ops/generate_mqtt_tls_certs.sh
```

## Host data layout

```bash
/opt/maximun/data/
  models_cache/
    qwen-2.5-1.5b-instruct.gguf
    deepseek-r1-distill-qwen-1.5b.gguf
    glm-4-9b-chat-iq4_xs.gguf
    yolov8n.onnx
    moondream2-text-model-f16.gguf
    moondream2-mmproj-f16.gguf
    es_ES-sharvard-medium.onnx
  projects/
  rag_store/
```

## Start

```bash
cp .env.example .env
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/storage_tier_setup.sh
./ops/check_system_consistency.sh || true
./ops/preflight_host_check.sh
podman compose build
podman compose up -d
podman compose ps
```

Dashboard: `http://localhost:5173`

For openSUSE MicroOS host preparation, follow:

- [docs/OPENSUSE_MICROOS_RUNBOOK.md](/root/codex/docs/OPENSUSE_MICROOS_RUNBOOK.md)
- [docs/INSTALL_DEPLOY_ROADMAP_V5.1.md](/root/codex/docs/INSTALL_DEPLOY_ROADMAP_V5.1.md)

## Module tests

```bash
./ops/generate_model_checksums.sh
./ops/self_test.sh
./ops/mqtt_smoke_test.sh
./ops/test_by_module.sh
```

## Runtime profiles (8GB)

```bash
# List available profiles
./ops/apply_runtime_profile.sh --list

# Stable mode (recommended daily)
./ops/apply_runtime_profile.sh lenovo330s_stable

# Engineering mode (heavier GLM/DeepSeek cycle)
./ops/apply_runtime_profile.sh lenovo330s_engineering

# MVP production baseline (secure defaults + TLS intended)
./ops/apply_runtime_profile.sh lenovo330s_mvp_production
```

Run consistency check after switching profile:

```bash
./ops/check_system_consistency.sh
```

`deploy_microos.sh` starts core services by default (`gateway-mqtt`, `rag-core`, `cognitive-core`, `audio-interface`) to stay inside 8GB.
Optional modules are controlled by `.env`:

- `ENABLE_UI=true` to include `dashboard`
- `ENABLE_VISION=true` to include `vision-cortex`
- `ENABLE_IOT=true` to include `iot-gateway`

## SSD + RAM tiering for RAG

- SSD persistent data: `${MAXIMUN_DATA_ROOT}/rag_store`
- RAM cache (tmpfs): `${RAG_RAM_CACHE_PATH}` (default `/dev/shm/maximun_rag_cache`)
- Target free SSD budget check: `${RAG_SSD_BUDGET_GB}` GB
- Recommended SSD free space for project/RAG workload: `>= 60GB` (prefer `>= 80GB`)
- Query cache TTL in RAM: `${RAG_QUERY_CACHE_TTL_SEC}` seconds

Prepare tiers:

```bash
./ops/storage_tier_setup.sh
```

Supported RAG ingestion formats: `pdf`, `md`, `markdown`, `txt`, `rst`.

MQTT topics for ingestion/feedback:

- `cognition/rag/ingest_path`
- `cognition/rag/feedback`
- `cognition/rag/stats/get`

## Repo coverage checklist

- Configuration: `docker-compose.yml`, `.env.example`, `gateway-mqtt/mosquitto.conf`
- Code: `services/*/app/main.py`
- Tests:
  - contract tests in `tests/`
  - smoke/module tests in `ops/`
- Deployment scripts:
  - `ops/microos_bootstrap.sh`
  - `ops/deploy_microos.sh`
  - `ops/apply_runtime_profile.sh`
  - `ops/storage_tier_setup.sh`
  - `ops/check_system_consistency.sh`
  - `ops/module_control.sh`

## Flow and troubleshooting

- Flow by module: [docs/FLOW_BY_MODULE.md](/root/codex/docs/FLOW_BY_MODULE.md)
- Host permissions: [ops/host_permissions.sh](/root/codex/ops/host_permissions.sh)

## Notes

- The stack is designed to stay offline after models are present locally.
- If dependencies/models are missing, services publish `system/error` instead of crashing the full bus.
- Integrity checks: `cognitive-core` validates signature files and optional model checksum manifest (`model_checksums.sha256`).
- Failsafe mode supports `notify` (default) and optional `execute` strategy via `FAILSAFE_EXEC_MODE`.
- `rag-core` usa detector avanzado si `self_protection.py` carga correctamente; si no, cae al detector basico.
- `rag-core` incluye `cryptography` y `phe` para cifrado y contador homomorfico ligero (Paillier).

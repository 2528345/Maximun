# MAXIMUN V5.1 - Flow By Module

Runtime flow map by module.

## Recommended startup order (8GB)

```bash
./ops/apply_runtime_profile.sh lenovo330s_stable
./ops/check_system_consistency.sh || true
./ops/preflight_host_check.sh
podman compose up -d
```

## Modules (6 runtime + dashboard)

1. `gateway-mqtt`
2. `cognitive-core`
3. `audio-interface`
4. `vision-cortex`
5. `rag-core`
6. `iot-gateway`
7. `dashboard` (UI)

## 1) Audio input

- `audio-interface` captures mic (`arecord`) and runs Faster-Whisper.
- Publishes transcription to `perception/audio/transcription`.

## 2) Cognitive orchestration

- `cognitive-core` reads `perception/audio/transcription`.
- If simple: Qwen (L1) responds directly.
- If complex: starts engineering duel.

### Engineering duel sequence

1. Publish `system/resource/pause` (`pause=true`).
2. Query `rag-core` via `cognition/rag/query` for extra context.
3. Load GLM-4 and generate draft -> `project/engineering/draft`.
4. Swap to DeepSeek for audit -> `cognition/thought/trace`.
5. Swap back to GLM-4 and apply mandatory changes -> `action/engineering/final`.
6. Return to Qwen and publish `system/resource/pause` (`pause=false`).

## 3) RAG memory

- `rag-core` subscribes to:
  - `cognition/rag/query`
  - `cognition/rag/upsert`
  - `cognition/rag/delete`
  - `cognition/rag/ingest_path`
  - `cognition/rag/feedback`
- Query response topic: `cognition/rag/result`
- Index status topic: `cognition/rag/index/status`
- Stats topic: `cognition/rag/stats/get` -> `cognition/rag/status`

## 4) Vision

- `vision-cortex` runs YOLO reflex loop and publishes low-priority detections.
- On `perception/vision/request_analysis`, runs Moondream2 only if RAM interlock allows.
- Sends result via `perception/vision/analysis_result`.

## 5) Audio output

- `audio-interface` consumes `action/speech/request`.
- Uses Piper + `aplay` and publishes `action/speech/played`.

## 6) Observability topics

- Ready:
  - `system/brain/ready`
  - `system/audio/ready`
  - `system/vision/ready`
  - `system/rag/ready`
- Resource:
  - `system/resource/status`
  - `system/resource/throttle`
  - `system/resource/failsafe`
- Errors:
  - `system/error`

## 7) IoT gateway

- `iot-gateway` consume comandos de:
  - `iot/gateway/command`
  - `iot/bluetooth/scan/request`
  - `iot/zigbee/scan/request`
  - `iot/industrial/request`
- Publica resultados en:
  - `perception/iot/bluetooth/devices`
  - `perception/iot/zigbee/devices`
  - `perception/iot/industrial/data`
  - `iot/gateway/response`
- Health y estado:
  - `system/iot/ready`
  - `system/iot/status`
- Si recibe `system/resource/pause`, reduce actividad de escaneo.

## 8) Debug commands

```bash
# Watch resource/error traffic
mosquitto_sub -h localhost -p 1883 -t 'system/#' -v

# Watch engineering duel
mosquitto_sub -h localhost -p 1883 -t 'project/engineering/draft' -v
mosquitto_sub -h localhost -p 1883 -t 'cognition/thought/trace' -v
mosquitto_sub -h localhost -p 1883 -t 'action/engineering/final' -v

# Trigger complex prompt
mosquitto_pub -h localhost -p 1883 -t perception/audio/transcription -m '{"text":"genera un script de backup con logs"}'

# Add RAG memory chunk
mosquitto_pub -h localhost -p 1883 -t cognition/rag/upsert -m '{"id":"doc-001","text":"El usuario prefiere openSUSE MicroOS y flujo offline","metadata":{"source":"manual"}}'

# Query RAG
mosquitto_pub -h localhost -p 1883 -t cognition/rag/query -m '{"request_id":"q1","query":"que sistema operativo prefiere el usuario","top_k":3}'

# Ingest all PDF/MD/TXT from docs path
mosquitto_pub -h localhost -p 1883 -t cognition/rag/ingest_path -m '{"path":"/rag_store/docs","recursive":true}'

# Feedback for RL ranking
mosquitto_pub -h localhost -p 1883 -t cognition/rag/feedback -m '{"interaction_id":"anonymous_1710000000_q1","feedback_type":"explicit","feedback_value":1.0}'

# IoT BLE scan
mosquitto_pub -h localhost -p 1883 -t iot/bluetooth/scan/request -m '{"request_id":"ble-1"}'

# IoT industrial Modbus
mosquitto_pub -h localhost -p 1883 -t iot/industrial/request -m '{"request_id":"mb-1","protocol":"modbus","register":100}'
```

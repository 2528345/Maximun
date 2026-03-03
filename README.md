# MAXIMUN V5.1 (Ordered Modular Repo)

Offline-first personal assistant stack for openSUSE MicroOS on Lenovo 330s (i5, 8GB RAM), using HMR with resource-aware model swapping.

## Current architecture (clean)

- `gateway-mqtt`: central MQTT + WebSocket bus
- `services/cognitive-core`: Qwen/DeepSeek/GLM orchestration with hot-swap via llama.cpp
- `services/audio-interface`: Faster-Whisper STT + Piper TTS
- `services/vision-cortex`: YOLOv8n ONNX reflex + Moondream2 deliberate analysis
- `services/rag-core`: ChromaDB offline memory (RAG over local documents)
- `dashboard`: real-time monitor/control UI

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
- `gateway-mqtt`: 100MB / 0.1 CPU

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
./ops/preflight_host_check.sh
podman compose build
podman compose up -d
podman compose ps
```

Dashboard: `http://localhost:5173`

## Module tests

```bash
./ops/self_test.sh
./ops/mqtt_smoke_test.sh
./ops/test_by_module.sh
```

## Flow and troubleshooting

- Flow by module: [docs/FLOW_BY_MODULE.md](/root/codex/docs/FLOW_BY_MODULE.md)
- Host permissions: [ops/host_permissions.sh](/root/codex/ops/host_permissions.sh)

## Notes

- The stack is designed to stay offline after models are present locally.
- If dependencies/models are missing, services publish `system/error` instead of crashing the full bus.

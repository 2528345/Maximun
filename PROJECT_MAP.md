# PROJECT MAP - MAXIMUN V5.1

## Goal

Keep one coherent offline architecture for openSUSE MicroOS with strict resource control on 8GB RAM.

## Runtime modules

- `gateway-mqtt`: internal event bus
- `services/cognitive-core`: L1/L2/L3 orchestration + hot-swap
- `services/audio-interface`: STT/TTS local
- `services/vision-cortex`: reflex + deliberate vision
- `services/rag-core`: local semantic memory with ChromaDB
- `dashboard`: monitoring and manual controls

## Why this map is clean

- Legacy mixed branch code with simulated logic is not used as runtime.
- Only one active service layout exists: `services/*`.
- Model hierarchy follows V5.1 restoration point as source of truth.

## Data paths

- Models: `/opt/maximun/data/models_cache`
- Projects: `/opt/maximun/data/projects`
- RAG store: `/opt/maximun/data/rag_store`

## Main operational files

- Compose: [docker-compose.yml](/root/codex/docker-compose.yml)
- Flow: [docs/FLOW_BY_MODULE.md](/root/codex/docs/FLOW_BY_MODULE.md)
- Host preflight: [ops/preflight_host_check.sh](/root/codex/ops/preflight_host_check.sh)
- Module test: [ops/test_by_module.sh](/root/codex/ops/test_by_module.sh)

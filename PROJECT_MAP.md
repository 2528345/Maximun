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
- openSUSE runbook: [docs/OPENSUSE_MICROOS_RUNBOOK.md](/root/codex/docs/OPENSUSE_MICROOS_RUNBOOK.md)
- Host preflight: [ops/preflight_host_check.sh](/root/codex/ops/preflight_host_check.sh)
- Profile apply: [ops/apply_runtime_profile.sh](/root/codex/ops/apply_runtime_profile.sh)
- Storage tier setup: [ops/storage_tier_setup.sh](/root/codex/ops/storage_tier_setup.sh)
- Consistency check: [ops/check_system_consistency.sh](/root/codex/ops/check_system_consistency.sh)
- Module test: [ops/test_by_module.sh](/root/codex/ops/test_by_module.sh)
- Deploy script: [ops/deploy_microos.sh](/root/codex/ops/deploy_microos.sh)

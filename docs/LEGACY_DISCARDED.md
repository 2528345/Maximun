# Legacy Discard Report

This repository keeps V5.1 runtime modules as source of truth.

## Discarded from old mixed snapshot

- Legacy runtime trees under `services/*` from older design (`audio`, `vision`, `reasoning`, `hardware`, `learning`, `filter`, `rag`) because they were mostly simulated/template logic.
- `v2_proposal/*` runtime code (also mostly simulated or incomplete).
- Outdated docs that referenced old ports/topologies not matching V5.1.

## Reused from old snapshot

- `LICENSE`
- CI workflow base in `.github/workflows/python-app.yml` (adapted to current layout)

## Active runtime now

- `gateway-mqtt`
- `services/cognitive-core`
- `services/audio-interface`
- `services/vision-cortex`
- `services/rag-core`
- `dashboard`

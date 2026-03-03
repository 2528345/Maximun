.PHONY: up down build logs ps preflight self-test smoke test-modules

build:
	podman compose build

up:
	podman compose up -d

down:
	podman compose down

logs:
	podman compose logs -f --tail=100

ps:
	podman compose ps

preflight:
	./ops/preflight_host_check.sh

self-test:
	./ops/self_test.sh

smoke:
	./ops/mqtt_smoke_test.sh

test-modules:
	./ops/test_by_module.sh

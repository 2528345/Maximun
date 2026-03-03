.PHONY: up down build logs ps preflight self-test smoke test-modules bootstrap-microos deploy-microos module-status apply-profile list-profiles check-consistency storage-tier

PROFILE ?= lenovo330s_stable

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

bootstrap-microos:
	./ops/microos_bootstrap.sh

deploy-microos:
	./ops/deploy_microos.sh

module-status:
	./ops/module_control.sh status all

apply-profile:
	./ops/apply_runtime_profile.sh $(PROFILE)

list-profiles:
	./ops/apply_runtime_profile.sh --list

check-consistency:
	./ops/check_system_consistency.sh

storage-tier:
	./ops/storage_tier_setup.sh

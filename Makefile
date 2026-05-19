.PHONY: up down restart ps logs load-smoke load-steady load-spike fault-reset clean

DOCKER_ROOT_DIR ?= $(shell docker info --format '{{.DockerRootDir}}' 2>/dev/null)
ifeq ($(DOCKER_ROOT_DIR),)
DOCKER_ROOT_DIR := /var/lib/docker
endif
export DOCKER_ROOT_DIR

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose down && docker compose up -d --build

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=200

load-smoke:
	docker compose run --rm -e BASE_URL=http://load-balancer k6 run /scripts/k6-smoke.js

load-steady:
	docker compose run --rm -e BASE_URL=http://load-balancer k6 run /scripts/k6-steady.js

load-spike:
	docker compose run --rm -e BASE_URL=http://load-balancer k6 run /scripts/k6-spike.js

fault-reset:
	curl -sS http://localhost:8080/api/fault/reset | jq .

clean:
	docker compose down -v --remove-orphans

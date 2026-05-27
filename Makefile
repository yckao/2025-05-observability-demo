.PHONY: up down restart ps logs load-smoke load-steady load-spike load-consistent traffic-start traffic-stop traffic-status traffic-logs fault-reset clean check

DOCKER_ROOT_DIR ?= $(shell docker info --format '{{.DockerRootDir}}' 2>/dev/null)
ifeq ($(DOCKER_ROOT_DIR),)
DOCKER_ROOT_DIR := /var/lib/docker
endif
export DOCKER_ROOT_DIR

TRAFFIC_DURATION ?= 30m
HOME_PER_MIN ?= 20
SHOP_PER_MIN ?= 30
PRODUCTS_PER_MIN ?= 20
CHECKOUT_PER_MIN ?= 10
ORDERS_PER_MIN ?= 10
HEALTH_PER_MIN ?= 6
PREALLOCATED_VUS ?=
MAX_VUS ?= 50
export TRAFFIC_DURATION HOME_PER_MIN SHOP_PER_MIN PRODUCTS_PER_MIN CHECKOUT_PER_MIN ORDERS_PER_MIN HEALTH_PER_MIN PREALLOCATED_VUS MAX_VUS

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

load-consistent:
	docker compose run --rm -e BASE_URL=http://load-balancer -e TRAFFIC_DURATION -e HOME_PER_MIN -e SHOP_PER_MIN -e PRODUCTS_PER_MIN -e CHECKOUT_PER_MIN -e ORDERS_PER_MIN -e HEALTH_PER_MIN -e PREALLOCATED_VUS -e MAX_VUS k6 run /scripts/k6-consistent.js

traffic-start:
	docker compose --profile traffic up -d traffic-generator

traffic-stop:
	-docker compose --profile traffic stop traffic-generator
	-docker compose --profile traffic rm -f traffic-generator

traffic-status:
	docker compose --profile traffic ps traffic-generator

traffic-logs:
	docker compose --profile traffic logs -f --tail=100 traffic-generator

fault-reset:
	./scripts/fault-reset.sh | jq .

clean:
	docker compose down -v --remove-orphans

check:
	python3 -m unittest discover -s tests -v

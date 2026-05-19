#!/usr/bin/env sh
set -eu
ms="${1:-1500}"
curl -sS "http://localhost:8080/api/fault/latency?ms=${ms}"

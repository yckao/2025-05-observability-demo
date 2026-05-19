#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
ms="${1:-1500}"
target="${2:-backend-1}"
scope="${3:-/api/}"
curl -sS "${admin_url}/api/fault/latency?ms=${ms}&target=${target}&scope=${scope}"

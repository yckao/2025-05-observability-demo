#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
rate="${1:-40}"
target="${2:-backend-1}"
scope="${3:-/api/}"
status="${4:-503}"
curl -sS "${admin_url}/api/fault/errors?rate=${rate}&target=${target}&scope=${scope}&status=${status}"

#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
seconds="${1:-10}"
target="${2:-backend-1}"
curl -sS "${admin_url}/api/fault/cpu?seconds=${seconds}&target=${target}"

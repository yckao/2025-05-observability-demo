#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
mb="${1:-128}"
target="${2:-backend-1}"
curl -sS "${admin_url}/api/fault/memory?mb=${mb}&target=${target}"

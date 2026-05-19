#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
count="${1:-20}"
seconds="${2:-30}"
target="${3:-backend-1}"
curl -sS "${admin_url}/api/fault/db-connections?count=${count}&seconds=${seconds}&target=${target}"

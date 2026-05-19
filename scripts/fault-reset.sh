#!/usr/bin/env sh
set -eu
admin_url="${ADMIN_URL:-http://localhost:8088}"
target="${1:-all}"
if [ "${target}" = "all" ]; then
  for replica in backend-1 backend-2 backend-3; do
    curl -sS "${admin_url}/api/fault/reset?target=${replica}"
  done
else
  curl -sS "${admin_url}/api/fault/reset?target=${target}"
fi

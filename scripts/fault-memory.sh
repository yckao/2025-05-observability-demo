#!/usr/bin/env sh
set -eu
mb="${1:-128}"
curl -sS "http://localhost:8080/api/fault/memory?mb=${mb}"

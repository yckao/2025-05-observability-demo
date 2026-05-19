#!/usr/bin/env sh
set -eu
seconds="${1:-10}"
curl -sS "http://localhost:8080/api/fault/cpu?seconds=${seconds}"

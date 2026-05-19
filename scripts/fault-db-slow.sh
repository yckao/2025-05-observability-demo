#!/usr/bin/env sh
set -eu
seconds="${1:-3}"
curl -sS "http://localhost:8080/api/fault/db-slow?seconds=${seconds}"

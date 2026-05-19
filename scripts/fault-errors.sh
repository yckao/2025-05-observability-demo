#!/usr/bin/env sh
set -eu
rate="${1:-40}"
curl -sS "http://localhost:8080/api/fault/errors?rate=${rate}"

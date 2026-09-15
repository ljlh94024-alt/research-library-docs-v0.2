#!/usr/bin/env bash
set -euo pipefail
printf 'sample=04\n'
printf 'kind=readonly-shell\n'
printf 'utc=' && date -u +'%Y-%m-%dT%H:%M:%SZ'
command -v systemctl >/dev/null 2>&1 && systemctl is-active tiangong-worker.service 2>/dev/null || true
command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null || true
printf 'result=PASS\n'

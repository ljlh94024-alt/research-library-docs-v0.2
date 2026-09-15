#!/usr/bin/env bash
set -u
BASE='/srv/tiangong/experiments/github-code-relay-20260915-r01/public-fetch'
REMOTE='https://github.com/ljlh94024-alt/research-library-docs-v0.2.git'
BRANCH='experiment/github-relay-public-20260915-r01'
SAMPLE_ROOT='experiments/github-relay-public-20260915-r01/samples'
rm -rf "$BASE"
mkdir -p "$BASE"
CSV="$BASE/results.csv"
printf 'iteration,fetch_rc,validate_rc,elapsed_ms,file_count\n' >"$CSV"
for I in $(seq 1 10); do
  R="$BASE/repo-$I"
  mkdir -p "$R"
  cd "$R"
  git init -q
  git remote add origin "$REMOTE"
  T0="$(date +%s%3N)"
  FETCH_RC=0
  GIT_TERMINAL_PROMPT=0 git fetch --no-tags --depth=1 origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" >"$BASE/fetch-$I.log" 2>&1 || FETCH_RC=$?
  VALIDATE_RC=0
  FILE_COUNT=0
  if [ "$FETCH_RC" -eq 0 ]; then
    git checkout -q --detach "refs/remotes/origin/$BRANCH" || VALIDATE_RC=1
    if [ "$VALIDATE_RC" -eq 0 ]; then
      FILE_COUNT="$(find "$SAMPLE_ROOT" -type f | wc -l | tr -d ' ')"
      [ "$FILE_COUNT" -ge 10 ] || VALIDATE_RC=2
      grep -q '天工网页端 → GitHub → 香港服务器' "$SAMPLE_ROOT/02-unicode.md" || VALIDATE_RC=3
      python3 -m py_compile "$SAMPLE_ROOT/03-python.py" || VALIDATE_RC=4
      python3 - "$SAMPLE_ROOT/05-config.json" <<'PY' || VALIDATE_RC=5
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    data = json.load(f)
assert data['sample'] == 5 and data['production_changes'] is False
PY
      grep -q 'END-OF-LONG-SAMPLE' "$SAMPLE_ROOT/07-long-markdown.md" || VALIDATE_RC=6
      [ "$(wc -c < "$SAMPLE_ROOT/07-long-markdown.md")" -gt 2500 ] || VALIDATE_RC=7
      grep -q 'NESTED-SAMPLE-10-PASS' "$SAMPLE_ROOT/nested/10-readme.md" || VALIDATE_RC=8
      bash "$SAMPLE_ROOT/04-readonly.sh" >"$BASE/probe-$I.log" 2>&1 || VALIDATE_RC=9
      grep -q 'result=PASS' "$BASE/probe-$I.log" || VALIDATE_RC=10
    fi
  fi
  T1="$(date +%s%3N)"
  ELAPSED=$((T1-T0))
  printf '%s,%s,%s,%s,%s\n' "$I" "$FETCH_RC" "$VALIDATE_RC" "$ELAPSED" "$FILE_COUNT" >>"$CSV"
done
python3 - "$CSV" <<'PY'
import csv, statistics, sys
with open(sys.argv[1], newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
fetch_success = sum(int(r['fetch_rc']) == 0 for r in rows)
validate_success = sum(int(r['validate_rc']) == 0 for r in rows)
elapsed = [int(r['elapsed_ms']) for r in rows]
print(f'iterations={len(rows)}')
print(f'fetch_success={fetch_success}')
print(f'validate_success={validate_success}')
print(f'median_elapsed_ms={int(statistics.median(elapsed))}')
print(f'min_elapsed_ms={min(elapsed)}')
print(f'max_elapsed_ms={max(elapsed)}')
print('classification=' + ('PASS' if fetch_success == len(rows) and validate_success == len(rows) else 'TRANSPORT_OR_CONTENT_FAILURE'))
PY
printf '%s\n' '--- per iteration ---'
cat "$CSV"
printf '%s\n' '--- attempted anonymous reverse push ---'
cd "$BASE/repo-10"
git config user.name 'Tiangong Relay Public Experiment'
git config user.email 'tiangong-relay@localhost'
printf '\nserver-local-result=true\n' >>"$SAMPLE_ROOT/nested/10-readme.md"
git add "$SAMPLE_ROOT/nested/10-readme.md"
git commit -q -m 'experiment: anonymous reverse push probe'
PUSH_RC=0
GIT_TERMINAL_PROMPT=0 git push origin "HEAD:refs/heads/experiment/github-relay-public-20260915-r01-server-result" >"$BASE/push.log" 2>&1 || PUSH_RC=$?
printf 'anonymous_reverse_push_rc=%s\n' "$PUSH_RC"
if [ "$PUSH_RC" -ne 0 ]; then
  sed -E 's#https://[^/@]+@github.com/#https://github.com/#g' "$BASE/push.log" | tail -n 10
fi

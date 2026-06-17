#!/usr/bin/env bash
#
# deploy.sh  --  one-command, deterministic deploy of BOTH front-ends.
#
# The repo serves two front-ends from its root on GitHub Pages:
#   index.html + assets/  -> the React/three.js 3D dashboard (built from app/)
#   classic.html          -> the static single-file dashboard (DATA inlined)
# They share ONE source of truth: data/dashboard_data.json. Building them by hand
# let them drift (the app shipped stale data more than once). This script rebuilds
# the data, regenerates BOTH front-ends from it, sanity-checks, then commits/pushes
# so the live site always matches the committed data.
#
#   ./deploy.sh                 # rebuild data (offline) + app, verify, commit, push
#   ./deploy.sh --no-push       # do everything except git push (dry run for review)
#   ./deploy.sh --online         # also re-pull the OER dataset (needs internet)
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-$ROOT/.venv/bin/python}"; [ -x "$PY" ] || PY="python3"
PUSH=1; OFFLINE_FLAG="--offline"
for a in "$@"; do
  case "$a" in
    --no-push) PUSH=0 ;;
    --online)  OFFLINE_FLAG="" ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done

echo "==> 1/5  Rebuild data + models + both DATA blocks"
PYTHONPATH="$ROOT/src" "$PY" src/rebuild.py $OFFLINE_FLAG

echo "==> 2/5  Build the 3D app"
( cd app && npm run build )

echo "==> 3/5  Publish app build to repo root (index.html + assets/)"
rm -rf assets
cp app/dist/index.html index.html
cp -R app/dist/assets assets

echo "==> 4/5  Verify (golden + data integrity + dual-front-end consistency)"
"$PY" tests/test_data_integrity.py
"$PY" tests/test_golden.py
test -f index.html && test -d assets && test -f classic.html || { echo "front-end artifacts missing" >&2; exit 1; }
grep -q 'const DATA' classic.html || { echo "classic.html DATA block missing" >&2; exit 1; }
# the two front-ends must not drift: classic.html's inlined DATA must deep-equal the
# JSON source of truth, classic must carry the honesty framing, and NEITHER may make
# an external network request (the offline claim).
"$PY" - <<'PYV'
import json, re, sys
data = json.load(open("data/dashboard_data.json"))
html = open("classic.html", encoding="utf-8").read()
m = re.search(r"^const DATA = (.*);\s*$", html, re.M)
assert m, "classic.html DATA line not found"
assert json.loads(m.group(1)) == data, "classic.html DATA has drifted from dashboard_data.json"
for s in ["Marginal", "leak-free", "representative", "out-of-sample", "literature primary"]:
    assert s in html, f"classic.html missing honesty string: {s!r}"
for bad in ["fonts.googleapis.com", "fonts.gstatic.com"]:
    assert bad not in html, f"classic.html still references {bad} (breaks offline)"
print("dual-front-end consistency + offline checks passed")
PYV
grep -rq "googleapis\|gstatic" assets/ && { echo "built bundle references external fonts (breaks offline)" >&2; exit 1; } || true

echo "==> 5/5  Commit"
git add -A
if git diff --cached --quiet; then
  echo "nothing changed; nothing to deploy."; exit 0
fi
git commit -m "deploy: rebuild data + both front-ends from dashboard_data.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

if [ "$PUSH" = "1" ]; then
  git push origin HEAD
  echo "pushed. GitHub Pages will redeploy in ~1 min."
else
  echo "committed but NOT pushed (--no-push). Review, then: git push origin HEAD"
fi

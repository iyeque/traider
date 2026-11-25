#!/usr/bin/env bash
# Trigger the tuning workflow on the cloudflare-agents branch.
# Usage: GITHUB_TOKEN=... ./scripts/dispatch_tune.sh [trials] [test_fraction]
set -euo pipefail
: "${GITHUB_TOKEN:?set GITHUB_TOKEN to a token with actions:write}"
TRIALS="${1:-50}"
FRACTION="${2:-0.25}"
PAYLOAD=$(printf '{"ref":"cloudflare-agents","inputs":{"trials":"%s","test_fraction":"%s","promote":"true"}}' "$TRIALS" "$FRACTION")
curl -fsS -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d "$PAYLOAD" \
  https://api.github.com/repos/iyeque/traider/actions/workflows/tune.yml/dispatches
echo "Dispatched tuning workflow (trials=$TRIALS, test_fraction=$FRACTION)"

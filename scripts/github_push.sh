#!/usr/bin/env bash
# github_push.sh — Push changed files to GitHub via Contents API.
#
# Usage:
#   GITHUB_TOKEN=<token> bash scripts/github_push.sh
#
# Why needed: `git push` is blocked in Replit dev environment.
# This script uses GitHub REST Contents API (GET sha → PUT base64 content).
#
# Files pushed per session:
#   Session #6: agent/status_event.py, agent/system_prompt.py,
#                bot/file_buffer.py, bot/handlers/reply_handler.py,
#                bot/handlers/sessions.py, bot/handlers/start.py,
#                bot/keyboards/reply_keyboard.py, bot/ui/status_blocks.py,
#                config/constants.py, docs/CONTEXT.md

set -euo pipefail

TOKEN="${GITHUB_TOKEN:?Need GITHUB_TOKEN env var}"
OWNER="artemjsdx"
REPO="RefAgent"
LOCAL_BASE="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT_MSG="${1:-"chore: auto-push via github_push.sh"}"

# Files relative to repo/local root
FILES=(
  "agent/status_event.py"
  "agent/system_prompt.py"
  "bot/file_buffer.py"
  "bot/handlers/reply_handler.py"
  "bot/handlers/sessions.py"
  "bot/handlers/start.py"
  "bot/keyboards/reply_keyboard.py"
  "bot/ui/status_blocks.py"
  "config/constants.py"
  "docs/CONTEXT.md"
)

push_file() {
  local REL="$1"
  local LOCAL="$LOCAL_BASE/$REL"
  local URL="https://api.github.com/repos/$OWNER/$REPO/contents/$REL"

  if [ ! -f "$LOCAL" ]; then
    echo "⚠️  SKIP (not found): $REL"
    return
  fi

  # Get current SHA (empty string if file is new)
  local SHA
  SHA=$(curl -sf -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "$URL" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null || echo "")

  local CONTENT
  CONTENT=$(base64 -w 0 "$LOCAL")

  local BODY
  if [ -n "$SHA" ]; then
    BODY=$(python3 -c "
import json, sys
print(json.dumps({
  'message': sys.argv[1],
  'content': sys.argv[2],
  'sha':     sys.argv[3],
}))" "$COMMIT_MSG" "$CONTENT" "$SHA")
  else
    BODY=$(python3 -c "
import json, sys
print(json.dumps({
  'message': sys.argv[1],
  'content': sys.argv[2],
}))" "chore: add $REL" "$CONTENT")
  fi

  local HTTP
  HTTP=$(curl -s -o /tmp/gh_push_resp.json -w "%{http_code}" \
    -X PUT \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    "$URL")

  if [ "$HTTP" = "200" ] || [ "$HTTP" = "201" ]; then
    echo "✅ $REL (HTTP $HTTP)"
  else
    local ERR
    ERR=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message','?'))" < /tmp/gh_push_resp.json 2>/dev/null || echo "unknown")
    echo "❌ $REL (HTTP $HTTP): $ERR"
  fi
}

echo "Pushing ${#FILES[@]} files to $OWNER/$REPO ..."
for f in "${FILES[@]}"; do
  push_file "$f"
done
echo "Done."

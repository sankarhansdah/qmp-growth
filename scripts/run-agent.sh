#!/usr/bin/env bash
# Run one agent headless.  Usage: scripts/run-agent.sh <agent-name> [extra instructions]
#   e.g. scripts/run-agent.sh 06-search-console-monitor
set -euo pipefail
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f "$HOME/.config/qmp/env" ] && . "$HOME/.config/qmp/env"
cd "$(dirname "$0")/.."
# one agent at a time; skip if another run is still going
exec 9>/tmp/qmp-agents.lock
flock -n 9 || { echo "another agent run in progress, skipping"; exit 0; }
AGENT="$1"; shift || true
EXTRA="${*:-}"
DATE=$(date +%Y%m%d)
mkdir -p reports logs

git switch main >/dev/null 2>&1 && git pull --ff-only >/dev/null 2>&1 || true
BRANCH="agent/${AGENT}/${DATE}"
git switch -c "$BRANCH" 2>/dev/null || git switch "$BRANCH"

PROMPT="You are running unattended. Today is $(date +%Y-%m-%d).
Follow CLAUDE.md and the instructions in agents/${AGENT}.md exactly.
You are on branch ${BRANCH}. When finished: commit, push this branch, open one PR, write your report.
${EXTRA}"

claude -p "$PROMPT" --permission-mode acceptEdits 2>&1 | tee "logs/${DATE}-${AGENT}.log"
git switch main >/dev/null 2>&1 || true

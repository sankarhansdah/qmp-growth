#!/usr/bin/env bash
# Run one agent headless.  Usage: scripts/run-agent.sh <agent-name> [extra instructions]
set -euo pipefail
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f "$HOME/.config/qmp/env" ] && . "$HOME/.config/qmp/env"
cd "$(dirname "$0")/.."
exec 9>/tmp/qmp-agents.lock
flock -n 9 || { echo "another agent run in progress, skipping"; exit 0; }

AGENT="$1"; shift || true
EXTRA="${*:-}"
RUN_ID="$(date +%Y%m%d-%H%M%S)-${AGENT}"
mkdir -p state logs
trap 'rm -f state/current.json; git switch -q -C main origin/main >/dev/null 2>&1 || true' EXIT

git stash push -u -m "abandoned before $RUN_ID" >/dev/null 2>&1 || true
git fetch -q origin main
BRANCH="agent/${AGENT}/$(date +%Y%m%d-%H%M)"
git switch -q -C "$BRANCH" origin/main   # always start from the latest main

PROMPT="You are running unattended. Today is $(date +%Y-%m-%d).
Follow CLAUDE.md and the instructions in agents/${AGENT}.md exactly.
You are on branch ${BRANCH}. When finished: commit, push this branch, open one PR, write your report.
${EXTRA}"

bash scripts/agent-exec.sh "$RUN_ID" "$AGENT" "$AGENT" "$PROMPT"

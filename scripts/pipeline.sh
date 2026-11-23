#!/usr/bin/env bash
# Full article pipeline: brief -> write -> fact-check -> edit/link -> PR.
# Each stage is a separate Claude session, so the fact-checker never sees the writer's reasoning.
#   scripts/pipeline.sh            # picks highest-score backlog keyword
#   scripts/pipeline.sh 7          # specific keyword row id
#   scripts/pipeline.sh refresh    # top row of queue/refresh.csv
set -euo pipefail
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f "$HOME/.config/qmp/env" ] && . "$HOME/.config/qmp/env"
cd "$(dirname "$0")/.."
# one agent at a time; skip if another run is still going
exec 9>/tmp/qmp-agents.lock
flock -n 9 || { echo "another agent run in progress, skipping"; exit 0; }
ARG="${1:-next}"
DATE=$(date +%Y%m%d)
mkdir -p logs reports

git switch main >/dev/null 2>&1 && git pull --ff-only >/dev/null 2>&1 || true
BRANCH="agent/article/${DATE}-${ARG}"
git switch -c "$BRANCH" 2>/dev/null || git switch "$BRANCH"

stage () {
  local AGENT="$1"; local NOTE="$2"
  echo "=== $AGENT ==="
  claude -p "You are running unattended. Today is $(date +%Y-%m-%d).
Follow CLAUDE.md and agents/${AGENT}.md. Target: ${ARG} (keyword id, 'next' = highest score
backlog row, 'refresh' = top row of queue/refresh.csv and update the existing article).
You are on branch ${BRANCH}. ${NOTE}" --permission-mode acceptEdits \
  2>&1 | tee -a "logs/${DATE}-pipeline-${ARG}.log"
}

stage 02-research-brief  "Commit the brief. Do NOT open a PR. Print the slug and market on the last line."
stage 03-writer          "Use the brief committed on this branch. Commit. Do NOT open a PR."
stage 04-fact-check      "Check the article committed on this branch. Commit fixes and the report. Do NOT open a PR."
stage 05-editor-linker   "Finish, build, push the branch and open the PR."

git switch main >/dev/null 2>&1 || true

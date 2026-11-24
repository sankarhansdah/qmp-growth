#!/usr/bin/env bash
# Article pipeline: brief -> write -> fact-check -> edit/link -> PR.
# Each stage is a separate Claude session, so the fact-checker never sees the writer's reasoning.
#   scripts/pipeline.sh            # highest-score backlog keyword
#   scripts/pipeline.sh 7          # keyword row id 7
#   scripts/pipeline.sh refresh    # top row of queue/refresh.csv
set -euo pipefail
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
[ -f "$HOME/.config/qmp/env" ] && . "$HOME/.config/qmp/env"
cd "$(dirname "$0")/.."
exec 9>/tmp/qmp-agents.lock
flock -n 9 || { echo "another agent run in progress, skipping"; exit 0; }

ARG="${1:-next}"
KIND="pipeline-$([ "$ARG" = refresh ] && echo refresh || echo next)"
RUN_ID="$(date +%Y%m%d-%H%M%S)-pipeline-${ARG}"
mkdir -p state logs
trap 'rm -f state/current.json; git switch -q -C main origin/main >/dev/null 2>&1 || true' EXIT

git stash push -u -m "abandoned before $RUN_ID" >/dev/null 2>&1 || true
git fetch -q origin main
BRANCH="agent/article/$(date +%Y%m%d-%H%M)-${ARG}"
git switch -q -C "$BRANCH" origin/main   # always start from the latest main

stage () {
  local AGENT="$1"; local NOTE="$2"
  bash scripts/agent-exec.sh "$RUN_ID" "$KIND" "$AGENT" "You are running unattended. Today is $(date +%Y-%m-%d).
Follow CLAUDE.md and agents/${AGENT}.md. Target: ${ARG} (keyword id, 'next' = highest score
backlog row, 'refresh' = top row of queue/refresh.csv and update the existing article).
You are on branch ${BRANCH}. ${NOTE}"
}

stage 02-research-brief "Commit the brief. Do NOT open a PR. Print the slug and market on the last line."
stage 03-writer         "Use the brief committed on this branch. Commit. Do NOT open a PR."
stage 04-fact-check     "Check the article committed on this branch. Commit fixes and the report. Do NOT open a PR."
stage 05-editor-linker  "Finish, build, push the branch and open the PR."

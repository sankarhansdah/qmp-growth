#!/usr/bin/env bash
# Installs the weekly schedule into your user crontab (macOS/Linux). Mac must be awake.
# Times are local. Re-running replaces the previous QMP block.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_BIN="$(command -v claude || echo $HOME/.npm-global/bin/claude)"; GUM_BIN="$(command -v gum || echo $HOME/.local/bin/gum)"
PATH_LINE="PATH=$(dirname "$CLAUDE_BIN"):$(dirname "$GUM_BIN"):/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

BLOCK="# >>> QMP growth agents >>>
$PATH_LINE
0 9 * * 1   cd $REPO && scripts/run-agent.sh 06-search-console-monitor
0 10 * * 2  cd $REPO && scripts/pipeline.sh next
0 10 * * 3  cd $REPO && scripts/pipeline.sh refresh
0 10 * * 5  cd $REPO && scripts/pipeline.sh next
0 8 1 * *   cd $REPO && scripts/run-agent.sh 01-keyword-research
0 8 15 * *  cd $REPO && scripts/run-agent.sh 07-aso
# <<< QMP growth agents <<<"

( crontab -l 2>/dev/null | sed '/# >>> QMP growth agents >>>/,/# <<< QMP growth agents <<</d'; echo "$BLOCK" ) | crontab -
echo "Installed:"; crontab -l | sed -n '/QMP growth/,/QMP growth/p'

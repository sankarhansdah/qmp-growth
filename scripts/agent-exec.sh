#!/usr/bin/env bash
# agent-exec.sh RUN_ID KIND STAGE PROMPT
# Runs one Claude session and records state/events for the dashboard.
#   KIND  = what the dashboard groups by (e.g. 06-search-console-monitor, pipeline-next)
#   STAGE = agent prompt file name (e.g. 03-writer)
set -uo pipefail
cd "$(dirname "$0")/.."
RUN_ID="$1"; KIND="$2"; STAGE="$3"; PROMPT="$4"
mkdir -p state "logs/runs/$RUN_ID"
EV="logs/runs/$RUN_ID/$STAGE.jsonl"
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
START=$(date +%s)

python3 -c 'import json,sys;r,k,s,b,t=sys.argv[1:];print(json.dumps({"run_id":r,"kind":k,"stage":s,"branch":b,"started":int(t)}))' \
  "$RUN_ID" "$KIND" "$STAGE" "$BRANCH" "$START" > state/current.json

claude -p "$PROMPT" --permission-mode acceptEdits --output-format stream-json --verbose \
  > "$EV" 2> "logs/runs/$RUN_ID/$STAGE.stderr"
CODE=$?

python3 - "$RUN_ID" "$KIND" "$STAGE" "$BRANCH" "$START" "$(date +%s)" "$CODE" "$EV" >> state/history.jsonl <<'PY'
import json, re, sys
run, kind, stage, branch, start, end, code, ev = sys.argv[1:]
res = {}
try:
    for line in open(ev, errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "result":
            res = e
except FileNotFoundError:
    pass
text = res.get("result") or ""
pr = re.findall(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+", text)
print(json.dumps({
    "run_id": run, "kind": kind, "stage": stage, "branch": branch,
    "started": int(start), "ended": int(end), "exit": int(code),
    "ok": int(code) == 0 and not res.get("is_error", False) and bool(res),
    "cost": res.get("total_cost_usd"), "turns": res.get("num_turns"),
    "pr": pr[-1] if pr else None, "summary": text[:1500],
}))
PY
exit $CODE

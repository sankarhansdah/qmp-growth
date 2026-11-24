#!/usr/bin/env python3
"""Auto-merge agent PRs that are safe to publish without a human click.

Runs from cron every 30 minutes (see scripts/install-schedule.sh).

A PR is merged only when ALL of these hold:
  - it comes from an agent/* branch and is not a draft (fact-check drafts unfixable articles)
  - it is not a Play Store listing PR (agent/07-aso/*): those always wait for Sankar
  - every changed file is inside AUTO_OK and none is inside NEVER
  - no fact-check report in the PR has a FAIL verdict row
  - all check runs have finished and passed, and PRs touching site/ have at least one check
Everything else stays open for review on GitHub or the dashboard.
"""
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO_OK = ("site/", "briefs/", "reports/", "queue/", "data/keywords.csv", "data/link-map.json")
NEVER = ("CLAUDE.md", ".claude/", ".agents/", ".github/", "scripts/", "dashboard/", "fastlane/",
         "data/product-facts.md", "data/experience-notes.md", "data/sources-allowlist.md")
MANUAL_BRANCHES = ("agent/07-aso/",)
PASSING = {"success", "neutral", "skipped"}


def gh(*args, body=None):
    r = subprocess.run(["gh", "api", *args] + (["--input", "-"] if body is not None else []), cwd=REPO,
                       input=json.dumps(body) if body is not None else None, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError((r.stdout or r.stderr).strip()[:300])
    return json.loads(r.stdout) if r.stdout.strip() else {}


def slug():
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url).group(1)


def audit(action, detail):
    os.makedirs(os.path.join(REPO, "state"), exist_ok=True)
    with open(os.path.join(REPO, "state", "audit.jsonl"), "a") as f:
        f.write(json.dumps({"t": int(time.time()), "user": "auto-merge", "action": action, "detail": detail[:300]}) + "\n")


def verdict(s, pr):
    n, ref = pr["number"], pr["head"]["ref"]
    if pr.get("draft"):
        return "draft"
    if not ref.startswith("agent/"):
        return "not an agent branch"
    if ref.startswith(MANUAL_BRANCHES):
        return "Play listing: needs Sankar"
    files = gh(f"repos/{s}/pulls/{n}/files?per_page=100")
    names = [f["filename"] for f in files]
    bad = [x for x in names if x.startswith(NEVER) or not x.startswith(AUTO_OK)]
    if bad:
        return "touches protected files: " + ", ".join(bad[:4])
    for f in files:
        if re.search(r"reports/.*factcheck.*\.md$", f["filename"]) and re.search(r"^\+.*\|\s*FAIL\s*\|", f.get("patch", ""), re.M):
            return "fact-check has FAIL rows"
    try:
        runs = gh(f"repos/{s}/commits/{pr['head']['sha']}/check-runs?per_page=100").get("check_runs", [])
    except RuntimeError as e:
        return f"can't read checks ({e}); give the server's GitHub token 'Checks: Read'"
    if any(r["status"] != "completed" for r in runs):
        return "checks still running"
    failed = [r["name"] for r in runs if (r.get("conclusion") or "") not in PASSING]
    if failed:
        return "checks failed: " + ", ".join(failed)
    if any(x.startswith("site/") for x in names) and not runs:
        return "no checks reported yet"
    full = gh(f"repos/{s}/pulls/{n}")
    if full.get("mergeable") is False:
        return "merge conflict"
    if full.get("mergeable") is None:
        return "GitHub still computing mergeability"
    return None


def main():
    s = slug()
    pulls = sorted(gh(f"repos/{s}/pulls?state=open&per_page=50"), key=lambda p: p["number"])
    for pr in pulls:
        n, title = pr["number"], pr["title"]
        try:
            why = verdict(s, pr)
        except RuntimeError as e:
            print(f"#{n} skipped: {e}")
            continue
        if why:
            print(f"#{n} waiting: {why}")
            continue
        try:
            gh("-X", "PUT", f"repos/{s}/pulls/{n}/merge", body={"merge_method": "squash"})
        except RuntimeError as e:
            print(f"#{n} merge failed: {e}")
            continue
        try:
            gh("-X", "DELETE", f"repos/{s}/git/refs/heads/{pr['head']['ref']}")
        except RuntimeError:
            pass
        print(f"#{n} merged: {title}")
        audit("auto-merge", f"#{n} {title}")
        time.sleep(5)  # let GitHub recompute mergeability of the next PR


if __name__ == "__main__":
    print(time.strftime("%Y-%m-%d %H:%M"), file=sys.stdout)
    main()

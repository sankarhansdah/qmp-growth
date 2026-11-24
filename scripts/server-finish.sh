#!/usr/bin/env bash
# Run as user agent:  bash ~/qmp-growth/scripts/server-finish.sh
# Guided logins. Safe to re-run; finished steps are skipped.
set -uo pipefail
export PATH=$HOME/.npm-global/bin:$HOME/.local/bin:$PATH
mkdir -p ~/.config/qmp && chmod 700 ~/.config/qmp
[ -f ~/.config/qmp/env ] && . ~/.config/qmp/env
cd ~/qmp-growth

ask_secret () {   # ask_secret "prompt" -> echoes value; retries until non-empty
  local v=""
  while [ -z "$v" ]; do
    read -rsp "   $1: " v </dev/tty; echo >/dev/tty
    v="$(printf '%s' "$v" | tr -d '[:space:]')"
    [ -z "$v" ] && echo "   (empty — paste again)" >/dev/tty
  done
  printf '%s' "$v"
}
yes_no () { local a; read -rp "   $1 [y/N] " a </dev/tty; [[ "$a" =~ ^[Yy] ]]; }

echo "== 1/5 GitHub =="
until gh auth status >/dev/null 2>&1; do
  echo "   github.com/settings/personal-access-tokens/new"
  echo "   Repository access: All repositories"
  echo "   Permissions -> Repository: Administration, Contents, Pull requests, Workflows = Read and write"
  echo "   Generate, copy the token (starts with github_pat_)."
  T=$(ask_secret "Paste GitHub token")
  printf '%s\n' "$T" | gh auth login --with-token || echo "   !! token rejected — make a new one and try again"
done
echo "   GitHub OK as $(gh api user -q .login)"
gh auth setup-git >/dev/null 2>&1
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create qmp-growth --private --source . --remote origin --push && echo "   Repo created and pushed."
else
  git push -u origin main >/dev/null 2>&1 && echo "   Remote already set, pushed."
fi

echo "== 2/5 Claude Code =="
until claude -p "reply with the single word OK" 2>/dev/null | grep -q OK; do
  echo "   On your Mac, open a NEW Terminal tab and run:  claude setup-token"
  echo "   Approve in the browser. Copy the long token it prints (starts with sk-ant-oat)."
  CT=$(ask_secret "Paste Claude token")
  printf 'export CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$CT" > ~/.config/qmp/env && chmod 600 ~/.config/qmp/env
  . ~/.config/qmp/env
done
grep -q qmp/env ~/.bashrc || echo '[ -f ~/.config/qmp/env ] && . ~/.config/qmp/env' >> ~/.bashrc
echo "   Claude OK."

echo "== 3/5 Trust repo for headless runs =="
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude.json")
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("projects", {}).setdefault(os.path.expanduser("~/qmp-growth"), {})["hasTrustDialogAccepted"] = True
json.dump(d, open(p, "w"), indent=2)
print("   Trusted ~/qmp-growth (permissions in .claude/settings.json now apply).")
PY

echo "== 4/5 Search Console (skip until the website is live) =="
if [ -f ~/.config/qmp/sa-searchconsole.json ]; then
  echo "   Already set."
elif yes_no "Set up now?"; then
  echo "   1. console.cloud.google.com -> project quotation-maker-pro-15aeb"
  echo "   2. APIs & Services -> enable 'Google Search Console API'"
  echo "   3. IAM -> Service accounts -> Create 'qmp-seo' -> Keys -> Add key -> JSON (downloads a file)"
  echo "   4. search.google.com/search-console -> Settings -> Users -> add that service account email"
  echo "   Paste the whole JSON file contents, then press Enter and Ctrl-D:"
  cat </dev/tty > ~/.config/qmp/sa-searchconsole.json; chmod 600 ~/.config/qmp/sa-searchconsole.json
  if jq -e .client_email ~/.config/qmp/sa-searchconsole.json >/dev/null 2>&1; then
    gum auth use-service-account ~/.config/qmp/sa-searchconsole.json && gum doctor | tail -5
  else
    echo "   !! That wasn't valid JSON — removed. Re-run later."; : > /dev/null; mv ~/.config/qmp/sa-searchconsole.json ~/.config/qmp/sa-invalid.json
  fi
else
  echo "   Skipped."
fi

echo "== 5/5 Schedule =="
bash scripts/install-schedule.sh

echo
echo "All set. First real run (builds the website, opens a PR on GitHub):"
echo "   bash ~/qmp-growth/scripts/run-agent.sh 00-bootstrap-site"

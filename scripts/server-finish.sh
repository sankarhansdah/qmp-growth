#!/usr/bin/env bash
# Run as user agent:  bash ~/qmp-growth/scripts/server-finish.sh
# Guided logins. Safe to re-run; finished steps are skipped.
set -uo pipefail
export PATH=$HOME/.npm-global/bin:$HOME/.local/bin:$PATH
[ -f ~/.config/qmp/env ] && . ~/.config/qmp/env
cd ~/qmp-growth
pause () { read -rp "   Press Enter when done... " _; }

echo "== 1/4 GitHub =="
if ! gh auth status >/dev/null 2>&1; then
  echo "   Create a token: github.com -> Settings -> Developer settings -> Fine-grained tokens"
  echo "   Repository access: All repositories (needed once to create qmp-growth; you can narrow it after)"
  echo "   Permissions: Administration RW (create repo), Contents RW, Pull requests RW, Workflows RW"
  gh auth login --with-token < <(read -rsp "   Paste token: " t; echo "$t")
  echo
fi
gh auth setup-git >/dev/null 2>&1
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create qmp-growth --private --source . --remote origin --push && echo "   Repo created and pushed."
else
  git push -u origin main >/dev/null 2>&1; echo "   Remote already set."
fi

echo "== 2/4 Claude Code =="
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && ! claude -p "reply OK" 2>/dev/null | grep -q OK; then
  echo "   On your Mac Terminal run:  claude setup-token"
  echo "   Approve in the browser, copy the token it prints."
  read -rsp "   Paste token: " CT; echo
  mkdir -p ~/.config/qmp && chmod 700 ~/.config/qmp
  echo "export CLAUDE_CODE_OAUTH_TOKEN=$CT" > ~/.config/qmp/env && chmod 600 ~/.config/qmp/env
  grep -q qmp/env ~/.bashrc || echo '[ -f ~/.config/qmp/env ] && . ~/.config/qmp/env' >> ~/.bashrc
  export CLAUDE_CODE_OAUTH_TOKEN="$CT"
  claude -p "reply OK" | grep -q OK && echo "   Claude works." || echo "   !! Claude check failed — re-run this script."
else
  echo "   Already working."
fi

echo "== 3/4 Search Console (can skip until your site is live) =="
if [ ! -f ~/.config/qmp/sa-searchconsole.json ]; then
  read -rp "   Set up now? [y/N] " yn
  if [ "${yn:-n}" = y ]; then
    echo "   console.cloud.google.com -> project quotation-maker-pro-15aeb -> IAM -> Service accounts"
    echo "   -> Create 'qmp-seo' -> Keys -> Add key -> JSON. Enable 'Google Search Console API'."
    echo "   Then Search Console -> Settings -> Users -> add the service account email (Full)."
    echo "   Paste the JSON below, then press Ctrl-D on an empty line:"
    mkdir -p ~/.config/qmp && chmod 700 ~/.config/qmp
    cat > ~/.config/qmp/sa-searchconsole.json; chmod 600 ~/.config/qmp/sa-searchconsole.json
    gum auth use-service-account ~/.config/qmp/sa-searchconsole.json && gum doctor || echo "   !! gum auth failed — check gumcli.dev auth guide"
  fi
else
  echo "   Already set."
fi

echo "== 4/4 Schedule =="
bash scripts/install-schedule.sh

echo
echo "Done. First real run (builds the website, opens a PR):"
echo "   bash ~/qmp-growth/scripts/run-agent.sh 00-bootstrap-site"

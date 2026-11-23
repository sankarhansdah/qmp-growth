#!/usr/bin/env bash
# Run as root on the Ubuntu/Debian server:  bash /root/qmp-growth/scripts/server-setup.sh
# Installs everything, creates user "agent", moves the repo to /home/agent/qmp-growth.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
export DEBIAN_FRONTEND=noninteractive

echo "==> Timezone"
timedatectl set-timezone Asia/Kolkata 2>/dev/null || ln -sf /usr/share/zoneinfo/Asia/Kolkata /etc/localtime

echo "==> Base packages"
apt-get update -qq
apt-get install -y -qq curl git cron ca-certificates gnupg jq unzip sudo util-linux locales >/dev/null
locale-gen en_US.UTF-8 en_IN.UTF-8 >/dev/null 2>&1 || true
update-locale LANG=en_US.UTF-8 >/dev/null 2>&1 || true

echo "==> Node 22"
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1)" != "v22" ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi

echo "==> GitHub CLI"
if ! command -v gh >/dev/null; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list
  apt-get update -qq && apt-get install -y -qq gh >/dev/null
fi

echo "==> User 'agent'"
id agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent
if [ "$SRC" != "/home/agent/qmp-growth" ]; then
  if [ -d /home/agent/qmp-growth/.git ]; then
    cp -a "$SRC/scripts/." /home/agent/qmp-growth/scripts/     # repo exists: only refresh scripts
  else
    rm -rf /home/agent/qmp-growth
    cp -a "$SRC" /home/agent/qmp-growth
  fi
  chown -R agent:agent /home/agent/qmp-growth
fi
chmod +x /home/agent/qmp-growth/scripts/*.sh

echo "==> Claude Code CLI + gum (as agent)"
sudo -u agent -H bash <<'AS_AGENT'
set -euo pipefail
mkdir -p ~/.npm-global ~/.local/bin
npm config set prefix ~/.npm-global
grep -q npm-global ~/.bashrc || echo 'export PATH=$HOME/.npm-global/bin:$HOME/.local/bin:$PATH' >> ~/.bashrc
export PATH=$HOME/.npm-global/bin:$HOME/.local/bin:$PATH
npm install -g --silent @anthropic-ai/claude-code
if ! command -v gum >/dev/null; then
  ARCH=$(dpkg --print-architecture)   # amd64 / arm64
  TAG=$(curl -fsSL https://api.github.com/repos/ehmo/gum/releases/latest | jq -r .tag_name)
  VER=${TAG#v}
  TMP=$(mktemp -d)
  curl -fsSL -o "$TMP/gum.tgz" "https://github.com/ehmo/gum/releases/download/${TAG}/gum_${VER}_linux_${ARCH}.tar.gz"
  tar -xzf "$TMP/gum.tgz" -C "$TMP"
  install -m 0755 "$(find "$TMP" -type f -name gum | head -1)" ~/.local/bin/gum
  rm -rf "$TMP"
fi
cd ~/qmp-growth
[ -d .git ] || { git init -q -b main; git add -A; git -c user.name="QMP Agent" -c user.email="agent@localhost" commit -qm "Initial agent repo"; }
git config user.name  "QMP Agent"
git config user.email "agent@localhost"
echo "claude: $(claude --version)"; echo "gum: $(gum --version 2>&1 | head -1)"
AS_AGENT

systemctl enable --now cron >/dev/null

echo
echo "================================================================"
echo " Install done. Next, run:   su - agent -c 'bash ~/qmp-growth/scripts/server-finish.sh'"
echo "================================================================"

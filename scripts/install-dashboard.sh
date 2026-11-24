#!/usr/bin/env bash
# Run as root:  bash /home/agent/qmp-growth/scripts/install-dashboard.sh you@example.com[,other@example.com]
# Installs the dashboard as a service (localhost:8787) and installs cloudflared.
set -euo pipefail
EMAILS="${1:?usage: install-dashboard.sh your@email.com}"
REPO=/home/agent/qmp-growth

cat > /etc/systemd/system/qmp-dashboard.service <<UNIT
[Unit]
Description=QMP agents dashboard
After=network-online.target

[Service]
User=agent
WorkingDirectory=$REPO
Environment=QMP_REPO=$REPO
Environment=QMP_DASH_EMAILS=$EMAILS
Environment=PATH=/home/agent/.npm-global/bin:/home/agent/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 $REPO/dashboard/server.py
Restart=always
RestartSec=3
# Agent runs started from the dashboard must survive a dashboard restart
KillMode=process

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable qmp-dashboard
systemctl restart qmp-dashboard
sleep 2
systemctl is-active qmp-dashboard && curl -s localhost:8787/healthz -o /dev/null -w "local check: HTTP %{http_code} (403 expected without login)\n" || true

if ! command -v cloudflared >/dev/null; then
  mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" > /etc/apt/sources.list.d/cloudflared.list
  apt-get update -qq && apt-get install -y -qq cloudflared >/dev/null
fi
echo "cloudflared: $(cloudflared --version)"
systemctl is-active --quiet cloudflared || echo "Note: cloudflared service isn't running; admin.quotationmaker.pro needs it."

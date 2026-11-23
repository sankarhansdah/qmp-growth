# QMP Growth — SEO + ASO agents

Agents research keywords, write fact-checked articles, maintain internal links, watch Search
Console and tune the Play Store listing. Every change arrives as a GitHub pull request; you
merge or close it. Rules for all agents live in `CLAUDE.md`.

## Agents

| # | Agent | When | Output |
|---|---|---|---|
| 00 | bootstrap-site | once | Astro site in `site/` |
| 01 | keyword-research | 1st of month | `data/keywords.csv` PR |
| 02→05 | article pipeline (brief → write → fact-check → edit/link) | Tue + Fri | 1 article PR |
| 02→05 | refresh pipeline | Wed | improves 1 existing page |
| 06 | search-console-monitor | Mon | report + `queue/refresh.csv` + CTR fixes |
| 07 | aso | 15th (self-limits to every 6 weeks) | store listing PR → auto-upload on merge |

## One-time setup (≈1 hour)

1. **Repo**: create a private GitHub repo `qmp-growth`, push this folder.
   `gh auth login` on your Mac.
2. **Claude Code CLI** on the Mac: `claude` must work in Terminal (you're logged in).
3. **gum**:
   ```bash
   brew tap ehmo/tap https://github.com/ehmo/homebrew-tap
   brew install ehmo/tap/gum        # NOT plain "brew install gum" — different tool
   gum setup --target claude --features skills,mcp --dry-run   # preview, then without --dry-run
   gum login --service searchconsole
   ```
   Follow gumcli.dev → Auth guides for Search Console and Google Ads.
4. **Search Console**: add the domain property for your site, verify via DNS.
5. **Keyword Planner** (optional at start): Google Ads account + developer token, apply for
   Basic access. Until approved, Agent 01 falls back to Trends + SERP data.
6. **Play listing upload**:
   - Play Console → Setup → API access → create service account, grant "Release manager"
     (or store listing edit) for the app.
   - GitHub repo → Settings → Secrets: `PLAY_SERVICE_ACCOUNT_JSON` (whole JSON),
     `PLAY_PACKAGE_NAME`.
   - The app must exist in Play Console (an internal testing release is enough).
7. **Hosting**: connect `site/` to Cloudflare Pages (build `npm run build`, output `dist`,
   root `site`). Merged PRs deploy automatically.
8. **Fill in** `data/product-facts.md` (package id, plans) and `data/experience-notes.md`.
9. **Bootstrap**: `scripts/run-agent.sh 00-bootstrap-site` → review and merge the PR.
10. **Schedule**: `scripts/install-schedule.sh`. Keep the Mac awake at those times
    (System Settings → Energy → prevent sleep, or `caffeinate`), or run them manually.

## Manual runs
```bash
scripts/pipeline.sh            # next best article
scripts/pipeline.sh 6          # article for keyword row 6
scripts/pipeline.sh refresh    # improve top page in queue/refresh.csv
scripts/run-agent.sh 06-search-console-monitor
scripts/run-agent.sh 07-aso
```

## Your weekly job (~15 min)
- Open PRs on GitHub (phone is fine). For article PRs: skim, fill any `<!-- SANKAR -->`
  markers with 1–2 real lines, merge. For ASO PRs: check wording, merge.
- Once a month, paste Play Console store listing conversion % into `queue/aso.md`.

## Guardrails built in
- Agents can't push to `main`, merge PRs, force-push, or call write/destructive Google APIs
  (`.claude/settings.json`).
- Facts only from `data/sources-allowlist.md`; a separate fact-check session verifies every claim.
- Product claims only from `data/product-facts.md`; CTAs stay in waitlist mode until the
  Play URL is filled in.
- Listing text lengths are validated in CI before upload.

## Running 24/7 on Proxmox (instead of the Mac)

1. **Container**: Proxmox → Create CT → Debian 12 template, unprivileged, 2 vCPU, 4 GB RAM,
   20 GB disk, DHCP. No inbound ports needed. Enable "Start at boot".
2. Inside the container as root:
   ```bash
   apt-get update && apt-get install -y curl
   curl -fsSLO <raw URL of scripts/server-setup.sh in your repo>   # or paste the file
   bash server-setup.sh https://github.com/<you>/qmp-growth.git
   su - agent
   ```
3. **Logins (as `agent`)** — all headless-friendly:
   - **Claude Code**: run `claude` once and complete the login link from your phone/Mac browser.
     If the interactive login is awkward over SSH, run `claude setup-token` on your Mac and set
     `CLAUDE_CODE_OAUTH_TOKEN` in `~/.bashrc` on the server. (Scheduled runs use your
     plan's usage limits; 3 pipelines a week is fine on most plans, more may not be.)
   - **GitHub**: `gh auth login` with a fine-grained token scoped only to `qmp-growth`
     (Contents: read/write, Pull requests: read/write). Nothing else.
   - **Search Console**: Google Cloud → create service account → download JSON →
     add the service account email as a **user** in Search Console (Settings → Users) →
     `gum auth use-service-account ~/sa-searchconsole.json`. No browser needed, never expires.
   - **Keyword Planner** (when your Ads developer token is approved): service accounts don't
     work for Google Ads without Workspace. Use host ADC instead:
     `gcloud auth application-default login --no-browser --scopes=https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform`
     then `gum auth probe --strategy adc --scopes https://www.googleapis.com/auth/adwords`.
     Verify against gumcli.dev → Google Ads auth guide; this is the one step most likely to
     need adjustment.
   - Avoid gum's OS keychain on Linux (it fails headless with `AUTH_KEYCHAIN_UNAVAILABLE`) —
     service account / ADC paths above sidestep it.
4. Test: `cd ~/qmp-growth && scripts/run-agent.sh 06-search-console-monitor`
5. Schedule: `scripts/install-schedule.sh` (same crontab, now always on).
6. **Safety**: snapshot the container after setup (Proxmox → Snapshots). Runs are locked so
   two agents never overlap. Logs: `~/qmp-growth/logs/`.
7. Turn off the Mac schedule if you installed it: `crontab -e` on the Mac, delete the QMP block.

#!/usr/bin/env python3
"""QMP agents dashboard — read-only status server.

Binds to 127.0.0.1 only. Meant to sit behind a Cloudflare Tunnel + Cloudflare Access,
which adds the Cf-Access-Authenticated-User-Email header after login.

Env:
  QMP_REPO              repo path (default ~/qmp-growth)
  QMP_DASH_PORT         port (default 8787)
  QMP_DASH_EMAILS       comma-separated emails allowed (empty = any Access-authenticated user)
  QMP_DASH_ALLOW_LOCAL  "1" lets localhost requests without the Access header through (testing)
"""
import base64
import csv
import fcntl
import datetime as dt
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPO = os.path.expanduser(os.environ.get("QMP_REPO", "~/qmp-growth"))
PORT = int(os.environ.get("QMP_DASH_PORT", "8787"))
ALLOWED = {e.strip().lower() for e in os.environ.get("QMP_DASH_EMAILS", "").split(",") if e.strip()}
ALLOW_LOCAL = os.environ.get("QMP_DASH_ALLOW_LOCAL") == "1"
HERE = os.path.dirname(os.path.abspath(__file__))

AGENTS = {
    "pipeline-next": ("Article pipeline", "Research → write → fact-check → edit & link → PR"),
    "pipeline-refresh": ("Refresh pipeline", "Improves an existing page from the refresh queue"),
    "06-search-console-monitor": ("Search Console monitor", "Rankings, CTR, indexing; queues refreshes"),
    "01-keyword-research": ("Keyword research", "Scored keyword backlog per market"),
    "07-aso": ("Play Store listing", "Title and descriptions per locale"),
    "00-bootstrap-site": ("Site bootstrap", "One-time website build"),
    "08-site-design": ("Site design", "21st.dev component pass on the website"),
}
STAGES = [
    ("02-research-brief", "Research"),
    ("03-writer", "Write"),
    ("04-fact-check", "Fact-check"),
    ("05-editor-linker", "Edit & link"),
]
DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
SAFE = re.compile(r"^[\w.\-]+$")
LOCK = "/tmp/qmp-agents.lock"
# How each agent is started from the dashboard: (script, default arg)
RUNNABLE = {
    "pipeline-next": ("pipeline", "next"),
    "pipeline-refresh": ("pipeline", "refresh"),
    "06-search-console-monitor": ("agent", None),
    "01-keyword-research": ("agent", None),
    "07-aso": ("agent", None),
    "08-site-design": ("agent", None),
    "00-bootstrap-site": ("agent", None),
}
# Files the owner may edit from the dashboard (committed straight to main on GitHub)
EDITABLE = [
    "data/product-facts.md", "data/experience-notes.md", ".agents/product-marketing.md",
    "data/seeds.md", "data/keywords.csv", "data/sources-allowlist.md", "data/competitors.md", "CLAUDE.md",
]


class Conflict(Exception):
    pass

_cache = {}
_lock = threading.Lock()


def cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (now, val)
    return val


def sh(args, timeout=10):
    try:
        return subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def rp(*parts):
    return os.path.join(REPO, *parts)


# ---------------- cron ----------------

def _field(f, lo, hi):
    vals = set()
    for part in f.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        vals.update(range(a, b + 1, step))
    return vals


def next_run(spec):
    try:
        mi, ho, dom, mo, dow = spec.split()
        M, H = _field(mi, 0, 59), _field(ho, 0, 23)
        D, MO = _field(dom, 1, 31), _field(mo, 1, 12)
        W = {d % 7 for d in _field(dow, 0, 7)}
    except Exception:
        return None
    t = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    end = t + dt.timedelta(days=62)
    while t < end:
        wd = t.isoweekday() % 7
        if dom == "*" or dow == "*":
            day_ok = (t.day in D) and (wd in W)
        else:
            day_ok = (t.day in D) or (wd in W)
        if not (day_ok and t.month in MO):
            t = (t + dt.timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if t.hour not in H:
            t = (t + dt.timedelta(hours=1)).replace(minute=0)
            continue
        if t.minute in M:
            return int(t.timestamp())
        t += dt.timedelta(minutes=1)
    return None


def human(spec):
    try:
        mi, ho, dom, mo, dow = spec.split()
        tm = f"{int(ho):02d}:{int(mi):02d}"
    except Exception:
        return spec
    if dom != "*":
        return f"Day {dom} of month · {tm}"
    if dow != "*":
        return f"{', '.join(DOW[d % 7] for d in sorted(_field(dow, 0, 7)))} · {tm}"
    return f"Daily · {tm}"


def cron_jobs():
    out = sh(["crontab", "-l"])
    jobs, inblock = {}, False
    for line in out.splitlines():
        if "QMP growth agents >>>" in line:
            inblock = True
            continue
        if "QMP growth agents <<<" in line:
            break
        s = line.strip()
        if not inblock or not s or s.startswith("PATH="):
            continue
        paused = s.startswith("#")
        s = s.lstrip("#").strip()
        parts = s.split(None, 5)
        if len(parts) < 6 or not re.match(r"^[\d*/,-]+$", parts[0]):
            continue
        spec, cmd = " ".join(parts[:5]), parts[5]
        m = re.search(r"run-agent\.sh\s+(\S+)", cmd)
        p = re.search(r"pipeline\.sh\s+(\S+)", cmd)
        key = m.group(1) if m else (f"pipeline-{'refresh' if p.group(1) == 'refresh' else 'next'}" if p else None)
        if not key:
            continue
        j = jobs.setdefault(key, {"key": key, "schedules": [], "next": None, "paused": True})
        j["schedules"].append({"spec": spec, "human": human(spec), "paused": paused})
        if not paused:
            j["paused"] = False
            n = next_run(spec)
            if n and (j["next"] is None or n < j["next"]):
                j["next"] = n
    return jobs


# ---------------- runs ----------------

def rel(path):
    if not isinstance(path, str):
        return path
    return path.replace(REPO + "/", "").replace(os.path.expanduser("~") + "/", "~/")


def summarize(tool, inp):
    inp = inp or {}
    if tool in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        return rel(inp.get("file_path", ""))
    if tool == "Bash":
        return (inp.get("description") or inp.get("command", ""))[:200]
    if tool == "WebSearch":
        return inp.get("query", "")
    if tool == "WebFetch":
        return inp.get("url", "")
    if tool in ("Glob", "Grep"):
        return f"{inp.get('pattern', '')} {rel(inp.get('path', '') or '')}".strip()
    if tool == "TodoWrite":
        todos = inp.get("todos", [])
        active = [t.get("activeForm") or t.get("content") for t in todos if t.get("status") == "in_progress"]
        done = sum(1 for t in todos if t.get("status") == "completed")
        return f"{active[0] if active else 'Plan updated'} ({done}/{len(todos)} done)"
    if tool == "Task":
        return inp.get("description", "")
    s = json.dumps(inp)
    return s[:200]


def events(run_id, stage, limit=60):
    if not (SAFE.match(run_id or "") and SAFE.match(stage or "")):
        return []
    path = rp("logs", "runs", run_id, stage + ".jsonl")
    out = []
    try:
        with open(path, errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return []
    for ln in lines:
        try:
            e = json.loads(ln)
        except Exception:
            continue
        t = e.get("type")
        if t == "assistant":
            for c in e.get("message", {}).get("content", []) or []:
                if c.get("type") == "tool_use":
                    out.append({"kind": "tool", "tool": c.get("name"), "detail": summarize(c.get("name"), c.get("input"))})
                elif c.get("type") == "text" and (c.get("text") or "").strip():
                    out.append({"kind": "text", "detail": c["text"].strip()[:800]})
        elif t == "result":
            out.append({"kind": "result", "ok": not e.get("is_error"), "detail": (e.get("result") or "")[:6000],
                        "cost": e.get("total_cost_usd"), "turns": e.get("num_turns"),
                        "duration_ms": e.get("duration_ms")})
    return out[-limit:] if limit else out


def current():
    p = rp("state", "current.json")
    if not os.path.exists(p):
        return None
    try:
        c = json.load(open(p))
    except Exception:
        return None
    alive = subprocess.run(["pgrep", "-f", "claude -p"], capture_output=True).returncode == 0
    age = time.time() - os.path.getmtime(p)
    if not alive and age > 90:
        return None
    ev_path = rp("logs", "runs", c.get("run_id", ""), c.get("stage", "") + ".jsonl")
    c["last_activity"] = int(os.path.getmtime(ev_path)) if os.path.exists(ev_path) else c.get("started")
    c["events"] = events(c.get("run_id"), c.get("stage"), limit=50)
    c["tool_calls"] = sum(1 for e in events(c.get("run_id"), c.get("stage"), limit=0) if e["kind"] == "tool")
    done = []
    hist = history_raw()
    for h in hist:
        if h["run_id"] == c.get("run_id"):
            done.append(h["stage"])
    c["stages_done"] = done
    c["pipeline"] = c.get("kind", "").startswith("pipeline")
    return c


def history_raw():
    p = rp("state", "history.jsonl")
    rows = []
    try:
        with open(p, errors="replace") as f:
            for ln in f:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return rows


def history(limit=30):
    runs = {}
    for h in history_raw():
        r = runs.setdefault(h["run_id"], {"run_id": h["run_id"], "kind": h.get("kind"), "stages": [],
                                          "started": h.get("started"), "ended": h.get("ended"),
                                          "cost": 0.0, "pr": None, "ok": True})
        r["stages"].append({k: h.get(k) for k in ("stage", "ok", "exit", "started", "ended", "cost", "turns", "summary")})
        r["started"] = min(r["started"] or h["started"], h["started"])
        r["ended"] = max(r["ended"] or h["ended"], h["ended"])
        r["cost"] += h.get("cost") or 0
        r["pr"] = h.get("pr") or r["pr"]
        r["ok"] = r["ok"] and bool(h.get("ok"))
    out = sorted(runs.values(), key=lambda r: r["started"] or 0, reverse=True)
    for r in out:
        if r["kind"] and r["kind"].startswith("pipeline") and len(r["stages"]) < 4 and r["ok"]:
            r["partial"] = True
    return out[:limit]


# ---------------- github ----------------

def prs():
    def load():
        fields = "number,title,url,createdAt,headRefName,isDraft,statusCheckRollup"
        o = sh(["gh", "pr", "list", "--state", "open", "--limit", "30", "--json", fields], 20)
        m = sh(["gh", "pr", "list", "--state", "merged", "--limit", "8", "--json", "number,title,url,mergedAt"], 20)
        try:
            open_ = json.loads(o or "[]")
            for pr in open_:
                checks = pr.pop("statusCheckRollup", None) or []
                states = [(c.get("conclusion") or c.get("state") or c.get("status") or "").upper() for c in checks]
                if any(x in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT") for x in states):
                    pr["checks"] = "fail"
                elif states and all(x in ("SUCCESS", "NEUTRAL", "SKIPPED") for x in states):
                    pr["checks"] = "pass"
                else:
                    pr["checks"] = "pending" if states else "none"
            return {"open": open_, "merged": json.loads(m or "[]"), "ok": bool(o)}
        except Exception:
            return {"open": [], "merged": [], "ok": False}
    return cached("prs", 60, load)


# ---------------- content ----------------

def frontmatter(path):
    try:
        with open(path, errors="replace") as f:
            txt = f.read(4000)
    except Exception:
        return {}
    return fm_text(txt)


def fm_text(txt):
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"\'')
    return fm


def content():
    def load():
        kw = {"by_status": {}, "by_market": {}, "top": []}
        try:
            with open(rp("data", "keywords.csv"), newline="") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                kw["by_status"][r.get("status") or "?"] = kw["by_status"].get(r.get("status") or "?", 0) + 1
                kw["by_market"][r.get("market") or "?"] = kw["by_market"].get(r.get("market") or "?", 0) + 1
            backlog = [r for r in rows if r.get("status") == "backlog"]

            def score(r):
                try:
                    return float(r.get("score") or 0)
                except ValueError:
                    return 0
            backlog.sort(key=score, reverse=True)
            kw["top"] = [{"id": r.get("id"), "market": r.get("market"), "keyword": r.get("primary_keyword"),
                          "score": r.get("score")} for r in backlog[:6]]
            kw["total"] = len(rows)
        except FileNotFoundError:
            kw["total"] = 0
        arts = {"by_market": {}, "total": 0, "drafts": 0, "review_due": []}
        soon = (dt.date.today() + dt.timedelta(days=14)).isoformat()
        for path in glob.glob(rp("site", "src", "content", "articles", "*", "*.md*")):
            market = os.path.basename(os.path.dirname(path))
            fm = frontmatter(path)
            arts["total"] += 1
            arts["by_market"][market] = arts["by_market"].get(market, 0) + 1
            if fm.get("published", "true").lower() == "false":
                arts["drafts"] += 1
            rb = fm.get("reviewBy", "")
            if rb and rb <= soon:
                arts["review_due"].append({"slug": f"{market}/{os.path.splitext(os.path.basename(path))[0]}", "reviewBy": rb})
        refresh = []
        try:
            with open(rp("queue", "refresh.csv"), newline="") as f:
                refresh = list(csv.DictReader(f))
        except FileNotFoundError:
            pass
        return {"keywords": kw, "articles": arts, "refresh": {"count": len(refresh), "top": refresh[:5]}}
    return cached("content", 30, load)


def reports():
    files = sorted(glob.glob(rp("reports", "*.md")), key=os.path.getmtime, reverse=True)[:30]
    return [{"name": os.path.basename(f), "mtime": int(os.path.getmtime(f)), "size": os.path.getsize(f)} for f in files]


def health():
    def load():
        du = shutil.disk_usage("/")
        try:
            up = float(open("/proc/uptime").read().split()[0])
        except Exception:
            up = None
        env = os.path.expanduser("~/.config/qmp/env")
        env_txt = open(env).read() if os.path.exists(env) else ""
        return {
            "disk_used_pct": round(du.used / du.total * 100),
            "disk_free_gb": round(du.free / 1e9, 1),
            "load": [round(x, 2) for x in os.getloadavg()],
            "uptime_h": round(up / 3600, 1) if up else None,
            "claude": sh(["claude", "--version"]).strip()[:40] or "not found",
            "claude_token": "CLAUDE_CODE_OAUTH_TOKEN" in env_txt,
            "gsc_key": os.path.exists(os.path.expanduser("~/.config/qmp/sa-searchconsole.json")),
            "gh": subprocess.run(["gh", "auth", "status"], cwd=REPO, capture_output=True).returncode == 0,
            "last_commit": sh(["git", "log", "-1", "--format=%h · %s · %cr", "main"]).strip(),
        }
    return cached("health", 30, load)


def agents_view():
    jobs = cached("cron", 60, cron_jobs)
    hist = history(200)
    out = []
    keys = list(AGENTS.keys()) + [k for k in jobs if k not in AGENTS]
    for key in keys:
        name, desc = AGENTS.get(key, (key, ""))
        j = jobs.get(key)
        last = next((h for h in hist if h["kind"] == key), None)
        if key == "00-bootstrap-site" and not j and not last:
            continue
        out.append({
            "key": key, "name": name, "desc": desc,
            "schedules": j["schedules"] if j else [],
            "paused": j["paused"] if j else None,
            "next": j["next"] if j else None,
            "last": {k: last.get(k) for k in ("run_id", "started", "ended", "ok", "cost", "pr", "partial")} if last else None,
            "runs": sum(1 for h in hist if h["kind"] == key),
        })
    return out



# ---------------- published articles + Google index status ----------------

SITE_URL = "https://quotationmaker.pro"
MARKET_PATH = {"us": "us", "gb": "uk", "ca": "ca", "au": "au", "in": "in", "ae": "ae"}  # global has no article route
GSC_FILE = "gsc-index.json"
GSC_TTL = 6 * 3600
_gsc_running = threading.Event()


def articles():
    """Articles on origin/main (what is actually deployed), newest first."""
    def load():
        sh(["git", "fetch", "-q", "origin", "main"], 40)
        ref = "origin/main"
        out = []
        for p in sh(["git", "ls-tree", "-r", "--name-only", ref, "site/src/content/articles"], 15).split():
            if not p.endswith((".md", ".mdx")):
                continue
            fm = fm_text(sh(["git", "show", f"{ref}:{p}"], 15)[:4000])
            market = p.split("/")[-2]
            slug = fm.get("slug") or os.path.splitext(os.path.basename(p))[0]
            path = MARKET_PATH.get(market)
            live = fm.get("published", "").lower() != "false"
            added = sh(["git", "log", "--diff-filter=A", "--format=%ct", "-1", ref, "--", p], 15).strip()
            out.append({
                "title": fm.get("title") or slug, "market": market, "slug": slug, "live": live,
                "url": f"{SITE_URL}/{path}/{slug}/" if (path and live) else None,
                "keyword": fm.get("primaryKeyword", ""), "lastReviewed": fm.get("lastReviewed", ""),
                "reviewBy": fm.get("reviewBy", ""), "added": int(added) if added.isdigit() else None,
            })
        out.sort(key=lambda a: a["added"] or 0, reverse=True)
        return out
    return cached("articles", 600, load)


def gsc_state():
    try:
        with open(rp("state", GSC_FILE)) as f:
            d = json.load(f)
    except Exception:
        d = {"checked": None, "urls": {}, "sitemaps": [], "error": None}
    d["running"] = _gsc_running.is_set()
    return d


def _gsc_cmd(args, timeout=60):
    r = subprocess.run(["scripts/gsc"] + args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:200] if (r.stderr or r.stdout).strip() else "gsc failed")
    return json.loads(r.stdout or "null")


def _gsc_worker():
    d = gsc_state()
    d.pop("running", None)
    errors = []
    urls = [SITE_URL + "/"] + [a["url"] for a in articles() if a["url"]]
    for u in urls:
        try:
            d["urls"][u] = _gsc_cmd(["inspect", "--url", u])
        except Exception as e:
            errors.append(f"{u}: {e}")
    try:
        d["sitemaps"] = (_gsc_cmd(["sitemaps"]) or {}).get("sitemap", [])
    except Exception as e:
        errors.append(f"sitemaps: {e}")
    d["checked"] = int(time.time())
    d["error"] = "; ".join(errors)[:500] or None
    os.makedirs(rp("state"), exist_ok=True)
    tmp = rp("state", GSC_FILE + ".tmp")
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, rp("state", GSC_FILE))


def gsc_refresh(force=False):
    if _gsc_running.is_set():
        return False
    last = gsc_state().get("checked") or 0
    if not force and time.time() - last < GSC_TTL:
        return False
    _gsc_running.set()

    def run():
        try:
            _gsc_worker()
        except Exception as e:
            print("gsc refresh failed:", e)
        finally:
            _gsc_running.clear()
    threading.Thread(target=run, daemon=True).start()
    return True


def gsc_submit_sitemap():
    _gsc_cmd(["submit-sitemap", "--url", SITE_URL + "/sitemap-index.xml"])
    gsc_refresh(force=True)


def status(user):
    return {
        "now": int(time.time()), "user": user,
        "current": current(),
        "agents": agents_view(),
        "history": history(30),
        "prs": prs(),
        "content": content(),
        "published": articles(),
        "gsc": gsc_state(),
        "reports": reports(),
        "health": health(),
        "stages": STAGES,
        "names": {k: v[0] for k, v in AGENTS.items()},
        "busy": busy(),
        "runnable": {k: v[0] for k, v in RUNNABLE.items()},
        "editable": EDITABLE,
        "audit": audit_log(15),
    }



# ---------------- control ----------------

def busy():
    try:
        fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o666)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def audit(user, action, detail=""):
    os.makedirs(rp("state"), exist_ok=True)
    with open(rp("state", "audit.jsonl"), "a") as f:
        f.write(json.dumps({"t": int(time.time()), "user": user, "action": action, "detail": str(detail)[:300]}) + "\n")


def audit_log(limit=20):
    try:
        with open(rp("state", "audit.jsonl")) as f:
            rows = [json.loads(x) for x in f.read().splitlines()[-limit:] if x.strip()]
        return list(reversed(rows))
    except FileNotFoundError:
        return []


def drop_caches(*keys):
    with _lock:
        for k in keys:
            _cache.pop(k, None)


def run_agent(key, arg=None, extra=None):
    if key not in RUNNABLE:
        raise ValueError("unknown agent")
    if busy():
        raise Conflict("Another agent is running. Stop it or wait for it to finish.")
    kind, default = RUNNABLE[key]
    if kind == "pipeline":
        arg = (arg or default or "next").strip()
        if not re.match(r"^(\d{1,6}|next|refresh)$", arg):
            raise ValueError("keyword id must be a number, 'next' or 'refresh'")
        cmd = ["bash", "scripts/pipeline.sh", arg]
    else:
        cmd = ["bash", "scripts/run-agent.sh", key]
        if extra:
            cmd.append(extra[:2000])
    os.makedirs(rp("logs"), exist_ok=True)
    log = open(rp("logs", f"dash-{time.strftime('%Y%m%d-%H%M%S')}-{key}.out"), "ab")
    subprocess.Popen(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True, env=os.environ.copy())
    return " ".join(cmd[1:3])


def _pids(pattern):
    out = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", pattern], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.strip().isdigit() and int(x) != os.getpid()]


def _lock_holders():
    """PIDs (ours) that have the agents lock file open — includes any child a run left behind."""
    pids, me = set(), os.getuid()
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            if os.stat(f"/proc/{d}").st_uid != me:
                continue
            for fd in os.listdir(f"/proc/{d}/fd"):
                if os.readlink(f"/proc/{d}/fd/{fd}") == LOCK:
                    pids.add(int(d))
                    break
        except OSError:
            continue
    return pids


def stop_run():
    cur = None
    try:
        cur = json.load(open(rp("state", "current.json")))
    except Exception:
        pass
    pids = set(_pids(r"scripts/(run-agent|pipeline|agent-exec)\.sh") + _pids(r"claude -p")) | _lock_holders()
    pids.discard(os.getpid())
    mine = os.getpgid(0)
    groups = set()
    for pid in pids:
        try:
            g = os.getpgid(pid)
            if g != mine:
                groups.add(g)
        except ProcessLookupError:
            pass
    if not groups and not cur:
        raise Conflict("Nothing is running.")
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for g in groups:
            try:
                os.killpg(g, sig)
            except (ProcessLookupError, PermissionError):
                pass
        for _ in range(10):
            time.sleep(0.5)
            if not busy():
                break
        if not busy():
            break
    if cur:
        with open(rp("state", "history.jsonl"), "a") as f:
            f.write(json.dumps({"run_id": cur.get("run_id"), "kind": cur.get("kind"), "stage": cur.get("stage"),
                                "branch": cur.get("branch"), "started": cur.get("started"), "ended": int(time.time()),
                                "exit": -15, "ok": False, "cost": None, "turns": None, "pr": None,
                                "summary": "Stopped from the dashboard."}) + "\n")
        try:
            os.remove(rp("state", "current.json"))
        except FileNotFoundError:
            pass
    return cur.get("kind") if cur else "processes"


def set_schedule(key, enabled):
    out = sh(["crontab", "-l"])
    lines, inblock, changed = out.splitlines(), False, 0
    for i, line in enumerate(lines):
        if "QMP growth agents >>>" in line:
            inblock = True
            continue
        if "QMP growth agents <<<" in line:
            break
        if not inblock or "scripts/" not in line:
            continue
        m = re.search(r"run-agent\.sh\s+(\S+)", line)
        p = re.search(r"pipeline\.sh\s+(\S+)", line)
        k = m.group(1) if m else (f"pipeline-{'refresh' if p.group(1) == 'refresh' else 'next'}" if p else None)
        if k != key:
            continue
        body = line.lstrip("#").strip()
        lines[i] = body if enabled else "# " + body
        changed += 1
    if not changed:
        raise ValueError("no schedule for this agent")
    r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "crontab failed")
    drop_caches("cron")
    return changed


def sync_repo():
    if busy():
        raise Conflict("An agent is running; sync when it finishes.")
    sh(["git", "stash", "push", "-u", "-m", "dashboard sync"], 30)
    r = subprocess.run("git fetch -q origin && git switch -q -C main origin/main", shell=True, cwd=REPO,
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    drop_caches("content", "health")
    return sh(["git", "log", "-1", "--format=%h %s"]).strip()


def repo_slug():
    url = sh(["git", "remote", "get-url", "origin"]).strip()
    m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
    if not m:
        raise RuntimeError("can't find the GitHub repo")
    return m.group(1)


def gh_api(args, body=None):
    r = subprocess.run(["gh", "api"] + args + (["--input", "-"] if body is not None else []), cwd=REPO,
                       input=json.dumps(body) if body is not None else None, capture_output=True, text=True, timeout=30)
    if r.returncode:
        msg = r.stdout.strip() or r.stderr.strip()
        try:
            msg = json.loads(msg).get("message", msg)
        except Exception:
            pass
        raise RuntimeError(msg[:300])
    return json.loads(r.stdout) if r.stdout.strip() else {}


def file_get(path):
    if path not in EDITABLE:
        raise ValueError("file not editable")
    try:
        d = gh_api([f"repos/{repo_slug()}/contents/{path}?ref=main"])
        return {"path": path, "sha": d["sha"], "content": base64.b64decode(d["content"]).decode("utf-8", "replace")}
    except RuntimeError as e:
        if "Not Found" in str(e):
            return {"path": path, "sha": None, "content": ""}
        raise


def file_put(path, content, sha, message):
    if path not in EDITABLE:
        raise ValueError("file not editable")
    if len(content.encode()) > 300_000:
        raise ValueError("file too large")
    body = {"message": (message or f"Update {path} from dashboard")[:200], "branch": "main",
            "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    d = gh_api(["-X", "PUT", f"repos/{repo_slug()}/contents/{path}"], body)
    drop_caches("content")
    return (d.get("commit") or {}).get("sha", "")[:7]


def pr_action(number, action):
    n = int(number)
    slug = repo_slug()
    pr = gh_api([f"repos/{slug}/pulls/{n}"])
    ref = pr["head"]["ref"]
    if action == "merge":
        gh_api(["-X", "PUT", f"repos/{slug}/pulls/{n}/merge"], {"merge_method": "squash"})
    elif action == "close":
        gh_api(["-X", "PATCH", f"repos/{slug}/pulls/{n}"], {"state": "closed"})
    else:
        raise ValueError("unknown action")
    if ref.startswith("agent/"):
        try:
            gh_api(["-X", "DELETE", f"repos/{slug}/git/refs/heads/{ref}"])
        except RuntimeError:
            pass
    drop_caches("prs")
    return f"#{n} {action}d"


# ---------------- http ----------------

class H(BaseHTTPRequestHandler):
    server_version = "qmp-dash"

    def log_message(self, *a):
        pass

    def user(self):
        email = (self.headers.get("Cf-Access-Authenticated-User-Email") or "").strip().lower()
        if email:
            return email if (not ALLOWED or email in ALLOWED) else None
        if ALLOW_LOCAL and self.client_address[0] in ("127.0.0.1", "::1"):
            return "local"
        return None

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        u = self.user()
        if not u:
            return self.send(403, {"error": "Sign in through admin.quotationmaker.pro"})
        # CSRF: only our own page (custom header + same-origin) may call control endpoints
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if self.headers.get("X-QMP") != "1" or (origin and urlparse(origin).netloc != host):
            return self.send(403, {"error": "bad request origin"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 400_000:
                return self.send(413, {"error": "too large"})
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send(400, {"error": "bad json"})
        path = urlparse(self.path).path
        try:
            if path == "/api/run":
                what = run_agent(body.get("key", ""), body.get("arg"), (body.get("extra") or "").strip() or None)
                audit(u, "run", what)
                return self.send(200, {"ok": True, "message": f"Started {AGENTS.get(body.get('key'), (body.get('key'),))[0]}"})
            if path == "/api/stop":
                what = stop_run()
                audit(u, "stop", what)
                return self.send(200, {"ok": True, "message": "Run stopped"})
            if path == "/api/schedule":
                en = bool(body.get("enabled"))
                set_schedule(body.get("key", ""), en)
                audit(u, "resume" if en else "pause", body.get("key"))
                return self.send(200, {"ok": True, "message": "Schedule resumed" if en else "Schedule paused"})
            if path == "/api/sync":
                head = sync_repo()
                audit(u, "sync", head)
                return self.send(200, {"ok": True, "message": f"Server repo now at {head}"})
            if path == "/api/file":
                sha = file_put(body.get("path", ""), body.get("content", ""), body.get("sha"), body.get("message"))
                audit(u, "edit", f"{body.get('path')} → {sha}")
                return self.send(200, {"ok": True, "message": f"Committed {sha} to main"})
            if path == "/api/gsc":
                if body.get("action") == "submit-sitemap":
                    gsc_submit_sitemap()
                    audit(u, "sitemap", "resubmitted sitemap-index.xml")
                    return self.send(200, {"ok": True, "message": "Sitemap resubmitted. Rechecking Google…"})
                started = gsc_refresh(force=True)
                audit(u, "gsc", "index check")
                return self.send(200, {"ok": True, "message": "Checking Google… takes about a minute" if started else "A check is already running"})
            if path == "/api/pr":
                msg = pr_action(body.get("number"), body.get("action"))
                audit(u, "pr", msg)
                return self.send(200, {"ok": True, "message": msg})
            return self.send(404, {"error": "not found"})
        except Conflict as e:
            return self.send(409, {"error": str(e)})
        except (ValueError, RuntimeError) as e:
            return self.send(400, {"error": str(e)})
        except Exception as e:
            return self.send(500, {"error": type(e).__name__})

    def do_GET(self):
        u = self.user()
        if not u:
            return self.send(403, "Forbidden — sign in through admin.quotationmaker.pro", "text/plain")
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html")
            if url.path == "/api/status":
                return self.send(200, status(u))
            if url.path == "/api/run":
                return self.send(200, {"events": events(q.get("run_id", ""), q.get("stage", ""), limit=0)})
            if url.path == "/api/report":
                name = q.get("name", "")
                path = rp("reports", name)
                if not (SAFE.match(name) and name.endswith(".md") and os.path.isfile(path)):
                    return self.send(404, {"error": "not found"})
                with open(path, errors="replace") as f:
                    return self.send(200, {"name": name, "text": f.read()[:200000]})
            if url.path == "/api/file":
                try:
                    return self.send(200, file_get(q.get("path", "")))
                except (ValueError, RuntimeError) as e:
                    return self.send(400, {"error": str(e)})
            if url.path == "/healthz":
                return self.send(200, {"ok": True})
            return self.send(404, {"error": "not found"})
        except Exception as e:  # never leak a traceback to the browser
            return self.send(500, {"error": type(e).__name__})


if __name__ == "__main__":
    def ticker():  # re-check Google every 6 hours without anyone clicking
        while True:
            try:
                if os.path.exists(rp("scripts", "gsc")) and os.path.exists(os.path.expanduser(os.environ.get("GSC_KEY", "~/.config/qmp/sa-searchconsole.json"))):
                    gsc_refresh()
            except Exception as e:
                print("gsc ticker:", e)
            time.sleep(1800)
    threading.Thread(target=ticker, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"QMP dashboard on http://127.0.0.1:{PORT}  repo={REPO}  allowed={sorted(ALLOWED) or 'any Access user'}")
    srv.serve_forever()

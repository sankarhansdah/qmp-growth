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
import csv
import datetime as dt
import glob
import json
import os
import re
import shutil
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
        fields = "number,title,url,createdAt,headRefName,isDraft"
        o = sh(["gh", "pr", "list", "--state", "open", "--limit", "30", "--json", fields], 20)
        m = sh(["gh", "pr", "list", "--state", "merged", "--limit", "8", "--json", "number,title,url,mergedAt"], 20)
        try:
            return {"open": json.loads(o or "[]"), "merged": json.loads(m or "[]"), "ok": bool(o)}
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


def status(user):
    return {
        "now": int(time.time()), "user": user,
        "current": current(),
        "agents": agents_view(),
        "history": history(30),
        "prs": prs(),
        "content": content(),
        "reports": reports(),
        "health": health(),
        "stages": STAGES,
        "names": {k: v[0] for k, v in AGENTS.items()},
    }


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
            if url.path == "/healthz":
                return self.send(200, {"ok": True})
            return self.send(404, {"error": "not found"})
        except Exception as e:  # never leak a traceback to the browser
            return self.send(500, {"error": type(e).__name__})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"QMP dashboard on http://127.0.0.1:{PORT}  repo={REPO}  allowed={sorted(ALLOWED) or 'any Access user'}")
    srv.serve_forever()

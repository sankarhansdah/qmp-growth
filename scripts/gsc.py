#!/usr/bin/env python3
"""Search Console CLI for QMP agents, using the service-account key directly.

  scripts/gsc sites
  scripts/gsc query   --days 28 [--prev] [--dims page,query,country] [--country usa] [--rows 25000]
  scripts/gsc inspect --url https://quotationmaker.pro/us/some-page/
  scripts/gsc sitemaps
  scripts/gsc submit-sitemap --url https://quotationmaker.pro/sitemap-index.xml

Env: GSC_KEY (default ~/.config/qmp/sa-searchconsole.json), GSC_SITE (default sc-domain:quotationmaker.pro)
Output: JSON on stdout. Data lags ~2-3 days, so windows end 3 days ago.
"""
import argparse, datetime as dt, json, os, sys
from urllib.parse import quote

from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

KEY = os.path.expanduser(os.environ.get("GSC_KEY", "~/.config/qmp/sa-searchconsole.json"))
SITE = os.environ.get("GSC_SITE", "sc-domain:quotationmaker.pro")
WM = "https://www.googleapis.com/webmasters/v3"
SC = "https://searchconsole.googleapis.com/v1"
RO = "https://www.googleapis.com/auth/webmasters.readonly"
RW = "https://www.googleapis.com/auth/webmasters"


def session(write=False):
    creds = service_account.Credentials.from_service_account_file(KEY, scopes=[RW if write else RO])
    return AuthorizedSession(creds)


def call(s, method, url, body=None):
    r = s.request(method, url, json=body, timeout=60)
    if r.status_code >= 400:
        sys.stderr.write(f"HTTP {r.status_code}: {r.text}\n")
        sys.exit(1)
    return r.json() if r.text.strip() else {}


def site_path(site):
    return f"{WM}/sites/{quote(site, safe='')}"


def window(days, prev):
    end = dt.date.today() - dt.timedelta(days=3)
    if prev:
        end -= dt.timedelta(days=days)
    start = end - dt.timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def cmd_sites(a):
    print(json.dumps(call(session(), "GET", f"{WM}/sites"), indent=1))


def cmd_query(a):
    start, end = (a.start, a.end) if a.start else window(a.days, a.prev)
    body = {"startDate": start, "endDate": end, "dimensions": a.dims.split(","),
            "rowLimit": min(a.rows, 25000), "startRow": 0}
    if a.country:
        body["dimensionFilterGroups"] = [{"filters": [
            {"dimension": "country", "operator": "equals", "expression": a.country}]}]
    s, rows = session(), []
    while True:
        res = call(s, "POST", f"{site_path(a.site)}/searchAnalytics/query", body)
        batch = res.get("rows", [])
        rows += batch
        if len(batch) < body["rowLimit"] or len(rows) >= a.rows:
            break
        body["startRow"] += len(batch)
    out = [dict(zip(body["dimensions"], r["keys"]), clicks=r["clicks"], impressions=r["impressions"],
                ctr=round(r["ctr"], 4), position=round(r["position"], 1)) for r in rows[:a.rows]]
    print(json.dumps({"site": a.site, "start": start, "end": end, "rows": out}, indent=1))


def cmd_inspect(a):
    body = {"inspectionUrl": a.url, "siteUrl": a.site, "languageCode": "en-US"}
    res = call(session(), "POST", f"{SC}/urlInspection/index:inspect", body)
    r = res.get("inspectionResult", {}).get("indexStatusResult", {})
    print(json.dumps({"url": a.url, "verdict": r.get("verdict"), "coverage": r.get("coverageState"),
                      "lastCrawl": r.get("lastCrawlTime"), "googleCanonical": r.get("googleCanonical"),
                      "robots": r.get("robotsTxtState"), "indexing": r.get("indexingState")}, indent=1))


def cmd_sitemaps(a):
    print(json.dumps(call(session(), "GET", f"{site_path(a.site)}/sitemaps"), indent=1))


def cmd_submit(a):
    call(session(write=True), "PUT", f"{site_path(a.site)}/sitemaps/{quote(a.url, safe='')}")
    print(json.dumps({"submitted": a.url}))


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--site", default=SITE)
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("sites").set_defaults(f=cmd_sites)
q = sub.add_parser("query")
q.add_argument("--days", type=int, default=28)
q.add_argument("--prev", action="store_true", help="the window before the last one (for comparison)")
q.add_argument("--start"); q.add_argument("--end")
q.add_argument("--dims", default="page,query,country")
q.add_argument("--country", help="ISO-3166 alpha-3, e.g. usa, gbr, ind")
q.add_argument("--rows", type=int, default=5000)
q.set_defaults(f=cmd_query)
i = sub.add_parser("inspect"); i.add_argument("--url", required=True); i.set_defaults(f=cmd_inspect)
sub.add_parser("sitemaps").set_defaults(f=cmd_sitemaps)
sm = sub.add_parser("submit-sitemap"); sm.add_argument("--url", required=True); sm.set_defaults(f=cmd_submit)

if __name__ == "__main__":
    a = p.parse_args()
    a.f(a)

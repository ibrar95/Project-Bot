#!/usr/bin/env python3
"""
Daily Project Finder
- Public feeds se naye jobs/projects uthata hai (Remotive, RemoteOK, WeWorkRemotely, Jobicy)
- Sirf NAYE dikhata hai (seen.json mein purane yaad rakhta hai)
- Report: daily_report.html (browser mein khud khulti hai)
- LinkedIn / Upwork / Freelancer / Fiverr scrape nahi hote (un ke rules ke khilaf).
  Un ke liye report mein "last 24 hours" wale search links milte hain.

Chalane ka tareeqa:  python daily_projects.py
Sirf Python 3.8+ chahiye. Koi extra install nahi.
"""
import json, os, re, sys, html, webbrowser, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

# ---------- APNI SETTINGS ----------
KEYWORDS = {
    "Graphic Design": ["graphic design", "logo", "brand identity", "packaging", "illustrator", "designer"],
    "Web": ["wordpress", "web design", "web developer", "landing page", "shopify", "woocommerce", "frontend"],
    "SEO": ["seo", "keyword research", "link building", "search engine"],
    "Marketing": ["social media", "facebook ads", "instagram", "digital marketing", "ppc", "meta ads"],
    "Writing": ["copywriter", "content writer", "blog", "article", "seo content", "copywriting"],
}
EXCLUDE = ["senior director", "10+ years", "security clearance",
           "us only", "usa only", "u.s. only", "us-only", "must be located in the us",
           "us citizens only", "uk only", "eu only", "canada only"]   # in words wali jobs hata do
TOP_N = 40   # report mein kitne best projects dikhane hain
MAX_PER_SOURCE = 60
# ------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(HERE, "seen.json")
REPORT = os.path.join(HERE, "docs", "index.html")
UA = {"User-Agent": "Mozilla/5.0 (DailyProjectFinder personal use)"}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(t or ""))).strip()


def src_remotive():
    out = []
    for cat in ("design", "marketing", "writing", "software-dev"):
        data = json.loads(get(f"https://remotive.com/api/remote-jobs?category={cat}&limit=50"))
        for j in data.get("jobs", []):
            out.append(dict(id="rm" + str(j["id"]), title=j["title"], company=j.get("company_name", ""),
                            url=j["url"], desc=strip(j.get("description", ""))[:300],
                            when=j.get("publication_date", ""), source="Remotive"))
    return out


def src_remoteok():
    data = json.loads(get("https://remoteok.com/api"))
    out = []
    for j in data:
        if not isinstance(j, dict) or "id" not in j:
            continue  # pehla item legal notice hota hai
        out.append(dict(id="ro" + str(j["id"]), title=j.get("position", ""), company=j.get("company", ""),
                        url=j.get("url", ""), desc=strip(j.get("description", ""))[:300] + " " + " ".join(j.get("tags", [])),
                        when=j.get("date", ""), source="RemoteOK"))
    return out


def src_wwr():
    out = []
    for cat in ("remote-design-jobs", "remote-marketing-jobs", "remote-copywriting-jobs", "remote-front-end-programming-jobs"):
        root = ET.fromstring(get(f"https://weworkremotely.com/categories/{cat}.rss"))
        for it in root.iter("item"):
            g = lambda k: (it.findtext(k) or "")
            out.append(dict(id="ww" + g("guid"), title=g("title"), company="", url=g("link"),
                            desc=strip(g("description"))[:300], when=g("pubDate"), source="WeWorkRemotely"))
    return out


def src_jobicy():
    data = json.loads(get("https://jobicy.com/api/v2/remote-jobs?count=50"))
    return [dict(id="jb" + str(j["id"]), title=j.get("jobTitle", ""), company=j.get("companyName", ""),
                 url=j.get("url", ""), desc=strip(j.get("jobExcerpt", ""))[:300],
                 when=j.get("pubDate", ""), source="Jobicy") for j in data.get("jobs", [])]


SOURCES = [src_remotive, src_remoteok, src_wwr, src_jobicy]


def match(job):
    text = (job["title"] + " " + job["desc"]).lower()
    if any(x in text for x in EXCLUDE):
        return None
    hits = [f for f, kws in KEYWORDS.items() if any(k in text for k in kws)]
    return hits or None


def age_hours(s):
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    try:
        try:
            d = parsedate_to_datetime(s)
        except Exception:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).total_seconds() / 3600
    except Exception:
        return None


def score(j):
    t, d = j["title"].lower(), j["desc"].lower()
    s = 0
    for kws in KEYWORDS.values():
        for k in kws:
            if k in t:
                s += 3
            elif k in d:
                s += 1
    h = age_hours(j["when"])
    if h is not None:
        s += 5 if h < 24 else 2 if h < 72 else 0
    return s


def search_links():
    q = lambda s: urllib.parse.quote(s)
    base = ["logo design", "wordpress", "SEO", "social media marketing", "content writing", "graphic designer"]
    rows = []
    for k in base:
        rows.append((k,
            f"https://www.linkedin.com/jobs/search/?keywords={q(k)}&f_TPR=r86400&f_WT=2",
            f"https://www.upwork.com/nx/search/jobs/?q={q(k)}&sort=recency",
            f"https://www.freelancer.com/jobs/?keyword={q(k)}"))
    return rows


def build_report(new_jobs, errors):
    e = html.escape
    cards = ""
    for j in new_jobs:
        tags = "".join(f"<span class=t>{e(x)}</span>" for x in j["fields"])
        cards += (f"<div class=c><div class=h><a href='{e(j['url'])}' target=_blank>{e(j['title'])}</a>"
                  f"<span class=s>{'NEW · ' if j['new'] else ''}Score {j['score']} · {e(j['source'])}</span></div><div class=m>{e(j['company'])} · {e(j['when'][:16])}</div>"
                  f"<p>{e(j['desc'][:220])}...</p>{tags}"
                  f"<a class=b href='{e(j['url'])}' target=_blank>Apply / Open</a></div>")
    if not cards:
        cards = "<p>Aaj koi naya matching project nahi mila. Keywords ko wide kar ke dekho.</p>"
    links = "".join(f"<tr><td>{e(k)}</td><td><a href='{e(a)}' target=_blank>LinkedIn (24h)</a></td>"
                    f"<td><a href='{e(b)}' target=_blank>Upwork (newest)</a></td>"
                    f"<td><a href='{e(c)}' target=_blank>Freelancer</a></td></tr>" for k, a, b, c in search_links())
    err = "".join(f"<li>{e(x)}</li>" for x in errors)
    return f"""<!DOCTYPE html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Daily Projects</title><style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:820px;margin:0 auto;padding:16px;background:#f6f5f1;color:#1d1d1b}}
.c{{background:#fff;border:1px solid #e2e0d8;border-radius:12px;padding:14px;margin:12px 0}}
.h{{display:flex;justify-content:space-between;gap:8px}} .h a{{font-weight:700;color:#0f6e56;text-decoration:none}}
.s{{font-size:12px;background:#e1f5ee;color:#0f6e56;border-radius:10px;padding:2px 8px;height:fit-content}}
.m{{color:#6b6a63;font-size:14px}} .t{{font-size:12px;border:1px solid #ccc;border-radius:10px;padding:1px 8px;margin-right:6px}}
.b{{display:inline-block;margin-top:8px;background:#0f6e56;color:#fff;padding:6px 14px;border-radius:8px;text-decoration:none}}
table{{width:100%;border-collapse:collapse}} td{{padding:6px;border-bottom:1px solid #e2e0d8}}
</style></head><body><h1>Daily Projects: {datetime.now():%d %b %Y}</h1>
<p>Top {len(new_jobs)} best projects (score ke hisaab se). NEW wale aaj pehli baar mile hain.</p>{cards}
<h2>Manual check (in sites ko scrape karna allowed nahi)</h2><table>{links}</table>
{'<h3>Kuch sources fail hue</h3><ul>'+err+'</ul>' if err else ''}</body></html>"""


def main():
    seen = set(json.load(open(SEEN_FILE))) if os.path.exists(SEEN_FILE) else set()
    new_jobs, errors, ids = [], [], set()
    for fn in SOURCES:
        try:
            for j in fn()[:MAX_PER_SOURCE * 4]:
                if j["id"] in ids:
                    continue
                f = match(j)
                if f:
                    j["fields"] = f
                    j["new"] = j["id"] not in seen
                    j["score"] = score(j)
                    new_jobs.append(j)
                    ids.add(j["id"])
        except Exception as ex:
            errors.append(f"{fn.__name__}: {ex}")
    new_jobs.sort(key=lambda x: x["score"], reverse=True)
    new_jobs = new_jobs[:TOP_N]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w", encoding="utf-8").write(build_report(new_jobs, errors))
    json.dump(sorted(seen | ids), open(SEEN_FILE, "w"))
    print(f"{len(new_jobs)} naye projects. Report: {REPORT}")
    for x in errors:
        print("WARN", x)
    if "--no-open" not in sys.argv:
        webbrowser.open("file://" + REPORT)


if __name__ == "__main__":
    main()

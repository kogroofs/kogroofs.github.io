#!/usr/bin/env python3
"""KOG site check: run before every publish.  python3 .claude/site_check.py

Catches the things that can get kogroofs.com in trouble with Google:
broken internal links, missing or wrong canonicals, pages missing from
the sitemap or llms.txt, noindex pages left in the sitemap, duplicate
titles or descriptions, FAQ schema that doesn't match the page, review
or rating schema on KOG itself, date signals that disagree, and claims
KOG can't make yet. Exits 1 if anything fails.
"""
import html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://kogroofs.com/"
SKIP = {"404.html"}
# Claims about KOG that must not appear until they're true and Bobby confirms them.
BLOCKED_CLAIMS = [r"\bKOG (?:is|are) (?:fully )?(?:licensed|insured|bonded)",
                  r"licensed,? (?:bonded|insured)", r"insured (?:and|&) bonded",
                  r"\b(?:GAF|Owens Corning|Malarkey|CertainTeed)[- ](?:certified|Master Elite|Preferred|Platinum)",
                  r"FORTIFIED[- ]certified roofer", r"Google Guaranteed"]
problems = []

def bad(page, msg):
    problems.append(f"{page}: {msg}")

def norm(s):
    return re.sub(r"[^a-z0-9]", "", html.unescape(re.sub(r"<[^>]+>", " ", s)).lower())

def walk(x, out):
    if isinstance(x, dict):
        out.append(x)
        for v in x.values():
            walk(v, out)
    elif isinstance(x, list):
        for v in x:
            walk(v, out)
    return out

files = set()
for d, _, fs in os.walk(ROOT):
    if "/.git" in d:
        continue
    for f in fs:
        files.add(os.path.relpath(os.path.join(d, f), ROOT))
pages = sorted(f for f in os.listdir(ROOT) if f.endswith(".html") and not f.startswith("google"))
sitemap = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
lastmod = {(u or "index.html"): d for u, d in re.findall(r"<loc>https://kogroofs\.com/([^<]*)</loc><lastmod>([^<]*)</lastmod>", sitemap)}
llms = set(u or "index.html" for u in re.findall(r"https://kogroofs\.com/?([^)\s]*)", open(os.path.join(ROOT, "llms.txt"), encoding="utf-8").read()))
for u in lastmod:
    if u not in files:
        bad("sitemap.xml", f"points to a page that doesn't exist: {u}")
seen_titles, seen_descs = {}, {}

for p in pages:
    if p in SKIP:
        continue
    t = open(os.path.join(ROOT, p), encoding="utf-8").read()
    noindex = re.search(r'<meta name="robots" content="[^"]*noindex', t)
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', t)
    canon = re.search(r'<link rel="canonical" href="([^"]*)"', t)
    want = SITE + ("" if p == "index.html" else p)
    if not title:
        bad(p, "no <title>")
    elif title.group(1).strip() in seen_titles:
        bad(p, f"same title as {seen_titles[title.group(1).strip()]}")
    else:
        seen_titles[title.group(1).strip()] = p
    if not desc:
        bad(p, "no meta description")
    elif desc.group(1) in seen_descs:
        bad(p, f"same description as {seen_descs[desc.group(1)]}")
    else:
        seen_descs[desc.group(1)] = p
    if not canon or canon.group(1) != want:
        bad(p, f"canonical should be {want}")
    if len(re.findall(r"<h1[\s>]", t)) != 1:
        bad(p, "needs exactly one <h1>")
    if noindex:
        if p in lastmod:
            bad(p, "noindex but listed in sitemap.xml")
    else:
        if p not in lastmod:
            bad(p, "missing from sitemap.xml")
        if p not in llms:
            bad(p, "missing from llms.txt")

    no_js = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    for m in re.finditer(r'(?:href|src)="([^"]+)"', no_js):
        u = html.unescape(m.group(1))
        if u.startswith(("mailto:", "tel:", "sms:", "#", "javascript:", "data:")) or (u.startswith("http") and not u.startswith(SITE)):
            continue
        path = u.replace(SITE, "/").split("#")[0].split("?")[0]
        if not path:
            continue
        path = "index.html" if path == "/" else os.path.normpath(path.lstrip("/"))
        if path not in files:
            bad(p, f"broken link: {u}")

    visible = norm(no_js)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", no_js)))
    for pat in BLOCKED_CLAIMS:
        m = re.search(pat, text, re.I)
        if m:
            bad(p, f"claim KOG can't make yet: '{m.group(0)}'")
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try:
            nodes = walk(json.loads(blk), [])
        except ValueError as e:
            bad(p, f"broken JSON-LD: {e}")
            continue
        for n in nodes:
            if n.get("@type") == "RoofingContractor" and ("aggregateRating" in n or "review" in n):
                bad(p, "review/rating schema on KOG itself (Google calls this self-serving)")
            if n.get("@type") == "Question":
                if norm(n.get("name", "")) not in visible or norm(n.get("acceptedAnswer", {}).get("text", "")) not in visible:
                    bad(p, f"FAQ schema doesn't match the page: {n.get('name', '')[:60]}")
            if "dateModified" in n and p in lastmod and n["dateModified"] != lastmod[p]:
                bad(p, f"dateModified {n['dateModified']} but sitemap lastmod {lastmod[p]}")

for line in problems:
    print("FAIL", line)
print(f"{len(pages)} pages checked, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)

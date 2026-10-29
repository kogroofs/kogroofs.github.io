#!/usr/bin/env python3
"""Link new town pages into kogroofs.com: service areas, home page, chat
widget, sitemap, llms.txt, and Nearby lists on existing town pages.

usage: link_towns.py TOWN [TOWN ...]   (run from the repo folder; pages must exist)
"""
import html, json, os, re, sys
from datetime import date

sys.path.insert(0, os.getcwd())
import hail_builder as hb
import town_hail as th

new = sys.argv[1:]
today = date.today().isoformat()
def slug(t): return t.lower().replace(" ", "-") + "-roofing.html"
def link(t): return f'<a href="{slug(t)}">{t}</a>'

def edit(path, fn):
    s = open(path, encoding="utf-8").read()
    n = fn(s)
    if n != s:
        open(path, "w", encoding="utf-8").write(n)
        print("updated", path)

# ---- service areas: county list and ZIP-checker page map
def sa(s):
    for t in new:
        s, n = re.subn(r'(<li><strong>Tarrant County</strong><span>[^\n]*?), ' + re.escape(t) + r'(,|</span>)',
                       lambda m: m.group(1) + ", " + link(t) + m.group(2), s, count=1)
        if n == 0:
            assert link(t) in s, t
    # linked towns first (alphabetical), then the rest, like the other counties
    m = re.search(r'(<li><strong>Tarrant County</strong><span>)(.*?)(</span></li>)', s)
    items = [x.strip() for x in m.group(2).split(", ")]
    linked = sorted([x for x in items if x.startswith("<a ")], key=lambda x: re.sub("<[^>]+>", "", x))
    plain = sorted([x for x in items if not x.startswith("<a ")])
    s = s[:m.start(2)] + ", ".join(linked + plain) + s[m.end(2):]
    m = re.search(r"var PAGES = (\{.*?\});", s)
    pages = json.loads(m.group(1))
    for t in new:
        pages[t] = slug(t)
    s = s[:m.start(1)] + json.dumps(pages, ensure_ascii=False) + s[m.end(1):]
    return s
edit("service-areas.html", sa)

# ---- home page: Tarrant County line
def home(s):
    m = re.search(r'(<li><strong><a href="fort-worth-roofing.html">Tarrant County</a></strong><span>)(.*?)(</span></li>)', s)
    items = [x.strip() for x in m.group(2).split(", ")]
    for t in new:
        if t in items:
            items[items.index(t)] = link(t)
        elif link(t) not in items:
            items.append(link(t))
    return s[:m.start(2)] + ", ".join(items) + s[m.end(2):]
edit("index.html", home)

# ---- chat widget town list
def chat(s):
    m = re.search(r"var TOWN_PAGES = \[(.*?)\];", s, re.S)
    towns = json.loads("[" + m.group(1) + "]")
    towns = sorted(set(towns) | set(new))
    lines, cur = [], "  var TOWN_PAGES = ["
    for i, t in enumerate(towns):
        piece = json.dumps(t) + (", " if i < len(towns) - 1 else "")
        if len(cur) + len(piece) > 110:
            lines.append(cur.rstrip())
            cur = "    "
        cur += piece
    lines.append(cur + "];")
    return s[:m.start()] + "\n".join(lines).lstrip() + s[m.end():]
edit("kog-chat.js", chat)

# ---- sitemap
def smap(s):
    for t in new:
        loc = f"https://kogroofs.com/{slug(t)}"
        if loc not in s:
            s = s.replace("</urlset>", f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod></url>\n</urlset>")
    return s
edit("sitemap.xml", smap)

# ---- llms.txt town lines, kept alphabetical
def llms(s):
    lines = s.split("\n")
    i = lines.index("## Towns") + 2
    j = i
    while j < len(lines) and lines[j].startswith("- [Roofing in"):
        j += 1
    block = lines[i:j]
    for t in new:
        page = open(slug(t), encoding="utf-8").read()
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', page).group(1))
        line = f"- [Roofing in {t}, TX](https://kogroofs.com/{slug(t)}): Roof Repair, Replacement, and Hail|{desc}"
        block = [b for b in block if f"/{slug(t)})" not in b] + [line]
    block.sort(key=lambda b: b.split("]")[0].lower())
    return "\n".join(lines[:i] + block + lines[j:])
edit("llms.txt", llms)

# ---- Nearby lists on existing town pages: add a new town when it's closer
# than the farthest town already listed (at most 5 listed)
zips = json.load(open(hb.ZIP_FILE, encoding="utf-8"))
OVR = {"Fort Worth": (32.7555, -97.3308), "Dallas": (32.7767, -96.797)}
for k, (pts, _) in th.CENTERS.items():
    OVR.setdefault(k, pts[0])
def center(t):
    if t in OVR: return OVR[t]
    p = [(z[3], z[4]) for z in zips if z[1] == t]
    return (sum(a for a, b in p) / len(p), sum(b for a, b in p) / len(p))
def miles(a, b): return hb.point_miles(a[0], a[1], b[0], b[1])
ITEM = re.compile(r'<li><a href="([a-z-]+)-roofing\.html">Roofing in ([^<]+)</a><p>About (\d+) miles away\.</p></li>')
for page in sorted(os.listdir(".")):
    if not page.endswith("-roofing.html") or page in th.NOT_TOWNS + ("roofing-contract.html",):
        continue
    me = th.town_name(page)
    if me in new:
        continue
    s = open(page, encoding="utf-8").read()
    m = re.search(r'(<h2>Nearby</h2>\n<ul class="guide-list">\n)(.*?)(\n</ul>)', s, re.S)
    if not m:
        continue
    items = ITEM.findall(m.group(2))
    have = [x[1] for x in items]
    far = max(int(x[2]) for x in items)
    c0 = center(me)
    adds = [t for t in new if t not in have and round(miles(c0, center(t))) < far]
    if not adds:
        continue
    adds = sorted(adds, key=lambda t: miles(c0, center(t)))[:max(0, 5 - len(items))]
    if not adds:
        continue
    rows = [(x[1], int(x[2])) for x in items] + [(t, max(1, round(miles(c0, center(t))))) for t in adds]
    rows.sort(key=lambda r: r[1])
    body = "\n".join(f'<li><a href="{slug(t)}">Roofing in {t}</a><p>About {d} miles away.</p></li>' for t, d in rows)
    s = s[:m.start(2)] + body + s[m.end(2):]
    open(page, "w", encoding="utf-8").write(s)
    print("nearby", page, "+", adds)

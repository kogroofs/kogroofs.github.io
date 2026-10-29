#!/usr/bin/env python3
"""Build KOG town pages for batch 3 from towns_b3.py.

usage: gen_towns.py OUT_DIR TOWN [TOWN ...]
Run from the kogroofs.github.io folder. LIVE env var: comma list of extra
town names that count as live for the Nearby links (besides existing pages).
"""
import html, json, math, os, re, sys
from datetime import date, datetime

REPO = "/home/claude/kogroofs.github.io"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hail_builder as hb
import town_hail as th
from towns_b3 import TOWNS, NCEI

out_dir, names = sys.argv[1], sys.argv[2:]
extra_live = [x for x in os.environ.get("LIVE", "").split(",") if x]

tpl = open(os.path.join(REPO, "north-richland-hills-roofing.html"), encoding="utf-8").read()
style = tpl[tpl.index("<style>"):tpl.index("</style>") + len("</style>")]
body_top = tpl[tpl.index('<body id="top">'):tpl.index('<main id="main">')]
foot = tpl[tpl.index("</main>"):]
icon_fonts = tpl[tpl.index('<link rel="icon"'):tpl.index("<style>")]

today = datetime.now(hb.CENTRAL).date()
start = date(today.year - hb.YEARS_BACK, 1, 1)
zips = json.load(open(hb.ZIP_FILE, encoding="utf-8"))
segs = hb.build_segments(hb.load_radar(start))
ground = hb.load_ground(start)
month_line = f"Hail records updated {th.MONTH_NAMES[today.month - 1]} {today.year}."

def slug(t): return t.lower().replace(" ", "-") + "-roofing.html"
def esc(s): return html.escape(s, quote=True)
def plain(s): return html.unescape(re.sub(r"<[^>]+>", "", s))

# ---- town centers for Nearby
OVR = {"Fort Worth": (32.7555, -97.3308), "Dallas": (32.7767, -96.797), "Benbrook": (32.6733, -97.4606)}
for k, (pts, _) in th.CENTERS.items():
    OVR.setdefault(k, pts[0])
def center(t):
    if t in OVR: return OVR[t]
    p = [(z[3], z[4]) for z in zips if z[1] == t]
    return (sum(a for a, b in p) / len(p), sum(b for a, b in p) / len(p))
def miles(a, b): return hb.point_miles(a[0], a[1], b[0], b[1])
existing = sorted(th.town_name(p) for p in os.listdir(REPO)
                  if p.endswith("-roofing.html") and p not in th.NOT_TOWNS + ("roofing-contract.html",))

for t in names:
    T = TOWNS[t]
    pts, where = th.town_points(t, zips)
    assert pts, t
    days = th.town_days(pts, segs, ground)
    block = th.block_html(t, where, start, today, days)
    S = th.summary_sentence(t, start, days)
    short = th.short_text(t, start, days)
    county = T["county"]
    county_text = T.get("county_text", county + " County")
    head_county = {"Crowley": "Tarrant County", "Haslet": "Tarrant and Denton counties"}.get(t, county_text)
    url = "https://kogroofs.com/" + slug(t)
    title = f"Roofing in {t}, TX | Roof Repair, Replacement, and Hail | KOG Roofing"
    tail = T["desc_tail"]; tail = tail[0].upper() + tail[1:]
    desc = f"Roof repair and replacement in {t}, Texas. {short}. {tail}"
    faq = [(q, a.replace("{S}", S)) for q, a in T["faq"]]

    service = {"@context": "https://schema.org", "@type": "Service", "serviceType": "Roofing",
               "name": f"Roofing in {t}, TX",
               "provider": {"@type": "RoofingContractor", "name": "KOG Roofing", "url": "https://kogroofs.com/",
                            "telephone": "+1-817-550-2339", "@id": "https://kogroofs.com/#business"},
               "areaServed": {"@type": "City", "name": f"{t}, TX",
                              "containedInPlace": {"@type": "AdministrativeArea", "name": f"{county} County, TX"}},
               "url": url}
    faqld = {"@context": "https://schema.org", "@type": "FAQPage",
             "mainEntity": [{"@type": "Question", "name": q,
                             "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in faq]}

    live = sorted(set(existing + extra_live) - {t})
    c0 = center(t)
    near = sorted(live, key=lambda x: miles(c0, center(x)))[:3]

    H = []
    H.append("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
             "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    H.append(f"<title>{esc(title)}</title>")
    H.append(f'<meta name="description" content="{esc(desc)}">')
    H.append('<meta name="theme-color" content="#1F2A5C">')
    H.append(f'<meta property="og:title" content="{esc(title)}">')
    H.append(f'<meta property="og:description" content="{esc(desc)}">')
    H.append('<meta property="og:type" content="website">')
    H.append(f'<meta property="og:url" content="{url}">')
    H.append('<script type="application/ld+json">\n' + json.dumps(service, indent=1, ensure_ascii=False) + "\n</script>")
    H.append(f'<link rel="canonical" href="{url}">')
    H.append(icon_fonts.rstrip("\n"))
    H.append(style)
    H.append('<script type="application/ld+json">\n' + json.dumps(faqld, indent=1, ensure_ascii=False) + "\n</script>")
    H.append("</head>")
    H.append(body_top.rstrip("\n"))
    M = []
    M.append('<main id="main">\n<div class="article-head">\n<div class="narrow">\n'
             '<p class="crumb"><a href="service-areas.html">Service areas</a></p>\n'
             f"<h1>Roofing in {t}</h1>\n<p class=\"updated\">{head_county}, Texas. {month_line}</p>\n</div>\n</div>\n"
             '<article class="article">\n<div class="narrow">')
    M.append(f'<div class="short">\n<h2>The short answer</h2>\n<p>{T["intro"]} {S} {T["permit_short"]}</p>\n</div>\n')
    M.append(f"<h2>Hail near {t}</h2>\n{block}\n<p>{T['hail_after']}</p>\n")
    M.append(f"<h2>When hail hits {t}</h2>\n" + "\n".join(f"<p>{p}</p>" for p in T["timing"]) +
             f'\n<p class="note">Times are when radar first picked up hail 1 inch or larger near {t}, using the same '
             f"NOAA records and the same 3-mile rule as above. Months and times are counted through October 2026.</p>\n")
    M.append(f"<h2>Permits in {t}</h2>\n" + "\n".join(f"<p>{p}</p>" for p in T["permits"]) + "\n")
    M.append(f"<h2>{T['local_h']}</h2>\n" + "\n".join(f"<p>{p}</p>" for p in T["local"]) + "\n")
    M.append(f'<h2 id="prices">Roof prices in {t}</h2>\n<p>{T["prices_intro"]}</p>\n<ul class="prices">' +
             "".join(f"<li><span>{a}</span><b>{b}</b></li>" for a, b in T["prices"]) + "</ul>\n" +
             f"<p>{T['prices_after']}</p>\n"
             '<p class="note">Typical ranges from our <a href="roof-prices.html">price page</a>, updated October 2026. '
             "They're not quotes: your written price comes after the free inspection. Insurance paying? The scope your "
             "insurance company approves sets the price, and you pay your deductible. Paying for it yourself? Code KOG100 "
             "takes $100 off any job of $500 or more.</p>\n")
    M.append(f"<h2>What we do in {t}</h2>\n<p>{T['work']}</p>\n")
    M.append(f"<h2>ZIP codes we serve in {t}</h2>\n<ul class=\"zips\">" + "".join(f"<li>{z}</li>" for z in T["zips"]) +
             f"</ul>\n<p>{T['zip_after']}</p>\n")
    M.append("<h2>Common questions</h2>\n" + "\n".join(f"<h3>{q}</h3>\n<p>{a}</p>" for q, a in faq) + "\n")
    M.append('<h2>Where this comes from</h2>\n<ul class="note">\n' +
             "\n".join(f'<li><a href="{u}">{esc(n)}</a></li>' for u, n in [NCEI] + T["sources"]) + "\n</ul>\n")
    M.append(f'<div class="cta-box">\n<h2>In {t}?</h2>\n<p>Call for a free inspection. You\'ll get photos and an honest '
             "answer about whether your roof needs a repair, a replacement, or nothing at all.</p>\n<div class=\"actions\">\n"
             '<a class="btn btn-yellow" href="free-inspection.html">Request a free inspection</a>\n'
             '<a class="btn btn-line" href="tel:+18175502339">Call (817) 550-2339</a>\n'
             '<a class="btn btn-line" href="sms:+18175502339?&amp;body=Hi%20KOG%20Roofing%2C%20I%20found%20you%20online.%20">Text us</a>\n'
             "</div>\n</div>")
    M.append('<div class="more">\n<h2>Nearby</h2>\n<ul class="guide-list">\n' +
             "\n".join(f'<li><a href="{slug(n)}">Roofing in {n}</a><p>About {max(1, round(miles(c0, center(n))))} miles away.</p></li>'
                       for n in near) + "\n</ul>\n</div>\n</div>\n</article>")
    page = "\n".join(H) + "\n" + "\n".join(M) + "\n" + foot
    path = os.path.join(out_dir, slug(t))
    open(path, "w", encoding="utf-8").write(page)
    # the nightly script must recognise every sentence it keeps in step
    assert th.summary_re(t).search(page) and th.short_re(t).search(page), t
    print(f"{slug(t)}: {len(days)} hail days, near {near}")

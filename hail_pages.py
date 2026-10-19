#!/usr/bin/env python3
"""KOG Roofing hail report page builder.

Runs every night on GitHub right after hail_builder.py (see
.github/workflows/hail-data.yml). It reads only the hail files that
hail_builder.py already saved, so it needs no internet.

It rewrites the parts of hail-report.html between the KOG markers:
the report itself, the "checked" date, and the page's schema. The rest
of the page (header, styles, footer) is left alone.

Prints "hail-report.html" when the report itself changed, so the nightly
job knows to tell Bing about it. A new "checked" date alone doesn't count.
"""

import html
import json
import os
import re
import sys
from datetime import date, datetime

import hail_builder as hb

PAGE = os.path.join(hb.ROOT, "hail-report.html")
URL = hb.SITE + "/hail-report.html"
BIZ_ID = hb.SITE + "/#business"
MONTHS_SHOWN = 12     # months listed on the page, newest first
TOWNS_PER_DAY = 8     # towns named per storm day before "and N more"
NOAA_URL = "https://www.ncei.noaa.gov/products/severe-weather-data-inventory"
# How a few ZIP-file town names should read on the page
DISPLAY_NAMES = {"Desoto": "DeSoto", "Mckinney": "McKinney", "Naval Air Station Jrb": "NAS JRB Fort Worth"}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def esc(s):
    return html.escape(DISPLAY_NAMES.get(str(s), str(s)), quote=False)


def size_text(s):
    return "about " + f"{s:.2f}".rstrip("0").rstrip(".") + (" inch" if s == 1 else " inches")


def long_date(d):
    return f"{MONTH_NAMES[d.month - 1]} {d.day}, {d.year}"


def day_label(d):
    return d.strftime("%A, ") + f"{MONTH_NAMES[d.month - 1]} {d.day}"


def town_pages():
    """City name -> town page on the site, for linking."""
    pages = {}
    for name in os.listdir(hb.ROOT):
        if name.endswith("-roofing.html") and name not in ("commercial-roofing.html", "metal-roofing.html"):
            slug = name[:-len("-roofing.html")]
            pages[" ".join(w.capitalize() for w in slug.split("-"))] = name
    return pages


def hits_by_day(segs, ground, zips):
    """Same rule as the storm reports: hail 1 inch or larger within
    TOWN_RADIUS miles of a ZIP center. Returns {day: {"towns": {city: size}, "max": size}}."""
    by_day = {}
    for s in segs:
        if max(s[5], s[6]) >= hb.ALERT_SIZE:
            by_day.setdefault(s[0], ([], []))[0].append(s)
    for g in ground:
        if g[3] >= hb.ALERT_SIZE:
            by_day.setdefault(g[0], ([], []))[1].append(g)
    out = {}
    for d, (day_segs, day_ground) in by_day.items():
        towns = {}
        for z, city, county, zlat, zlon in zips:
            best = None
            for _, alat, alon, blat, blon, asz, bsz in day_segs:
                if abs(alat - zlat) > 0.2 and abs(blat - zlat) > 0.2:
                    continue
                dist, t = hb.seg_distance(zlat, zlon, alat, alon, blat, blon)
                if dist <= hb.TOWN_RADIUS:
                    size = asz if t < 0.5 else bsz
                    if size >= hb.ALERT_SIZE and (best is None or size > best):
                        best = size
            for g in day_ground:
                if hb.point_miles(zlat, zlon, g[1], g[2]) <= hb.TOWN_RADIUS and (best is None or g[3] > best):
                    best = g[3]
            if best is not None:
                towns[city] = max(towns.get(city, 0), best)
        if towns:
            out[d] = {"towns": towns, "max": max(towns.values())}
    return out


def town_list(towns, pages):
    ranked = sorted(towns.items(), key=lambda kv: (-kv[1], kv[0]))
    names = []
    for city, _ in ranked[:TOWNS_PER_DAY]:
        page = pages.get(city)
        names.append(f'<a href="{page}">{esc(city)}</a>' if page else esc(city))
    more = len(ranked) - len(names)
    if more:
        names.append(f"{more} more town" + ("s" if more > 1 else ""))
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + (", and " if len(names) > 2 else " and ") + names[-1]


def biggest(days):
    """(day, size, city) of the biggest hail among these days."""
    best = None
    for d, rec in days.items():
        city, size = max(rec["towns"].items(), key=lambda kv: (kv[1], kv[0]))
        if best is None or size > best[1] or (size == best[1] and d > best[0]):
            best = (d, size, city)
    return best


def build_report(today, hits, pages):
    months = []
    y, m = today.year, today.month
    for _ in range(MONTHS_SHOWN):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    parts = []
    this_year = {d: r for d, r in hits.items() if d.year == today.year}
    this_month = {d: r for d, r in this_year.items() if d.month == today.month}
    last_day = max(hits) if hits else None

    # the short answer
    lines = []
    month_name = MONTH_NAMES[today.month - 1]
    if this_month:
        b = biggest(this_month)
        lines.append(f"So far this {month_name}, NOAA weather radar has picked up hail 1 inch or larger "
                     f"in towns we serve on {len(this_month)} day{'s' if len(this_month) != 1 else ''}. "
                     f"The biggest was {size_text(b[1])} near {esc(b[2])} on {long_date(b[0])}.")
    else:
        lines.append(f"So far this {month_name}, NOAA weather radar hasn't picked up hail 1 inch or larger "
                     f"in any of the towns we serve.")
        if last_day:
            rec = hits[last_day]
            city = max(rec["towns"].items(), key=lambda kv: (kv[1], kv[0]))[0]
            lines.append(f"The last day it did was {long_date(last_day)}, with {size_text(rec['max'])} "
                         f"near {esc(city)}.")
    if this_year:
        b = biggest(this_year)
        lines.append(f"In {today.year} so far, there have been {len(this_year)} days with 1-inch hail in at least "
                     f"one town we serve. The biggest was {size_text(b[1])} near {esc(b[2])} on {long_date(b[0])}.")
    parts.append('<div class="short">\n<h2>The short answer</h2>\n<p>' + " ".join(lines) + "</p>\n</div>")

    parts.append('<p>Wondering about your own street? <a href="hail-check.html">Check your address</a> '
                 'against the same radar records. Hail damage often doesn\'t leak right away, so a roof that '
                 'looks fine from the ground can still be bruised.</p>')

    # month by month
    for (y, m) in months:
        days = {d: r for d, r in hits.items() if d.year == y and d.month == m}
        current = (y, m) == (today.year, today.month)
        label = f"{MONTH_NAMES[m - 1]} {y}" + (" so far" if current else "")
        parts.append(f'<h2 id="m{y}-{m:02d}">{label}</h2>')
        if not days:
            parts.append("<p>No hail 1 inch or larger in the towns we serve.</p>")
            continue
        towns_hit = set()
        for r in days.values():
            towns_hit.update(r["towns"])
        b = biggest(days)
        parts.append(f"<p>{len(days)} day{'s' if len(days) != 1 else ''} with hail 1 inch or larger, "
                     f"hitting {len(towns_hit)} town{'s' if len(towns_hit) != 1 else ''} in all. "
                     f"The biggest was {size_text(b[1])} near {esc(b[2])}.</p>")
        items = []
        for d in sorted(days, reverse=True):
            r = days[d]
            items.append(f"<li><strong>{day_label(d)}</strong><span>Up to {size_text(r['max'])}: "
                         f"{town_list(r['towns'], pages)}.</span></li>")
        parts.append('<ul class="hail-days">\n' + "\n".join(items) + "\n</ul>")

    # by year
    parts.append('<h2 id="by-year">Year by year</h2>')
    parts.append("<p>Days with hail 1 inch or larger in at least one town we serve:</p>")
    rows = []
    for yr in sorted({d.year for d in hits}, reverse=True):
        days = {d: r for d, r in hits.items() if d.year == yr}
        b = biggest(days)
        label = f"{yr} so far" if yr == today.year else str(yr)
        rows.append(f"<li><span>{label}</span><b>{len(days)} days</b></li>")
    parts.append('<ul class="prices">' + "".join(rows) + "</ul>")
    biggest_rows = []
    for yr in sorted({d.year for d in hits}, reverse=True):
        days = {d: r for d, r in hits.items() if d.year == yr}
        b = biggest(days)
        biggest_rows.append(f"<li><strong>{yr}</strong><span>{size_text(b[1]).capitalize()} near "
                            f"{esc(b[2])}, {long_date(b[0])}</span></li>")
    parts.append("<p>The biggest hail each year:</p>")
    parts.append('<ul class="hail-days">\n' + "\n".join(biggest_rows) + "\n</ul>")

    return "\n".join(parts)


def schema(today, start):
    data = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "DFW hail report: radar-detected hail 1 inch or larger by town",
        "description": ("Every day NOAA NEXRAD weather radar detected hail 1 inch or larger within "
                        f"{hb.TOWN_RADIUS:g} miles of a ZIP code center in the Dallas-Fort Worth towns KOG Roofing "
                        "serves, with the biggest estimated stone size for each town. Updated every morning."),
        "url": URL,
        "creator": {"@id": BIZ_ID},
        "publisher": {"@id": BIZ_ID},
        "isBasedOn": NOAA_URL,
        "temporalCoverage": f"{start.isoformat()}/{today.isoformat()}",
        "spatialCoverage": {
            "@type": "Place",
            "name": "Dallas-Fort Worth Metroplex, Texas",
            "geo": {"@type": "GeoShape", "box": f"{hb.SOUTH} {hb.WEST} {hb.NORTH} {hb.EAST}"},
        },
        "variableMeasured": "Estimated maximum hail size (inches)",
        "dateModified": today.isoformat(),
        "inLanguage": "en-US",
        "keywords": ["hail", "Dallas-Fort Worth", "hail map", "roof damage", "NEXRAD"],
    }
    return ('<script type="application/ld+json">\n' + json.dumps(data, indent=1, ensure_ascii=False)
            + "\n</script>")


def swap(text, name, new):
    pat = re.compile(r"(<!-- KOG:%s:START -->).*?(<!-- KOG:%s:END -->)" % (name, name), re.S)
    if not pat.search(text):
        raise SystemExit(f"hail-report.html is missing its {name} markers; not changing it")
    old = pat.search(text).group(0)
    return pat.sub(lambda m: m.group(1) + "\n" + new + "\n" + m.group(2), text, count=1), old


def main():
    today = datetime.now(hb.CENTRAL).date()
    if os.environ.get("HAIL_TODAY"):  # local testing only
        today = date.fromisoformat(os.environ["HAIL_TODAY"])
    start = date(today.year - hb.YEARS_BACK, 1, 1)
    with open(hb.ZIP_FILE, encoding="utf-8") as f:
        zips = json.load(f)
    segs = hb.build_segments(hb.load_radar(start))
    ground = hb.load_ground(start)
    hits = hits_by_day(segs, ground, zips)

    with open(PAGE, encoding="utf-8") as f:
        page = f.read()
    report = build_report(today, hits, town_pages())
    page, old_report = swap(page, "REPORT", report)
    page, _ = swap(page, "CHECKED", f"Updated every morning from NOAA weather radar. Last checked {long_date(today)}.")
    page, _ = swap(page, "SCHEMA", schema(today, start))
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(page)

    new_report = re.search(r"<!-- KOG:REPORT:START -->.*?<!-- KOG:REPORT:END -->", page, re.S).group(0)
    if new_report != old_report:
        print("hail-report.html")
    print(f"hail report: {len(hits)} storm days since {start}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

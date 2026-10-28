#!/usr/bin/env python3
"""KOG Roofing town page hail history.

Runs every night on GitHub right after hail_pages.py (see
.github/workflows/hail-data.yml). It reads only the hail files that
hail_builder.py already saved, so it needs no internet.

For every town page (granbury-roofing.html, weatherford-roofing.html, ...)
it rebuilds the hail record between the markers

    <!-- KOG:TOWNHAIL:START --> ... <!-- KOG:TOWNHAIL:END -->

and keeps the sentences that repeat those numbers in step: the short
answer, the common-questions answer and its schema, the page description,
the "Hail records updated" line, the town's line in llms.txt, and the
page's lastmod in sitemap.xml.

It uses the same rule as the address hail check (hail-check.html) and the
DFW hail report: radar hail within TOWN_RADIUS miles of a ZIP code center,
sized at the nearest point of the storm track.

A page is only rewritten when its numbers change, so a quiet night changes
nothing. Prints the name of each page that changed, so the nightly job
can tell Bing about it.
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime

import hail_builder as hb

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
NOT_TOWNS = ("commercial-roofing.html", "metal-roofing.html")
BIGGEST_SHOWN = 4

# Towns that aren't a ZIP code city of their own: (lat, lon) and how the page says it.
CENTERS = {
    "Pecan Plantation": ([(32.3637, -97.6625)], "the center of Pecan Plantation"),
    "Willow Park": ([(32.758, -97.653)], "the center of town"),
}

START_MARK = "<!-- KOG:TOWNHAIL:START -->"
END_MARK = "<!-- KOG:TOWNHAIL:END -->"
BLOCK_RE = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.S)


def long_date(d):
    return f"{MONTH_NAMES[d.month - 1]} {d.day}, {d.year}"


def inches(s):
    n = f"{s:.2f}".rstrip("0").rstrip(".")
    return f"about {n} inch" if s == 1 else f"about {n} inches"


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def town_name(page):
    slug = page[:-len("-roofing.html")]
    return " ".join(w.capitalize() for w in slug.split("-"))


def town_points(city, zips):
    if city in CENTERS:
        pts, where = CENTERS[city]
        return pts, where
    pts = [(z[3], z[4]) for z in zips if z[1] == city]
    if not pts:
        return [], ""
    where = ("the center of its ZIP code" if len(pts) == 1
             else f"the center of one of its {len(pts)} ZIP codes")
    return pts, where


def town_days(points, segs, ground):
    """{day: biggest hail} within TOWN_RADIUS miles of any of these points."""
    days = {}
    for d, alat, alon, blat, blon, asz, bsz in segs:
        for plat, plon in points:
            if abs(alat - plat) > 0.2 and abs(blat - plat) > 0.2:
                continue
            dist, t = hb.seg_distance(plat, plon, alat, alon, blat, blon)
            if dist <= hb.TOWN_RADIUS:
                size = asz if t < 0.5 else bsz
                if size > days.get(d, 0):
                    days[d] = size
    for g in ground:
        for plat, plon in points:
            if hb.point_miles(plat, plon, g[1], g[2]) <= hb.TOWN_RADIUS and g[3] > days.get(g[0], 0):
                days[g[0]] = g[3]
    return days


def facts(days):
    one = {d: s for d, s in days.items() if s >= 1}
    two = [d for d, s in days.items() if s >= 2]
    top = sorted(days.items(), key=lambda kv: (-kv[1], -kv[0].toordinal()))
    return one, two, top


def block_html(city, where, start, today, days):
    one, two, top = facts(days)
    since = f"{MONTH_NAMES[start.month - 1]} {start.year}"
    p = []
    if days:
        p.append(f'<p class="stat">Since {since}, NOAA weather radar detected hail near {city} on '
                 f'<b>{plural(len(days), "day")}</b>. On <b>{len(one)}</b> of them the stones were 1 inch '
                 f'or larger, and on <b>{len(two)}</b> they were 2 inches or larger.</p>')
        p.append("<p>The biggest storm days:</p>")
        p.append('<ul class="prices">' + "".join(
            f"<li><span>{long_date(d)}</span><b>{inches(s)}</b></li>" for d, s in top[:BIGGEST_SHOWN]) + "</ul>")
    else:
        p.append(f'<p class="stat">Since {since}, NOAA weather radar hasn\'t detected hail 3/4 inch or larger '
                 f'near {city}.</p>')
    if one:
        last = max(one)
        p.append(f"<p>The most recent day with hail 1 inch or larger was {long_date(last)}, "
                 f"at {inches(one[last])}.</p>")
        per_year = Counter(d.year for d in one)
        rows = []
        for yr in range(start.year, today.year + 1):
            label = f"{yr} so far" if yr == today.year else str(yr)
            rows.append(f"<li><span>{label}</span><b>{plural(per_year.get(yr, 0), 'day')}</b></li>")
        p.append("<p>Days with hail 1 inch or larger, by year:</p>")
        p.append('<ul class="prices">' + "".join(rows) + "</ul>")
    p.append(f'<p class="note">"Near {city}" means within {hb.TOWN_RADIUS:g} miles of {where}. These are '
             "radar estimates of hail size from NOAA's NEXRAD weather radars, not measurements on the ground. "
             "Radar can miss small or short bursts, and stone sizes vary block to block. This record updates "
             "on its own when radar picks up new hail.</p>")
    return START_MARK + "\n" + "\n".join(p) + "\n" + END_MARK


def summary_sentence(city, start, days):
    """The sentence the short answer and common questions use."""
    one, _, top = facts(days)
    since = f"{MONTH_NAMES[start.month - 1]} {start.year}"
    if not one:
        return f"Since {since}, NOAA weather radar hasn't picked up hail 1 inch or larger near {city}."
    big = top[0][1]
    ties = sorted(d for d, s in days.items() if s == big)
    if len(ties) == 1:
        tail = f"The biggest was {inches(big)}, on {long_date(ties[0])}."
    else:
        tail = f"The biggest were {inches(big)}, on " + " and ".join(long_date(d) for d in ties[:2]) + "."
    return (f"Since {since}, NOAA weather radar picked up hail 1 inch or larger near {city} on "
            f"{plural(len(one), 'different day')}. {tail}")


DATE = r"[A-Z][a-z]+ \d{1,2}, \d{4}"


def summary_re(city):
    c = re.escape(city)
    return re.compile(
        r"Since [A-Z][a-z]+ \d{4}, NOAA weather radar (?:"
        r"picked up hail 1 inch or larger near " + c + r" on \d+ different days?\. "
        r"The biggest (?:was|were) about [\d.]+ inch(?:es)?, on " + DATE + r"(?: and " + DATE + r")?\."
        r"|hasn't picked up hail 1 inch or larger near " + c + r"\.)")


def short_re(city):
    return re.compile(r"Radar picked up hail 1 inch or larger near " + re.escape(city) +
                      r" on \d+ days? since \d{4}")


# "on 6 of the 15 days with 1-inch hail since 2023, the stones reached 2 inches or more" (Burleson)
BIG_RE = re.compile(r"\d+ of the \d+ days with 1-inch hail( here)? since \d{4}, the stones reached 2 inches or more")


def short_text(city, start, days):
    one, _, _ = facts(days)
    return f"Radar picked up hail 1 inch or larger near {city} on {plural(len(one), 'day')} since {start.year}"


def main():
    today = datetime.now(hb.CENTRAL).date()
    if os.environ.get("HAIL_TODAY"):  # local testing only
        today = date.fromisoformat(os.environ["HAIL_TODAY"])
    start = date(today.year - hb.YEARS_BACK, 1, 1)
    with open(hb.ZIP_FILE, encoding="utf-8") as f:
        zips = json.load(f)
    segs = hb.build_segments(hb.load_radar(start))
    ground = hb.load_ground(start)
    if not segs:
        print("town hail: no radar data, leaving town pages alone", file=sys.stderr)
        return 0

    llms_path = os.path.join(hb.ROOT, "llms.txt")
    sitemap_path = os.path.join(hb.ROOT, "sitemap.xml")
    llms = open(llms_path, encoding="utf-8").read() if os.path.exists(llms_path) else None
    sitemap = open(sitemap_path, encoding="utf-8").read() if os.path.exists(sitemap_path) else None
    llms_old, sitemap_old = llms, sitemap
    month_line = f"Hail records updated {MONTH_NAMES[today.month - 1]} {today.year}."

    changed = []
    for page in sorted(os.listdir(hb.ROOT)):
        if not page.endswith("-roofing.html") or page in NOT_TOWNS:
            continue
        path = os.path.join(hb.ROOT, page)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if START_MARK not in text or END_MARK not in text:
            print(f"town hail: {page} has no markers, skipped", file=sys.stderr)
            continue
        city = town_name(page)
        points, where = town_points(city, zips)
        if not points:
            print(f"town hail: no ZIP codes or center for {city}, skipped", file=sys.stderr)
            continue
        days = town_days(points, segs, ground)
        new = BLOCK_RE.sub(lambda m: block_html(city, where, start, today, days), text, count=1)
        if new == text:
            continue  # numbers unchanged: leave the page alone
        new = summary_re(city).sub(summary_sentence(city, start, days), new)
        new = short_re(city).sub(short_text(city, start, days), new)
        one, two, _ = facts(days)
        new = BIG_RE.sub(lambda m: f"{len(two)} of the {len(one)} days with 1-inch hail{m.group(1) or ''} since "
                                   f"{start.year}, the stones reached 2 inches or more", new)
        new = re.sub(r"Hail records updated [A-Z][a-z]+ \d{4}\.", month_line, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        changed.append(page)
        if llms is not None:
            llms = short_re(city).sub(short_text(city, start, days), llms)
        if sitemap is not None:
            sitemap = re.sub(r"(<loc>" + re.escape(hb.SITE + "/" + page) + r"</loc><lastmod>)[\d-]+(</lastmod>)",
                             lambda m: m.group(1) + today.isoformat() + m.group(2), sitemap)

    if llms is not None and llms != llms_old:
        with open(llms_path, "w", encoding="utf-8") as f:
            f.write(llms)
    if sitemap is not None and sitemap != sitemap_old:
        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(sitemap)
    for page in changed:
        print(page)
    print(f"town hail: {len(changed)} town pages updated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

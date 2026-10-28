#!/usr/bin/env python3
"""KOG Roofing hail data builder.

Runs every night on GitHub (see .github/workflows/hail-data.yml). It:
  1. Downloads NOAA radar hail detections (NEXRAD Level III hail signatures,
     NOAA NCEI Severe Weather Data Inventory) for the KOG service area.
  2. Downloads NOAA Storm Prediction Center ground hail reports for the
     last few days.
  3. Builds small map tiles in hail-data/tiles/ that the Hail Check page
     (hail-check.html) reads in the visitor's browser.
  4. When hail 1 inch or larger hits towns in the service area, opens a
     GitHub issue (a storm report). GitHub emails it to the account owner.

Uses only the Python standard library. Run it locally without a GitHub
token and it prints the storm reports instead of posting them.
"""

import csv
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "hail-data")
RADAR_DIR = os.path.join(DATA, "radar")
GROUND_DIR = os.path.join(DATA, "ground")
TILE_DIR = os.path.join(DATA, "tiles")
STATE_FILE = os.path.join(DATA, "reported.json")
META_FILE = os.path.join(DATA, "meta.json")
RECENT_FILE = os.path.join(DATA, "recent.json")
ZIP_FILE = os.path.join(ROOT, "service-zips.json")

# Service area box: west, south, east, north (covers all 14 counties + margin)
WEST, SOUTH, EAST, NORTH = -98.8, 31.8, -95.7, 33.6
TILE = 0.5            # degrees per tile
MARGIN = 0.08         # tiles include hail this far outside their edges (~5 mi)
YEARS_BACK = 3        # history kept: Jan 1 three years back to today
REFETCH_DAYS = 62     # months newer than this get downloaded again
MIN_SIZE = 0.75       # smallest radar hail size kept for the map (inches)
ALERT_SIZE = 1.0      # storm reports start at this size (inches)
ALERT_DAYS = 10       # only report storms from the last N days
TOWN_RADIUS = 3.0     # miles from a town (ZIP) center
TRACK_GAP_MIN = 12    # radar points this close in time join into a track
TRACK_GAP_MI = 15
SITE = "https://kogroofs.com"
PHONE = "(817) 550-2339"

SWDI_URL = ("https://www.ncei.noaa.gov/swdiws/csv/nx3hail/{start}:{end}"
            "?bbox={w},{s},{e},{n}")
SPC_URL = "https://www.spc.noaa.gov/climo/reports/{d}_rpts_hail.csv"
USER_AGENT = "KOG Roofing hail check (https://kogroofs.com; kogroofs@gmail.com)"
RADAR_HEADER = ["ZTIME", "WSR_ID", "CELL_ID", "PROB", "SEVPROB", "MAXSIZE", "LAT", "LON"]
GROUND_HEADER = ["UTC", "LOCAL_DATE", "SIZE", "LAT", "LON", "LOCATION", "COUNTY", "STATE"]

# Radar sites near the service area. Hail estimates get rough far from the
# radar, so detections more than MAX_RADAR_KM from their radar are dropped.
# Radars not listed here are kept.
RADAR_SITES = {
    "KFWS": (32.573, -97.303), "KDYX": (32.538, -99.254), "KGRK": (30.722, -97.383),
    "KSJT": (31.371, -100.492), "KFDR": (34.362, -98.976), "KTLX": (35.333, -97.278),
    "KSHV": (32.451, -93.841), "KINX": (36.175, -95.564), "KEWX": (29.704, -98.028),
    "KHGX": (29.472, -95.079), "KLBB": (33.654, -101.814), "KVNX": (36.741, -98.128),
    "KSRX": (35.290, -94.362), "KMAF": (31.943, -102.189), "KAMA": (35.233, -101.709),
    "KDFW": (33.065, -96.918), "TDFW": (33.065, -96.918),
    "KDAL": (32.926, -96.968), "TDAL": (32.926, -96.968),
}
MAX_RADAR_KM = 200

FIXTURES = os.environ.get("HAIL_FIXTURE_DIR")  # local testing only
warnings = []


def log(msg):
    print(msg, flush=True)


def warn(msg):
    warnings.append(msg)
    print("WARNING: " + msg, flush=True)


# ---------------------------------------------------------------- downloads

def http_get(url, tries=4):
    if FIXTURES:
        name = url.split("/")[-1].split("?")[0].replace(":", "_")
        path = os.path.join(FIXTURES, name)
        if not os.path.exists(path):
            raise urllib.error.HTTPError(url, 404, "fixture missing", None, None)
        with open(path, encoding="utf-8") as f:
            return f.read()
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:  # timeouts, resets
            last = e
        time.sleep(5 * (3 ** attempt))
    raise last


def month_iter(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def next_month(y, m):
    return date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)


def parse_swdi(text):
    lines = [ln.strip() for ln in text.splitlines()]
    try:
        h = next(i for i, ln in enumerate(lines) if ln.startswith("ZTIME,"))
    except StopIteration:
        if "count,0" in lines:  # NOAA leaves out the header when nothing was detected
            return []
        raise ValueError("no data header in NOAA reply: " + text[:200].replace("\n", " "))
    rows, expected = [], None
    for ln in lines[h + 1:]:
        if ln.startswith("count,"):
            try:
                expected = int(ln.split(",")[1])
            except ValueError:
                pass
            continue
        parts = ln.split(",")
        if len(parts) != 8 or not parts[0][:4].isdigit():
            continue
        try:
            float(parts[5]); float(parts[6]); float(parts[7])
        except ValueError:
            continue
        rows.append(parts)
    if expected is not None and expected != len(rows):
        raise ValueError(f"NOAA said {expected} rows but sent {len(rows)}")
    return rows


def update_radar(today):
    os.makedirs(RADAR_DIR, exist_ok=True)
    start = date(today.year - YEARS_BACK, 1, 1)
    fresh_after = today - timedelta(days=REFETCH_DAYS)
    fetched = 0
    for y, m in month_iter(start, today):
        path = os.path.join(RADAR_DIR, f"{y:04d}-{m:02d}.csv")
        m_start, m_end = date(y, m, 1), next_month(y, m)
        if os.path.exists(path) and m_end < fresh_after:
            continue
        end = min(m_end, today + timedelta(days=1))
        url = SWDI_URL.format(start=m_start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"),
                              w=WEST, s=SOUTH, e=EAST, n=NORTH)
        try:
            rows = parse_swdi(http_get(url))
        except Exception as e:
            warn(f"radar {y}-{m:02d} not updated ({e})")
            continue
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(RADAR_HEADER)
            w.writerows(rows)
        fetched += 1
        log(f"radar {y}-{m:02d}: {len(rows)} detections")
        if not FIXTURES:
            time.sleep(1.5)
    # drop months older than the history window
    for name in os.listdir(RADAR_DIR):
        if name.endswith(".csv") and name[:7] < f"{start.year:04d}-01":
            os.remove(os.path.join(RADAR_DIR, name))
    return fetched


def spc_local(conv_day, hhmm):
    """SPC times are UTC within the convective day (12Z to 12Z)."""
    hh, mm = int(hhmm[:2]), int(hhmm[2:])
    t = datetime(conv_day.year, conv_day.month, conv_day.day, hh, mm, tzinfo=timezone.utc)
    if hh < 12:
        t += timedelta(days=1)
    return t, t.astimezone(CENTRAL).date()


def update_ground(today):
    os.makedirs(GROUND_DIR, exist_ok=True)
    new = {}
    for back in (1, 2, 3, 4):
        day = today - timedelta(days=back)
        url = SPC_URL.format(d=day.strftime("%y%m%d"))
        try:
            text = http_get(url, tries=2)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                warn(f"ground reports {day} not updated ({e})")
            continue
        except Exception as e:
            warn(f"ground reports {day} not updated ({e})")
            continue
        reader = csv.reader(io.StringIO(text))
        header = next(reader, [])
        if [h.strip().lower() for h in header[:7]] != ["time", "size", "location", "county", "state", "lat", "lon"]:
            warn(f"ground reports {day}: unexpected format {header[:8]}")
            continue
        for row in reader:
            if len(row) < 7 or not row[0].strip().isdigit() or len(row[0].strip()) != 4:
                continue
            try:
                size = int(row[1]) / 100.0
                lat, lon = float(row[5]), float(row[6])
            except ValueError:
                continue
            if lon > 0:  # some feeds drop the minus sign
                lon = -lon
            if not (SOUTH <= lat <= NORTH and WEST <= lon <= EAST):
                continue
            t, local = spc_local(day, row[0].strip())
            key = (t.strftime("%Y-%m-%dT%H:%MZ"), f"{lat:.3f}", f"{lon:.3f}")
            new[key] = [key[0], local.isoformat(), f"{size:.2f}", f"{lat:.3f}", f"{lon:.3f}",
                        tidy(row[2].strip()), tidy(row[3].strip()), row[4].strip().upper()]
        if not FIXTURES:
            time.sleep(1)
    by_month = {}
    for rec in new.values():
        by_month.setdefault(rec[1][:7], {})[(rec[0], rec[3], rec[4])] = rec
    for month, recs in by_month.items():
        path = os.path.join(GROUND_DIR, f"{month}.csv")
        merged = {}
        if os.path.exists(path):
            for rec in read_csv(path):
                merged[(rec[0], rec[3], rec[4])] = rec
        merged.update(recs)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(GROUND_HEADER)
            w.writerows(sorted(merged.values()))
    start = date(today.year - YEARS_BACK, 1, 1)
    for name in os.listdir(GROUND_DIR):
        if name.endswith(".csv") and name[:7] < f"{start.year:04d}-01":
            os.remove(os.path.join(GROUND_DIR, name))
    return len(new)


DIRECTIONS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NNE", "ENE", "ESE", "SSE",
              "SSW", "WSW", "WNW", "NNW"}


def tidy(place):
    """'2 WNW GRANBURY' -> '2 WNW Granbury'."""
    words = []
    for w in place.split():
        words.append(w.upper() if w.upper() in DIRECTIONS else w.capitalize())
    return " ".join(words)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        return [row for row in r if row]


# ------------------------------------------------------------------ geometry

def miles_xy(lat0):
    return 69.172 * math.cos(math.radians(lat0)), 68.97


def seg_distance(lat, lon, a_lat, a_lon, b_lat, b_lon):
    """Miles from a point to segment a-b, and t (0 at a, 1 at b)."""
    kx, ky = miles_xy(lat)
    ax, ay = (a_lon - lon) * kx, (a_lat - lat) * ky
    bx, by = (b_lon - lon) * kx, (b_lat - lat) * ky
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(px, py), t


def point_miles(lat1, lon1, lat2, lon2):
    kx, ky = miles_xy((lat1 + lat2) / 2)
    return math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * ky)


# ------------------------------------------------------------------- tracks

def load_radar(start):
    points = []
    if not os.path.isdir(RADAR_DIR):
        return points
    for name in sorted(os.listdir(RADAR_DIR)):
        if not name.endswith(".csv"):
            continue
        for row in read_csv(os.path.join(RADAR_DIR, name)):
            try:
                t = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                size, lat, lon = float(row[5]), float(row[6]), float(row[7])
            except (ValueError, IndexError):
                continue
            local = t.astimezone(CENTRAL).date()
            if local < start:
                continue
            site = RADAR_SITES.get(row[1])
            if site and point_miles(site[0], site[1], lat, lon) * 1.609 > MAX_RADAR_KM:
                continue
            points.append((row[1], row[2], t, local, lat, lon, size))
    return points


def build_segments(points):
    groups = {}
    for p in points:
        groups.setdefault((p[0], p[1]), []).append(p)
    segs = []
    for pts in groups.values():
        pts.sort(key=lambda p: p[2])
        used = [False] * len(pts)
        for i in range(1, len(pts)):
            a, b = pts[i - 1], pts[i]
            if (b[2] - a[2]) <= timedelta(minutes=TRACK_GAP_MIN) and \
               point_miles(a[4], a[5], b[4], b[5]) <= TRACK_GAP_MI:
                if max(a[6], b[6]) >= MIN_SIZE:
                    segs.append((a[3], a[4], a[5], b[4], b[5], a[6], b[6]))
                used[i - 1] = used[i] = True
        for i, p in enumerate(pts):
            if not used[i] and p[6] >= MIN_SIZE:
                segs.append((p[3], p[4], p[5], p[4], p[5], p[6], p[6]))
    return segs


def load_ground(start):
    out = []
    if not os.path.isdir(GROUND_DIR):
        return out
    for name in sorted(os.listdir(GROUND_DIR)):
        if not name.endswith(".csv"):
            continue
        for row in read_csv(os.path.join(GROUND_DIR, name)):
            try:
                t = datetime.strptime(row[0], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                local = date.fromisoformat(row[1])
                size, lat, lon = float(row[2]), float(row[3]), float(row[4])
            except (ValueError, IndexError):
                continue
            if local < start:
                continue
            clock = t.astimezone(CENTRAL).strftime("%I:%M %p").lstrip("0")
            out.append((local, lat, lon, size, row[5], row[6], clock))
    return out


# -------------------------------------------------------------------- tiles

def tile_ranges(lat_min, lat_max, lon_min, lon_max, rows, cols):
    r0 = max(0, math.floor((lat_min - MARGIN - SOUTH) / TILE))
    r1 = min(rows - 1, math.floor((lat_max + MARGIN - SOUTH) / TILE))
    c0 = max(0, math.floor((lon_min - MARGIN - WEST) / TILE))
    c1 = min(cols - 1, math.floor((lon_max + MARGIN - WEST) / TILE))
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            yield r, c


def write_tiles(segs, ground):
    rows = math.ceil(round((NORTH - SOUTH) / TILE, 6))
    cols = math.ceil(round((EAST - WEST) / TILE, 6))
    tiles = {(r, c): {"d": [], "s": [], "g": []} for r in range(rows) for c in range(cols)}
    day_idx = {}

    def di(tile, d):
        key = (id(tile), d)
        if key not in day_idx:
            tile["d"].append(d.isoformat())
            day_idx[key] = len(tile["d"]) - 1
        return day_idx[key]

    for d, alat, alon, blat, blon, asz, bsz in sorted(segs):
        for rc in tile_ranges(min(alat, blat), max(alat, blat), min(alon, blon), max(alon, blon), rows, cols):
            t = tiles[rc]
            t["s"].append([round(alat, 3), round(alon, 3), round(blat, 3), round(blon, 3),
                           asz, bsz, di(t, d)])
    for d, lat, lon, size, loc, county, clock in sorted(ground):
        for rc in tile_ranges(lat, lat, lon, lon, rows, cols):
            t = tiles[rc]
            t["g"].append([round(lat, 3), round(lon, 3), size, di(t, d), loc, county, clock])
    os.makedirs(TILE_DIR, exist_ok=True)
    keep = set()
    for (r, c), t in tiles.items():
        name = f"r{r}c{c}.json"
        keep.add(name)
        with open(os.path.join(TILE_DIR, name), "w", encoding="utf-8") as f:
            json.dump(t, f, separators=(",", ":"))
    for name in os.listdir(TILE_DIR):
        if name not in keep:
            os.remove(os.path.join(TILE_DIR, name))
    return rows, cols


# ------------------------------------------------------------ storm reports

def fmt_size(s):
    return f'{s:.2f}'.rstrip("0").rstrip(".") + '"'


def nice_date(d):
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


def storm_reports(today, segs, ground):
    with open(ZIP_FILE, encoding="utf-8") as f:
        zips = json.load(f)
    since = today - timedelta(days=ALERT_DAYS)
    reports = {}
    days = sorted({s[0] for s in segs if s[0] >= since and max(s[5], s[6]) >= ALERT_SIZE} |
                  {g[0] for g in ground if g[0] >= since and g[3] >= ALERT_SIZE})
    for d in days:
        day_segs = [s for s in segs if s[0] == d and max(s[5], s[6]) >= ALERT_SIZE]
        day_ground = [g for g in ground if g[0] == d and g[3] >= ALERT_SIZE]
        towns = {}
        for z, city, county, zlat, zlon in zips:
            best = None
            for _, alat, alon, blat, blon, asz, bsz in day_segs:
                if abs(alat - zlat) > 0.2 and abs(blat - zlat) > 0.2:
                    continue
                dist, t = seg_distance(zlat, zlon, alat, alon, blat, blon)
                if dist <= TOWN_RADIUS:
                    size = asz if t < 0.5 else bsz
                    if size >= ALERT_SIZE and (best is None or size > best):
                        best = size
            for g in day_ground:
                if point_miles(zlat, zlon, g[1], g[2]) <= TOWN_RADIUS and (best is None or g[3] > best):
                    best = g[3]
            if best is not None:
                key = (city, county)
                town = towns.setdefault(key, {"city": city, "county": county, "zips": [], "size": 0})
                town["zips"].append(z)
                town.setdefault("zip_sizes", {})[z] = best
                town["size"] = max(town["size"], best)
        if not towns and not day_ground:
            continue
        ranked = sorted(towns.values(), key=lambda t: (-t["size"], t["city"]))
        reports[d] = {"towns": ranked, "ground": sorted(day_ground, key=lambda g: -g[3]),
                      "max": max([t["size"] for t in ranked] + [g[3] for g in day_ground])}
    return reports


def report_text(d, rep):
    names = [t["city"] for t in rep["towns"]]
    lead = ", ".join(names[:3]) + (f" (+{len(names) - 3} more)" if len(names) > 3 else "")
    title = f"Hail report {d.strftime('%a %b')} {d.day}: up to {fmt_size(rep['max'])}"
    if lead:
        title += f" near {lead}"
    lines = [f"## Hail on {nice_date(d)}", ""]
    if rep["towns"]:
        lines += [f"Towns in your service area with hail {fmt_size(ALERT_SIZE)} or larger within "
                  f"{TOWN_RADIUS:g} miles of town center:", "",
                  "| Town | County | ZIP codes | Largest hail |", "|---|---|---|---|"]
        for t in rep["towns"][:80]:
            z = sorted(t["zips"])
            zlist = ", ".join(z[:6]) + (f" and {len(z) - 6} more" if len(z) > 6 else "")
            lines.append(f"| {t['city']} | {t['county']} | {zlist} | {fmt_size(t['size'])} |")
        lines.append("")
        all_zips = sorted({z for t in rep["towns"] for z in t["zips"]})
        lines += ["**Every ZIP code hit** (copy this line into the KOG CRM: Send, then Hail hit):", "",
                  "```", ", ".join(all_zips), "```", ""]
    if rep["ground"]:
        lines += ["**Hail reported on the ground** (National Weather Service storm reports):", ""]
        for g in rep["ground"][:40]:
            lines.append(f"- {fmt_size(g[3])} at {g[4]} ({g[5]} County), {g[6]}")
        lines.append("")
    lines += ["Radar sizes are estimates from NOAA weather radar. They show where to look, not "
              "what happened to any one roof.", "",
              f"Check any address: {SITE}/hail-check.html", ""]
    town = rep["towns"][0]["city"] if rep["towns"] else (rep["ground"][0][4] if rep["ground"] else "your area")
    lines += ["### Alert email for hail-alert sign-ups in these towns", "",
              "Copy this, change [Name], and send it from bobby@kogroofs.com to each sign-up whose "
              "address is in one of the towns above. Put their addresses in BCC, never in To.", "",
              "```",
              f"Subject: Hail was detected near your home on {d.strftime('%A, %B')} {d.day}",
              "",
              "Hi [Name],",
              "",
              f"NOAA weather radar picked up hail up to {fmt_size(rep['max'])} near {town} on "
              f"{d.strftime('%A, %B')} {d.day}. Hail that size can bruise shingles without "
              "causing a leak right away.",
              "",
              "If you'd like, we'll inspect your roof and give you a written report with photos, "
              "even if the answer is that your roof is fine.",
              "",
              f"Call or text {PHONE}, or reply to this email.",
              "",
              "Bobby Roach",
              "KOG Roofing",
              "[mailing address]",
              "",
              "You're getting this because you signed up for hail alerts at kogroofs.com. "
              "Reply STOP and we'll take you off the list.",
              "```"]
    return title, "\n".join(lines)


def github(method, path, body=None):
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}", method=method,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": USER_AGENT,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def write_recent(today, reports):
    """Small file the site's storm banner reads: storms from the last ALERT_DAYS days."""
    storms = []
    for d, rep in sorted(reports.items(), reverse=True):
        towns = [t["city"] for t in rep["towns"]]
        if not towns:  # only ground reports: "2 W Granbury" -> "Granbury"
            towns = [re.sub(r"^\d+(\.\d+)?\s+[NSEW]{1,3}\s+", "", g[4]) for g in rep["ground"]]
        towns = list(dict.fromkeys(t for t in towns if t))
        # every ZIP code with hail 1 inch or larger, for the KOG CRM's "Hail hit" screen
        zips = {}
        for t in rep["towns"]:
            zips.update(t.get("zip_sizes", {}))
        storms.append({"date": d.isoformat(), "max": rep["max"], "towns": towns[:4],
                       "more": max(0, len(towns) - 4), "zips": dict(sorted(zips.items()))})
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "made": today.isoformat(), "storms": storms}, f, indent=1)


def post_reports(today, reports):
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    live = bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY"))
    for d, rep in sorted(reports.items()):
        key = d.isoformat()
        fp = json.dumps([[t["city"], t["size"]] for t in rep["towns"]] + [len(rep["ground"])])
        prev = state.get(key)
        if prev and prev.get("fp") == fp:
            continue
        title, body = report_text(d, rep)
        if not live:
            log("\n=== STORM REPORT (dry run) ===\n" + title + "\n\n" + body)
            continue
        try:
            if prev and prev.get("issue"):
                github("PATCH", f"/issues/{prev['issue']}", {"title": title})
                github("POST", f"/issues/{prev['issue']}/comments",
                       {"body": "**Updated with new radar or ground reports:**\n\n" + body})
                num = prev["issue"]
            else:
                num = github("POST", "/issues", {"title": title, "body": body})["number"]
            state[key] = {"issue": num, "fp": fp}
            log(f"storm report posted for {key} (issue #{num})")
        except Exception as e:
            warn(f"could not post storm report for {key} ({e})")
    cutoff = (today - timedelta(days=60)).isoformat()
    state = {k: v for k, v in state.items() if k >= cutoff}
    if live:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, sort_keys=True)


# --------------------------------------------------------------------- main

def main():
    today = datetime.now(CENTRAL).date()
    if os.environ.get("HAIL_TODAY"):  # local testing only
        today = date.fromisoformat(os.environ["HAIL_TODAY"])
    start = date(today.year - YEARS_BACK, 1, 1)
    os.makedirs(DATA, exist_ok=True)
    first_run = not os.path.isdir(RADAR_DIR) or not os.listdir(RADAR_DIR)

    fetched = update_radar(today)
    got_ground = update_ground(today)
    points = load_radar(start)
    segs = build_segments(points)
    ground = load_ground(start)
    rows, cols = write_tiles(segs, ground)
    log(f"{len(points)} radar detections -> {len(segs)} track pieces; {len(ground)} ground reports")

    latest = max([s[0] for s in segs] + [g[0] for g in ground], default=None)
    meta = {
        "v": 1,
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "start": start.isoformat(),
        "latest_hail": latest.isoformat() if latest else None,
        "bbox": [WEST, SOUTH, EAST, NORTH], "tile": TILE, "rows": rows, "cols": cols,
        "min_size": MIN_SIZE, "track_pieces": len(segs), "ground_reports": len(ground),
        "warnings": warnings[:20],
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)

    reports = storm_reports(today, segs, ground)
    write_recent(today, reports)
    post_reports(today, reports)

    if first_run and fetched == 0:
        log("No radar data could be downloaded on the first run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

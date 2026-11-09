#!/usr/bin/env python3
"""KOG Roofing recent jobs.

Run by hand each time a job is posted (the nightly hail job never runs it).
The steps, and the rules every job has to pass, are in _jobs-howto.md
(the underscore keeps GitHub Pages from publishing it).

  python3 jobs_builder.py photos JOB-ID RAW-PHOTO [RAW-PHOTO ...]
      Cleans the photos for one job: turns them upright, removes everything
      stored inside the file (GPS location, phone model, time taken), shrinks
      them to web size, and saves jobs/img/JOB-ID-1.jpg (and a -sm copy).
      The raw photos have to stay outside this folder so they are never
      published.

  python3 jobs_builder.py check
      Checks every job in jobs/data/*.json and changes nothing.

  python3 jobs_builder.py build
      Checks every job, then rebuilds:
        recent-jobs.html  the full list, between the KOG:JOBS markers
        index.html        the newest 3 jobs, between the KOG:HOMEJOBS markers
        each town page    that town's newest 3, between the KOG:TOWNJOBS markers
      While there are no jobs, recent-jobs.html stays hidden from search and
      unlinked. Once there is one, it is opened to search, added to
      sitemap.xml and llms.txt, and linked from every page's footer.
      Prints the name of each file that changed.
"""

import glob
import html
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "jobs", "data")
IMG = os.path.join(ROOT, "jobs", "img")
SITE = "https://kogroofs.com/"
PAGE = "recent-jobs.html"
NOT_TOWNS = ("commercial-roofing.html", "metal-roofing.html")
BIG, SMALL = 1600, 800
SHOWN = 3
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_RE = re.compile(r"^[A-Z][a-z'-]+(?: [A-Z]\.)?$")
SUFFIX = (r"St|Street|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Ave|Avenue|Blvd|Boulevard|"
          r"Cir|Circle|Trl|Trail|Pkwy|Parkway|Way|Pl|Place|Loop|Ter|Terrace|Cv|Cove|Hwy|Highway")
ADDRESS_RES = [
    re.compile(r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:[A-Z][A-Za-z.'-]*\s+){1,3}(?:%s)\b" % SUFFIX),
    re.compile(r"\b(?:[A-Z][a-z]+\s+){1,3}(?:St|Street|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|"
               r"Ave|Avenue|Blvd|Boulevard|Cir|Circle|Trl|Trail|Pkwy|Parkway)\b\.?"),
    re.compile(r"\b7[5-9]\d{3}(?:-\d{4})?\b"),                  # Texas ZIP code
    re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),       # phone number
    re.compile(r"@"),                                           # email
]
KOG_PHONE = re.compile(r"\(?817\)?[-.\s]550[-.\s]2339")
VIDEO_RE = re.compile(r"^https://(?:www\.youtube\.com/|youtu\.be/|www\.facebook\.com/)")

JOB_CSS = """/* KOG jobs */
.job-cards{list-style:none;padding:0!important;margin:18px 0 0;display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.job-cards li{margin:0}
.job-card-link{display:block;height:100%;text-decoration:none;color:var(--ink);background:var(--white);border:1px solid var(--line);border-bottom:5px solid var(--yellow)}
.job-card-link:hover .job-card-title{text-decoration:underline}
.job-card-link img{display:block;width:100%;height:auto;aspect-ratio:4/3;object-fit:cover}
.job-card-title{display:block;padding:12px 14px 0;font-weight:800;font-stretch:110%;color:var(--navy);font-size:1.1rem;line-height:1.3}
.job-card-meta{display:block;padding:2px 14px 14px;color:var(--steel);font-size:.95rem}
.job-more{margin-top:22px}
.job{border-top:6px solid var(--yellow);margin-top:44px;padding-top:6px}
.article .job h2{margin-top:.5em}
.job-meta{color:var(--steel);margin:-.4em 0 1em}
.job-photos{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));align-items:start;margin:0 0 1.2em}
.job-photos figure{margin:0}
.job-photos img{display:block;width:100%;height:auto;border:1px solid var(--line)}
.job-photos figcaption{font-size:.93rem;color:var(--steel);margin-top:6px;line-height:1.4}
.job-quote{margin:1.2em 0;padding:14px 20px;background:var(--wash);border-left:6px solid var(--navy)}
.job-quote p{margin:0}
.job-quote footer{margin-top:6px;font-weight:700;color:var(--navy)}
.job-towns{margin:26px 0 0}
/* end KOG jobs */
"""
FOOT_LINK = '<a href="recent-jobs.html">Recent jobs</a>'
LLMS_LINE = ("- [Recent KOG Jobs](https://kogroofs.com/recent-jobs.html): Recent roofing jobs "
             "across Dallas-Fort Worth with photos from each roof: what KOG found and what it did. "
             "Posted with each homeowner's OK. Towns only, never addresses.")


def e(s):
    return html.escape(str(s), quote=True)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_if_changed(path, old, new, changed):
    if new != old:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        changed.append(os.path.relpath(path, ROOT))


def town_pages():
    """{'granbury': ('Granbury', 'granbury-roofing.html'), ...}"""
    towns = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "*-roofing.html"))):
        page = os.path.basename(path)
        if page in NOT_TOWNS:
            continue
        name = " ".join(w.capitalize() for w in page[:-len("-roofing.html")].split("-"))
        towns[name.lower()] = (name, page)
    return towns


# ---------------------------------------------------------------- photos

def metadata_left(path):
    """Return a list of what metadata is still in a saved photo (should be empty)."""
    from PIL import Image
    found = []
    with Image.open(path) as im:
        if len(im.getexif()):
            found.append("EXIF")
        for key in ("exif", "xmp", "XML:com.adobe.xmp", "comment"):
            if im.info.get(key):
                found.append(key)
    raw = open(path, "rb").read()
    if b"Exif\x00\x00" in raw:
        found.append("EXIF block")
    if b"ns.adobe.com/xap" in raw or b"<x:xmpmeta" in raw:
        found.append("XMP block")
    return found


def cmd_photos(job_id, raws):
    if not ID_RE.match(job_id):
        sys.exit("Job ID has to look like 2026-11-14-granbury-new-roof (date, town, work).")
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        if any(r.lower().endswith((".heic", ".heif")) for r in raws):
            sys.exit("iPhone HEIC photos need: pip install pillow-heif --break-system-packages")
    os.makedirs(IMG, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(IMG, "%s-%d.jpg" % (job_id, n))):
        n += 1
    for raw in raws:
        src = os.path.realpath(raw)
        if src == ROOT or src.startswith(ROOT + os.sep):
            sys.exit("%s is inside the site folder. Keep raw photos outside it so they never get published." % raw)
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            icc = im.info.get("icc_profile")
            im = im.convert("RGB")
            pixels = Image.new("RGB", im.size)   # a fresh image carries nothing but pixels
            pixels.paste(im)
        shown = None
        for size, tag in ((BIG, ""), (SMALL, "-sm")):
            out = os.path.join(IMG, "%s-%d%s.jpg" % (job_id, n, tag))
            copy = pixels.copy()
            copy.thumbnail((size, size), Image.LANCZOS)
            kw = {"quality": 82, "optimize": True, "progressive": True}
            if icc:
                kw["icc_profile"] = icc          # color only; holds no location
            copy.save(out, "JPEG", **kw)
            left = metadata_left(out)
            if left:
                os.remove(out)
                sys.exit("Could not strip %s from %s. Nothing saved for it." % (", ".join(left), raw))
            shown = shown or copy.size
        print("jobs/img/%s-%d.jpg  from %s  (%dx%d, location and phone data removed)"
              % (job_id, n, os.path.basename(raw), shown[0], shown[1]))
        n += 1


# ---------------------------------------------------------------- checks

def scan_text(label, text, errors, where):
    for rx in ADDRESS_RES:
        clean = KOG_PHONE.sub("", text)
        m = rx.search(clean)
        if m:
            errors.append("%s: %s looks like it has an address, ZIP, phone or email in it (%r). "
                          "Towns only." % (where, label, m.group(0)))
            return


def load_jobs(towns):
    from PIL import Image
    jobs, errors, warnings = [], [], []
    for path in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        jid = os.path.basename(path)[:-5]
        where = "jobs/data/%s.json" % jid
        try:
            j = json.loads(read(path))
        except ValueError as ex:
            errors.append("%s: not valid JSON (%s)" % (where, ex))
            continue
        if not ID_RE.match(jid):
            errors.append("%s: file name has to look like 2026-11-14-granbury-new-roof.json" % where)
            continue
        if j.get("photo_ok") != "in writing":
            errors.append('%s: "photo_ok" must be "in writing". No written OK from the homeowner, no post.' % where)
        try:
            d = date.fromisoformat(j.get("date", ""))
        except ValueError:
            errors.append('%s: "date" must be YYYY-MM-DD' % where)
            continue
        if d > date.today():
            errors.append("%s: date is in the future" % where)
        if not jid.startswith(d.isoformat()):
            errors.append("%s: file name should start with the job date %s" % (where, d.isoformat()))
        for key in ("town", "work", "did"):
            if not str(j.get(key, "")).strip():
                errors.append('%s: "%s" is required' % (where, key))
        town = str(j.get("town", "")).strip()
        if town and town.lower() not in towns:
            warnings.append("%s: no town page for %r, so it shows on recent-jobs.html only. "
                            "Check the spelling." % (where, town))
        name = j.get("name", "")
        if name and not NAME_RE.match(name):
            errors.append('%s: "name" is first name only, or first name and last initial ("Linda" or "Linda R.")' % where)
        if j.get("quote") and j.get("quote_ok") != "in writing":
            errors.append('%s: a quote needs "quote_ok": "in writing" (the homeowner\'s own words, '
                          'OK\'d in writing). Never write a quote for them.' % where)
        if j.get("video") and not VIDEO_RE.match(j["video"]):
            errors.append('%s: "video" must be a YouTube or Facebook link' % where)
        for key in ("town", "work", "found", "did", "roof", "quote", "name"):
            if j.get(key):
                scan_text(key, str(j[key]), errors, where)
        photos = j.get("photos") or []
        if not photos:
            errors.append("%s: needs at least one photo" % where)
        for i, p in enumerate(photos, 1):
            f = p.get("file", "")
            if not re.match(r"^%s-\d+\.jpg$" % re.escape(jid), f):
                errors.append("%s: photo %d file must be %s-N.jpg from the photos step" % (where, i, jid))
                continue
            big = os.path.join(IMG, f)
            small = big[:-4] + "-sm.jpg"
            if not (os.path.exists(big) and os.path.exists(small)):
                errors.append("%s: jobs/img/%s or its -sm copy is missing. Run the photos step." % (where, f))
                continue
            for img in (big, small):
                left = metadata_left(img)
                if left:
                    errors.append("%s: %s still has %s in it. Re-run the photos step."
                                  % (where, os.path.basename(img), ", ".join(left)))
            if not str(p.get("caption", "")).strip():
                errors.append("%s: photo %d needs a caption" % (where, i))
            else:
                scan_text("photo %d caption" % i, p["caption"], errors, where)
            with Image.open(big) as im:
                p["_big"] = im.size
            with Image.open(small) as im:
                p["_small"] = im.size
        cover = j.get("cover", len(photos))
        if photos and not (isinstance(cover, int) and 1 <= cover <= len(photos)):
            errors.append('%s: "cover" must be a photo number from 1 to %d' % (where, len(photos)))
        j["_id"], j["_date"], j["_cover"] = jid, d, cover if isinstance(cover, int) else 1
        jobs.append(j)
    jobs.sort(key=lambda j: (j["_date"], j["_id"]), reverse=True)
    return jobs, errors, warnings


# ---------------------------------------------------------------- html

def month(d):
    return "%s %d" % (MONTHS[d.month - 1], d.year)


def title(j):
    return "%s in %s" % (j["work"].strip(), j["town"].strip())


def img(p, sizes):
    base = p["file"][:-4]
    (bw, bh), (sw, sh) = p["_big"], p["_small"]
    return ('<img src="jobs/img/%s-sm.jpg" srcset="jobs/img/%s-sm.jpg %dw, jobs/img/%s.jpg %dw" '
            'sizes="%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async">'
            % (base, base, sw, base, bw, sizes, sw, sh, e(p["caption"])))


def cards(jobs):
    out = ['<ul class="job-cards">']
    for j in jobs[:SHOWN]:
        p = j["photos"][j["_cover"] - 1]
        out.append('<li><a class="job-card-link" href="%s#job-%s">%s'
                   '<span class="job-card-title">%s</span><span class="job-card-meta">%s</span></a></li>'
                   % (PAGE, j["_id"], img(p, "(max-width:759px) 100vw, 340px"), e(title(j)), month(j["_date"])))
    out.append("</ul>")
    return "\n".join(out)


def full_job(j, towns):
    town = j["town"].strip()
    out = ['<section class="job" id="job-%s" aria-labelledby="job-%s-title">' % (j["_id"], j["_id"]),
           '<h2 id="job-%s-title">%s</h2>' % (j["_id"], e(title(j))),
           '<p class="job-meta">%s</p>' % month(j["_date"]),
           '<div class="job-photos">']
    for p in j["photos"]:
        out.append('<figure><a href="jobs/img/%s">%s</a><figcaption>%s</figcaption></figure>'
                   % (p["file"], img(p, "(max-width:759px) 100vw, 230px"), e(p["caption"])))
    out.append("</div>")
    if j.get("found"):
        out.append("<p><strong>What we found.</strong> %s</p>" % e(j["found"]))
    out.append("<p><strong>What we did.</strong> %s</p>" % e(j["did"]))
    if j.get("roof"):
        out.append("<p><strong>Roof.</strong> %s</p>" % e(j["roof"]))
    if j.get("quote"):
        who = "%s, %s" % (j["name"], town) if j.get("name") else "Homeowner, %s" % town
        out.append('<blockquote class="job-quote"><p>&ldquo;%s&rdquo;</p><footer>%s</footer></blockquote>'
                   % (e(j["quote"]), e(who)))
    if j.get("video"):
        out.append('<p><a href="%s">Watch the video from this job</a></p>' % e(j["video"]))
    t = towns.get(town.lower())
    if t:
        out.append('<p><a href="%s">Roofing in %s</a></p>' % (t[1], e(t[0])))
    out.append("</section>")
    return "\n".join(out)


def jobs_block(jobs, towns):
    if not jobs:
        return "<p>The first jobs go up soon.</p>"
    out = [full_job(j, towns) for j in jobs]
    counts = {}
    for j in jobs:
        counts[j["town"].strip()] = counts.get(j["town"].strip(), 0) + 1
    links = []
    for town in sorted(counts):
        t = towns.get(town.lower())
        label = "%s (%d)" % (e(town), counts[town])
        links.append('<a href="%s">%s</a>' % (t[1], label) if t else label)
    out.append('<p class="job-towns"><strong>Towns:</strong> %s</p>' % ", ".join(links))
    return "\n".join(out)


def home_block(jobs):
    if not jobs:
        return ""
    return "\n".join([
        '<section class="section" id="recent-jobs" aria-labelledby="jobs-title">',
        '<div class="wrap">',
        '<h2 id="jobs-title">Recent KOG jobs</h2>',
        "<p>Real roofs from across Dallas-Fort Worth. Every photo is from the job, posted with the homeowner's OK.</p>",
        cards(jobs),
        '<p class="job-more"><a class="btn btn-navy" href="%s">See all recent jobs</a></p>' % PAGE,
        "</div>",
        "</section>"])


def town_block(name, jobs):
    if not jobs:
        return ""
    return "\n".join([
        "<h2>Recent KOG jobs in %s</h2>" % e(name),
        cards(jobs),
        '<p class="job-more"><a href="%s">See all recent jobs</a></p>' % PAGE])


# ---------------------------------------------------------------- pages

def put(text, marker, body, where, anchor=None):
    """Replace what sits between a page's markers. If the page has no markers
    yet, they go in just before `anchor` the first time there is something to
    show, so pages without jobs are left alone."""
    start, end = "<!-- KOG:%s:START -->" % marker, "<!-- KOG:%s:END -->" % marker
    if start not in text and end not in text and anchor:
        if not body:
            return text
        if text.count(anchor) != 1:
            sys.exit("%s: can't find one %r to put the %s markers before" % (where, anchor, marker))
        text = text.replace(anchor, start + "\n" + end + "\n\n" + anchor)
    if text.count(start) != 1 or text.count(end) != 1:
        sys.exit("%s: needs exactly one %s and one %s" % (where, start, end))
    a = text.index(start) + len(start)
    b = text.index(end)
    inner = "\n" + body + "\n" if body else "\n"
    text = text[:a] + inner + text[b:]
    return ensure_css(text) if body else text


def ensure_css(text):
    """Put the current job styles in the page's style block, or refresh them."""
    old = re.search(r"/\* KOG jobs \*/.*?/\* end KOG jobs \*/\n", text, re.S)
    if old:
        return text[:old.start()] + JOB_CSS + text[old.end():]
    i = text.index("</style>")
    return text[:i] + JOB_CSS + text[i:]


def set_lastmod(sitemap, page, day):
    loc = "<loc>%s%s</loc>" % (SITE, page)
    return re.sub(r"(%s<lastmod>)[^<]*(</lastmod>)" % re.escape(loc), r"\g<1>%s\g<2>" % day, sitemap)


def cmd_build(only_check=False):
    towns = town_pages()
    jobs, errors, warnings = load_jobs(towns)
    for w in warnings:
        print("warning:", w)
    if errors:
        for x in errors:
            print("STOP:", x)
        sys.exit(1)
    print("%d job(s) pass every check." % len(jobs))
    if only_check:
        return
    public = bool(jobs)
    today = date.today().isoformat()
    changed, touched = [], []

    # recent-jobs.html
    path = os.path.join(ROOT, PAGE)
    old = read(path)
    new = put(old, "JOBSROBOTS", "" if public else '<meta name="robots" content="noindex">', PAGE)
    new = put(new, "JOBS", jobs_block(jobs, towns), PAGE)
    new = ensure_css(new)
    write_if_changed(path, old, new, changed)
    if new != old:
        touched.append(PAGE)

    # homepage: the newest jobs go just above the reviews
    path = os.path.join(ROOT, "index.html")
    old = read(path)
    new = put(old, "HOMEJOBS", home_block(jobs), "index.html",
              anchor='<section class="section reviews" id="reviews"')
    if new != old:
        touched.append("")
    write_if_changed(path, old, new, changed)

    # town pages: that town's jobs go just above the common questions
    for key, (name, page) in towns.items():
        path = os.path.join(ROOT, page)
        old = read(path)
        mine = [j for j in jobs if j["town"].strip().lower() == key]
        new = put(old, "TOWNJOBS", town_block(name, mine), page, anchor="<h2>Common questions</h2>")
        if new != old:
            touched.append(page)
        write_if_changed(path, old, new, changed)

    # footer link on every page
    for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        old = read(path)
        if 'class="foot-links"' not in old:
            continue
        new = old
        has = FOOT_LINK in new
        if public and not has:
            new = re.sub(r'(<div class="foot-links">\s*<a href="/?about\.html">About</a>)',
                         lambda m: m.group(1) + "\n" + FOOT_LINK, new, count=1)
            if FOOT_LINK not in new:
                new = new.replace('<div class="foot-links">', '<div class="foot-links">\n' + FOOT_LINK, 1)
        elif not public and has:
            new = new.replace("\n" + FOOT_LINK, "").replace(FOOT_LINK, "")
        write_if_changed(path, old, new, changed)

    # sitemap.xml
    path = os.path.join(ROOT, "sitemap.xml")
    old = read(path)
    new = old
    entry = "  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>\n" % (SITE, PAGE, today)
    listed = "<loc>%s%s</loc>" % (SITE, PAGE) in new
    if public and not listed:
        new = new.replace("</urlset>", entry + "</urlset>")
    elif not public and listed:
        new = re.sub(r"  <url><loc>%s</loc>.*?</url>\n" % re.escape(SITE + PAGE), "", new)
    if public:
        for page in touched:
            new = set_lastmod(new, page, today)
    write_if_changed(path, old, new, changed)

    # llms.txt
    path = os.path.join(ROOT, "llms.txt")
    if os.path.exists(path):
        old = read(path)
        new = old
        if public and LLMS_LINE not in new:
            m = re.search(r"^- \[About KOG Roofing\].*$", new, re.M)
            if m:
                new = new[:m.end()] + "\n" + LLMS_LINE + new[m.end():]
            else:
                new = new.rstrip("\n") + "\n" + LLMS_LINE + "\n"
        elif not public and LLMS_LINE in new:
            new = new.replace(LLMS_LINE + "\n", "").replace(LLMS_LINE, "")
        write_if_changed(path, old, new, changed)

    for c in dict.fromkeys(changed):
        print(c)


def main():
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "photos":
        cmd_photos(args[1], args[2:])
    elif args == ["check"]:
        cmd_build(only_check=True)
    elif args == ["build"]:
        cmd_build()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

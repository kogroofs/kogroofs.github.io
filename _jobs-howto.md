# Posting a KOG job

Recent jobs go on `recent-jobs.html`, the homepage (newest 3), and that town's page (its newest 3).
The page stays hidden from search and unlinked until the first job is posted.

## What comes in after a job

1. The homeowner's written OK (a text that says YES to the photo-permission message). Log it in the CRM: Contact, "OK to post job photos?" = Yes, in writing.
2. Three photos: before, what we found, after.
3. Two lines: what we found, and what we did. Town and month. A first name only if they said it's OK.

## Rules (the builder enforces the starred ones)

- * No written OK, no post.
- * Town only. Never a street, house number, ZIP, phone or email, in the text or a caption.
- * First name only, or first name and last initial ("Linda R.").
- * Every photo is cleaned: GPS location, phone model and time taken are removed.
- Before posting, look at every photo for a house number, street sign, mailbox, license plate, face, or anything inside the home. Crop it or skip that photo.
- Only photos taken on KOG jobs. No stock photos. No AI-made or AI-edited images.
- * A quote is the homeowner's own words, OK'd in writing. Never write one for them, never pay or trade for one (FTC rule, 16 CFR Part 465).
- Show the month, not the exact day.

## Steps

Keep the raw photos outside this folder (the builder refuses raw photos inside it).

```
python3 jobs_builder.py photos 2026-11-14-granbury-new-roof ~/raw/IMG_0001.HEIC ~/raw/IMG_0002.HEIC ~/raw/IMG_0003.HEIC
```

That writes `jobs/img/2026-11-14-granbury-new-roof-1.jpg` (and `-sm`), `-2`, `-3`. iPhone HEIC photos need `pip install pillow-heif --break-system-packages`.

Then create `jobs/data/2026-11-14-granbury-new-roof.json`:

```json
{
  "date": "2026-11-14",
  "town": "Granbury",
  "work": "New roof",
  "name": "Linda",
  "photo_ok": "in writing",
  "found": "Hail bruises on the north and west slopes, and 3 sheets of rotten decking by the chimney.",
  "did": "Tore off to the deck, replaced the decking, new underlayment, drip edge and ridge vent, and architectural shingles.",
  "roof": "Architectural shingles in Charcoal",
  "photos": [
    {"file": "2026-11-14-granbury-new-roof-1.jpg", "caption": "Before: hail bruises on the north slope"},
    {"file": "2026-11-14-granbury-new-roof-2.jpg", "caption": "Rotten decking we found by the chimney"},
    {"file": "2026-11-14-granbury-new-roof-3.jpg", "caption": "After: the finished roof"}
  ]
}
```

Optional: `"cover": 3` (the photo shown on cards; the last photo by default), `"quote"` with `"quote_ok": "in writing"`, `"video"` (a YouTube or Facebook link). `"name"`, `"found"` and `"roof"` can be left out.

`"town"` should match a town page (granbury-roofing.html is "Granbury", north-richland-hills-roofing.html is "North Richland Hills"). Other towns still post, on recent-jobs.html only.

```
python3 jobs_builder.py check
python3 jobs_builder.py build
```

Review the pages, then commit and push. The push tells Bing about the changed pages.

To take a job down, delete its JSON file and its photos in `jobs/img/`, run `build`, and push.

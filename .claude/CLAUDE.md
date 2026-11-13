# kogroofs.com: rules for every change

This is KOG Roofing's website (GitHub Pages, custom domain kogroofs.com). The owner is Bobby (William Roach). He's been locked out of Google once before and won't risk it again. Every change has to keep the site clean with Google.

GitHub Pages doesn't publish dot-folders, so this file and `site_check.py` stay private.

## Before every publish

Run `python3 .claude/site_check.py`. It has to say `0 problem(s)` before you push. If it fails, fix the problem. Don't loosen the check to get it to pass.

## Google rules

1. **Dates only move for real changes.** A page's `dateModified`, its visible "Updated" line, and its sitemap `lastmod` change only when the page's main content changes in a meaningful way. Menu, footer, contact-bar, link and other sitewide template edits don't count. All three dates have to agree. The nightly hail job keeps its own dates honest: `hail_pages.py` only moves the hail report's date when new hail is added, and `town_hail.py` only moves a town page's date when its numbers change.
2. **Never change or delete a page's address.** Rankings and outside links are tied to the URL. If a page truly has to go, ask Bobby first. Then point its links somewhere useful and remove it from `sitemap.xml` and `llms.txt` in the same change.
3. **Schema has to match the page.** FAQ answers in JSON-LD must say exactly what the visible answer says. Never put review or rating schema (`aggregateRating`, `review`) on KOG's own business. Never post made-up reviews or quotes.
4. **Every indexable page** gets a unique title, a unique meta description, exactly one H1, a canonical of `https://kogroofs.com/<page>` (the home page is `https://kogroofs.com/`), and a listing in `sitemap.xml` and `llms.txt`. Pages marked noindex (like `recent-jobs.html` until the first job) stay out of both.
5. **No look-alike pages.** Every town page needs its own real local facts: hail record, permit office, neighborhoods, local roof ages. Never clone a page and swap the town name. Don't mass-produce thin pages to chase keywords. One strong page per real homeowner question.
6. **No hidden text.** Nothing written for Google that visitors can't see.
7. **Only true claims.** Don't say KOG is insured, bonded, licensed, Google Guaranteed, or GAF/Owens Corning/FORTIFIED/RCAT certified until Bobby confirms it's true now. Check Bobby's facts against real sources before they go on the site. Cite sources at the bottom of guide pages.
8. **Business info matches the Google profile exactly:** KOG Roofing, (817) 550-2339, office@kogroofs.com, https://kogroofs.com, Granbury, TX. No street address on the site. KOG's Google profile is a service-area business with the address hidden.
9. **One big change at a time.** Don't stack a redesign, URL changes and new templates in one push.

## Voice

Write "KOG" or "we," not Bobby's name, except on the About page. Never say KOG is "back" or was ever gone. Keep his ministry (books, sermons) off this site.

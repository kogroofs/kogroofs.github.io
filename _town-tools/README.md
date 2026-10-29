# Town batch 3, second half (go live Nov 12, 2026)

This branch holds Crowley, Kennedale, Hurst and Haslet, built Oct 29, 2026
and held back because Google had crawled but not indexed 4 town pages.

On go-live day:
1. Check Search Console > Pages with Bobby first.
2. `git checkout town-batch-3b && git rebase origin/main`
3. Rebuild the pages with fresh hail numbers (from the repo folder):
   `LIVE="Benbrook,Euless,Bedford,Haltom City,Crowley,Kennedale,Hurst,Haslet" python3 _town-tools/gen_towns.py . Crowley Kennedale Hurst Haslet`
   (gen_towns.py expects the repo at /home/claude/kogroofs.github.io)
4. `python3 _town-tools/link_towns.py Crowley Kennedale Hurst Haslet`
5. Delete `_town-tools/` from what goes to main, check pages at phone width, merge to main, push.

Facts on these pages came from: Wikipedia (Crowley, Kennedale, Haslet),
the City of Hurst's own pages, Kennedale ISD, and a City of Crowley permits
document title (817-297-2201 x 3000, permits@ci.crowley.tx.us). The Crowley,
Kennedale and Haslet city websites blocked our reader, so those permit
sections stay general; try again before go-live.

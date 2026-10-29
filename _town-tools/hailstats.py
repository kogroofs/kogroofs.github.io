import sys, json, math
sys.path.insert(0, '/home/claude/kogroofs.github.io')
import hail_builder as hb
from datetime import date, datetime, timedelta
from collections import Counter
today = datetime.now(hb.CENTRAL).date()
start = date(today.year - hb.YEARS_BACK, 1, 1)
zips = json.load(open(hb.ZIP_FILE))
pts = hb.load_radar(start)
# segments with time of first point
groups = {}
for p in pts: groups.setdefault((p[0], p[1]), []).append(p)
segs = []
for g in groups.values():
    g.sort(key=lambda p: p[2]); used=[False]*len(g)
    for i in range(1,len(g)):
        a,b=g[i-1],g[i]
        if (b[2]-a[2])<=timedelta(minutes=hb.TRACK_GAP_MIN) and hb.point_miles(a[4],a[5],b[4],b[5])<=hb.TRACK_GAP_MI:
            if max(a[6],b[6])>=hb.MIN_SIZE: segs.append((a[3],a[4],a[5],b[4],b[5],a[6],b[6],a[2],b[2]))
            used[i-1]=used[i]=True
    for i,p in enumerate(g):
        if not used[i] and p[6]>=hb.MIN_SIZE: segs.append((p[3],p[4],p[5],p[4],p[5],p[6],p[6],p[2],p[2]))
CENT = {"Benbrook": [(32.673, -97.461)]}
towns = ["Benbrook","Crowley","Kennedale","Euless","Bedford","Hurst","Haltom City","Haslet"]
out = {}
for c in towns:
    P = CENT.get(c) or [(z[3], z[4]) for z in zips if z[1]==c]
    days = {}; first1 = {}
    for s in segs:
        d,alat,alon,blat,blon,asz,bsz,ta,tb = s
        for plat,plon in P:
            if abs(alat-plat)>0.2 and abs(blat-plat)>0.2: continue
            dist,t = hb.seg_distance(plat,plon,alat,alon,blat,blon)
            if dist<=hb.TOWN_RADIUS:
                size = asz if t<0.5 else bsz
                days[d]=max(days.get(d,0),size)
                if size>=1:
                    tt = (ta if t<0.5 else tb).astimezone(hb.CENTRAL)
                    if d not in first1 or tt<first1[d]: first1[d]=tt
    one={d:s for d,s in days.items() if s>=1}
    months=Counter(d.month for d in one)
    def bucket(t):
        h=t.hour
        if 5<=h<12: return 'morning'
        if 12<=h<17: return 'afternoon'
        if 17<=h<22: return 'evening'
        return 'overnight'
    times=Counter(bucket(t) for t in first1.values())
    top=sorted(days.items(), key=lambda kv:(-kv[1],-kv[0].toordinal()))[:4]
    print(c, 'days',len(days),'1in',len(one),'2in',sum(1 for s in days.values() if s>=2))
    print('  top', [(str(d),s) for d,s in top])
    print('  months', sorted(months.items()))
    print('  times', dict(times))
    print('  years', sorted(Counter(d.year for d in one).items()), 'last1', max(one) if one else None)
    out[c]=P
# centers for distance
allc = {}
for z in zips: allc.setdefault(z[1],[]).append((z[3],z[4]))
json.dump({k:v for k,v in allc.items()}, open('/tmp/claude-0/-home-claude/280f93f4-2720-59e5-a85a-3780c278d701/scratchpad/centers.json','w'))

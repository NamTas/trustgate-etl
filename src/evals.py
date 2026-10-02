import json, pathlib
from .validate import validate
from .inject import KINDS, apply
from collections import Counter
D = pathlib.Path(__file__).resolve().parents[1] / "data"
import os
GTS = [D/"ground_truth_real.json"] + ([pathlib.Path(os.environ["DW_GT"])] if os.environ.get("DW_GT") else [])
def selftest(rows):
    """Inject each error kind into the extracted data of clean real documents; check the validator flags it."""
    tot = caught = 0; by = {}
    for r in rows:
        f = json.loads(r["extracted"])
        if "Extraction Failed" in r["issues"] or validate(f, False)[0]: continue
        for k, ok in KINDS.items():
            if ok(f):
                hit = bool(validate(apply(f, k), False)[0]); tot += 1; caught += hit; b = by.setdefault(k, [0, 0]); b[0] += hit; b[1] += 1
    return tot, caught, by
def compute(c):
    rows = [dict(r) for r in c.execute("SELECT * FROM documents")]
    gt = {}
    for g_ in GTS:
        if g_.exists(): gt.update(json.loads(g_.read_text()))
    fa = fn = em = nc = inj = caught = di = dc = 0
    for r in rows:
        g = gt.get(r["filename"]); flagged = r["issues"] != "[]"
        if not g: continue
        if g["injected"]:
            inj += 1; caught += flagged
            if "duplicate" in g["injected"]: di += 1; dc += flagged
        else:
            t, e = g["truth"], json.loads(r["extracted"]); ks = [k for k in ("id","party","date","total") if t.get(k) is not None]
            if not ks: continue
            ok = [e.get(k) == t[k] for k in ks]; fa += sum(ok); fn += len(ok); em += all(ok); nc += 1
    n = len(rows) or 1; pct = lambda a, b: round(100*a/b, 1) if b else None
    st = Counter(r["status"] for r in rows)
    hv = hn = 0  # model output vs what a human reviewer finally approved
    for r in rows:
        if r.get('original') and r['review'] == 'approved':
            o, e2 = json.loads(r['original']), json.loads(r['extracted'])
            for k in ('id', 'party', 'date', 'total'):
                if e2.get(k) is not None: hn += 1; hv += o.get(k) == e2.get(k)
    sf = selftest(rows)
    return dict(extraction_ok=pct(sum('Extraction Failed' not in r['issues'] for r in rows), len(rows)), pass_rate=pct(st['passed'], len(rows)),
        st_total=sf[0], st_caught=sf[1], st_rate=pct(sf[1], sf[0]), st_by=sf[2], hv_accuracy=pct(hv, hn), hv_n=hn, total=len(rows), passed=st["passed"], quarantined=st["quarantined"], review=st["review"],
        pending=sum(r["review"] == "pending" for r in rows), duplicates=sum('Duplicate' in r["issues"] for r in rows),
        by_issue=dict(Counter(i for r in rows for i in json.loads(r["issues"]))),
        field_accuracy=pct(fa, fn), exact_match=pct(em, nc), catch_rate=pct(caught, inj), injected=inj, caught=caught,
        dup_detection=pct(dc, di), review_rate=pct(sum(r["review"] != "none" for r in rows), n),
        avg_ms=round(sum(r["proc_ms"] for r in rows)/n, 1), avg_conf=round(100*sum(r["confidence"] for r in rows)/n, 1))

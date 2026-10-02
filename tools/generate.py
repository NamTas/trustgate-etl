"""Synthetic invoices + lab reports with deliberately injected errors (for validation-catch-rate)."""
import random, json, pathlib, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parents[1]
VEND = ["Acme Corp","Globex","Initech","Umbra Ltd","Hooli","Stark Supply","Wayne Parts","Soylent Co"]
TESTS = [("Glucose","mg/dL",70,99),("Hemoglobin","g/dL",12,16),("Cholesterol","mg/dL",125,200),("Creatinine","mg/dL",.6,1.3)]

def render(t, bad):
    L = [f"{'INVOICE' if t['type']=='Invoice' else 'LAB REPORT'} {t['id']}"]
    if bad != "missing_field": L.append(f"{'Vendor' if t['type']=='Invoice' else 'Patient'}: {t['party']}")
    L.append(f"Date: {'2026-13-40' if bad=='invalid_date' else t['date']}")
    if t["type"] == "Invoice":
        L.append(f"Currency: {'XXX' if bad=='invalid_currency' else t['currency']}")
        L += [f"Item: {n} | {q} | {p:.2f}" for n,q,p in t["items"]]
        tot = t["total"] + 45 if bad == "total_mismatch" else t["total"]
        L += [f"Subtotal: {t['subtotal']:.2f}", f"Tax: {t['tax']:.2f}", f"Total: {tot:.2f}"]
    else:
        L += [f"Test: {n} | {v} | {u}" for n,v,u in t["items"]]
    return "\n".join(L) + "\n"

def make(n=120, seed=7):
    r = random.Random(seed); out = []
    for i in range(1, n+1):
        d = (dt.date(2026,9,1) + dt.timedelta(days=r.randint(0,29))).isoformat()
        if r.random() < .7:
            it = [(r.choice(["Widget","Cable","Sensor","License","Support"]), r.randint(1,9), round(r.uniform(5,300),2)) for _ in range(r.randint(1,4))]
            sub = round(sum(q*p for _,q,p in it),2); tax = round(sub*.1,2)
            t = dict(type="Invoice", id=f"INV-{i:04d}", party=r.choice(VEND), date=d, currency="USD", items=it, subtotal=sub, tax=tax, total=round(sub+tax,2))
            kinds = ["total_mismatch","invalid_date","missing_field","invalid_currency"]; ext = ".pdf" if r.random()<.6 else ".jpg"
        else:
            t = dict(type="Lab Report", id=f"LAB-{i:04d}", party=f"P-{r.randint(100,999)}", date=d, total=None,
                     items=[(a, round(r.uniform(lo,hi),1), u) for a,u,lo,hi in r.sample(TESTS, 3)])
            kinds = ["invalid_date","missing_field"]; ext = ".pdf"
        bad = r.choice(kinds) if r.random() < .22 else None
        out.append((t["id"]+ext, render(t, bad), t, [bad] if bad else []))
        if r.random() < .05:
            out.append((t["id"]+"_copy"+ext, out[-1][1], t, ["duplicate"]))
    return out

if __name__ == "__main__":
    raw = ROOT/"data/synthetic/docs"; gt = {}; raw.mkdir(parents=True, exist_ok=True)
    for f in raw.glob("*.txt"): f.unlink()
    for name, text, t, inj in make():
        (raw/(name+".txt")).write_text(text); gt[name] = {"truth": t, "injected": inj}
    (ROOT/"data/synthetic/ground_truth.json").write_text(json.dumps(gt, indent=1)); print(len(gt), "documents generated")

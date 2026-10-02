import json, time, hashlib, random, datetime as dt
from .inject import applicable, apply
from .extract import extract, _n
from .validate import validate
VERSIONS = ("v1.3", "p7", "2.1")  # model, prompt, pipeline
def load(c, doc_id, f):
    c.execute("INSERT INTO warehouse_records VALUES(?,?,?,?,?,?,?)", (doc_id, f.get("id"), f.get("party"), f.get("date"), f.get("currency"), f.get("total"), dt.datetime.now().isoformat(" ", "seconds")))
def process(c, name, data, inject=False):
    t0 = time.perf_counter(); h = hashlib.sha256(data + (b"|inj" if inject else b"")).hexdigest()[:16]
    try: f, conf, model = extract(data); err = None
    except Exception as e: f, conf, model, err = {"type": "Invoice", "items": []}, 0.0, "none", str(e)[:120]
    kind = random.choice(applicable(f)) if inject and not err else None
    if kind: f = apply(f, kind)
    dup = c.execute("SELECT 1 FROM documents WHERE file_hash=?", (h,)).fetchone() is not None
    issues, exp = validate(f, dup)
    if err: issues, exp = ["Extraction Failed"], {"error": err}
    if kind: exp = {**exp, "injected": kind}
    status = "quarantined" if issues else ("review" if conf < .8 else "passed")
    val = ", ".join(issues) or ("Low confidence" if status == "review" else "Passed")
    cur = c.execute("INSERT INTO documents(filename,doctype,status,confidence,validation,issues,model,model_version,prompt_version,pipeline_version,file_hash,processed_at,proc_ms,extracted,expected,review) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (name, f["type"], status, conf, val, json.dumps(issues), model, *VERSIONS, h, dt.datetime.now().isoformat(" ", "seconds"),
         round((time.perf_counter()-t0)*1000, 1), json.dumps(f), json.dumps(exp), "none" if status == "passed" else "pending"))
    if status == "passed": load(c, cur.lastrowid, f)
    c.commit(); return cur.lastrowid
def review(c, doc_id, action, fields=None):
    r = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not r: return {"ok": False, "error": "Document not found"}
    if r["review"] == "approved": return {"ok": True}
    if action != "approve":
        c.execute("UPDATE documents SET review='rejected' WHERE id=?", (doc_id,)); c.commit(); return {"ok": True}
    f = json.loads(r["extracted"]); f.setdefault("type", "Invoice"); f.setdefault("items", [])
    for k, v in (fields or {}).items():  # reviewer corrections
        v = None if v is None or str(v).strip() == "" else str(v).strip()
        f[k] = _n(v) if k in ("subtotal", "tax", "total") else v
    issues, _ = validate(f, False)  # the gate applies to humans too
    if issues: return {"ok": False, "error": "Still invalid: " + ", ".join(issues) + ". Correct the values above, then approve."}
    c.execute("UPDATE documents SET review='approved', status='passed', issues='[]', validation='Passed (reviewed)', expected='{}', original=COALESCE(original, ?), extracted=? WHERE id=?", (r["extracted"], json.dumps(f), doc_id))
    load(c, doc_id, f); c.commit(); return {"ok": True}

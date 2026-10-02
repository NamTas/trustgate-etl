"""Extraction layer. Parses OCR text into structured fields + confidence.
Swap internals for Gemini/OpenAI calls (same return shape) - validation stays identical."""
import re, random, hashlib
def _g(p, text):
    m = re.search(p, text, re.M); return m.group(1).strip() if m else None
def _n(v):
    try: return float(re.sub(r"[^\d.\-]", "", str(v)))
    except (TypeError, ValueError): return None
def _regex(text):
    rnd = random.Random(int(hashlib.md5(text.encode()).hexdigest(), 16))
    inv = text.startswith("INVOICE")
    f = dict(type="Invoice" if inv else "Lab Report", id=_g(r"^(?:INVOICE|LAB REPORT) (\S+)", text),
             party=_g(r"^(?:Vendor|Patient): (.+)", text), date=_g(r"^Date: (.+)", text))
    if inv:
        f.update(currency=_g(r"^Currency: (.+)", text), subtotal=_n(_g(r"^Subtotal: (.+)", text)), tax=_n(_g(r"^Tax: (.+)", text)),
                 total=_n(_g(r"^Total: (.+)", text)),
                 items=[(a, int(b), float(c)) for a,b,c in re.findall(r"^Item: (.+) \| (\d+) \| ([\d.]+)$", text, re.M)])
    else:
        f["items"] = [(a, float(b), c) for a,b,c in re.findall(r"^Test: (.+) \| ([\d.]+) \| (.+)$", text, re.M)]
    conf = 0.98 - 0.07 * sum(f.get(k) in (None, "") for k in ("id","party","date"))
    if rnd.random() < .09 and f["party"]:
        i = rnd.randrange(len(f["party"])); f["party"] = f["party"][:i] + "#" + f["party"][i+1:]; conf -= rnd.uniform(.2,.4)
    conf = round(max(.3, conf - rnd.uniform(0, .05)), 2)
    return f, conf, ("Gemini-v1" if inv else "OCR-v2")

# ---------- Real documents: PDF / JPG / PNG via Gemini or OpenAI (keys in .env) ----------
import os, json, base64, io, time, pathlib, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[1]
PROMPT = ("Extract this document as JSON only: {type:'Invoice'|'Lab Report', id, party (vendor or patient), date (YYYY-MM-DD), "
          "currency (ISO code), subtotal, tax, total (numbers), items:[{name,qty,price}]}. Use null for anything not visible. "
          "Copy printed values exactly. Never guess, correct or compute values.")
def _env():
    for n in (".env", ".env.example"):  # .env wins; .env.example is read too in case the key was typed there
        f = ROOT / n
        if not f.exists(): continue
        for l in f.read_text(encoding="utf-8-sig").splitlines():
            l = l.strip()
            if l.startswith("export "): l = l[7:]
            if "=" in l and not l.startswith("#"):
                k, v = l.split("=", 1); k = k.strip(); v = v.split(" #")[0].strip().strip("'\"")
                if v and not os.environ.get(k): os.environ[k] = v
    if os.environ.get("MODEL_NAME") and not os.environ.get("GEMINI_MODEL"): os.environ["GEMINI_MODEL"] = os.environ["MODEL_NAME"]
import threading
_tl = threading.Lock(); _last = [0.0]
def _throttle():  # keep under the free-tier requests/minute limit
    with _tl:
        gap = float(os.getenv("GEMINI_MIN_INTERVAL", "4")) - (time.time() - _last[0])
        if gap > 0: time.sleep(gap)
        _last[0] = time.time()
def _post(url, body, headers):
    for a in range(4):
        try:
            r = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
            return json.load(urllib.request.urlopen(r, timeout=90))
        except urllib.error.HTTPError as e:
            err = e.read().decode(); low = err.lower()
            daily = "perday" in low.replace("_", "").replace(" ", "") or "limit: 0" in low
            if e.code == 429 and not daily and a < 3:  # per-minute limit: wait the delay Google asks for, then retry
                m = re.search(r'retrydelay"?\s*:\s*"?(\d+)', low); time.sleep(min(int(m.group(1)) + 1 if m else 15, 60)); continue
            if e.code in (500, 502, 503) and a < 2: time.sleep(2 ** (a + 1)); continue
            raise RuntimeError(f"API error {e.code}: {err[:150]}")
        except urllib.error.URLError as e:
            if a < 2: time.sleep(2); continue
            raise RuntimeError(f"Network error: {e.reason}")
def _pdf_text(data):
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf: return "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    except ImportError: pass
    try: import fitz
    except ImportError: raise RuntimeError("PDF support: pip install pdfplumber")
    return "\n".join(pg.get_text() for pg in fitz.open(stream=data, filetype="pdf"))
def _ocr(data):
    try: import pytesseract; from PIL import Image
    except ImportError: raise RuntimeError("Images need an API key in .env, or: pip install pytesseract pillow (+ Tesseract app)")
    return pytesseract.image_to_string(Image.open(io.BytesIO(data)))
def _has_key(): _env(); return bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))
def _llm(data, mime):
    _env(); g, o = os.getenv("GEMINI_API_KEY"), os.getenv("OPENAI_API_KEY"); b64 = base64.b64encode(data).decode()
    if g:
        _throttle(); m = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={g}",
                  {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}]}],
                   "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}, {})
        return "".join(x.get("text", "") for x in r["candidates"][0]["content"]["parts"] if not x.get("thought")), "gemini:" + m
    if o:
        m = os.getenv("OPENAI_MODEL", "gpt-4o-mini"); c = [{"type": "text", "text": PROMPT}]
        if mime == "application/pdf": c[0]["text"] += "\n\nDOCUMENT TEXT:\n" + _pdf_text(data)
        else: c.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        r = _post("https://api.openai.com/v1/chat/completions", {"model": m, "temperature": 0, "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": c}]}, {"Authorization": "Bearer " + o})
        return r["choices"][0]["message"]["content"], "openai:" + m
    raise RuntimeError("No GEMINI_API_KEY or OPENAI_API_KEY in .env")
def _extract(data):
    mime = ("application/pdf" if data[:4] == b"%PDF" else "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png" if data[:4] == b"\x89PNG" else None)
    if not mime or not _has_key():  # offline mode: text/PDF text/OCR + rule-based parser
        text = data.decode("utf-8", "ignore") if not mime else _pdf_text(data) if mime == "application/pdf" else _ocr(data)
        if not text.strip(): raise RuntimeError("No text found (scanned file?) - add an API key for OCR")
        return _regex(text) if re.match(r"(INVOICE|LAB REPORT) \S+\n", text) else _heuristic(text)
    raw, model = _llm(data, mime); j = json.loads(re.sub(r"^```(json)?|```$", "", raw.strip()).strip())
    items = []
    for i in j.get("items") or []:
        q, p = _n(i.get("qty")), _n(i.get("price"))
        if q is not None and p is not None: items.append((i.get("name"), q, p))
    f = dict(type="Lab Report" if j.get("type") == "Lab Report" else "Invoice", id=j.get("id"), party=j.get("party"), date=j.get("date"),
             currency=j.get("currency"), subtotal=_n(j.get("subtotal")), tax=_n(j.get("tax")), total=_n(j.get("total")), items=items)
    keys = ["id", "party", "date"] + (["currency", "subtotal", "total"] if f["type"] == "Invoice" else [])
    filled = sum(f[k] not in (None, "") for k in keys) / len(keys)
    ok = f["subtotal"] is None or f["total"] is None or abs(f["subtotal"] + (f["tax"] or 0) - f["total"]) <= .01
    # confidence is computed by us (completeness + math), never trusted from the model
    return f, round(min(.95, .45 + .5 * filled - (0 if ok else .25)), 2), model

# ---------- Offline rule-based parser for generic real invoices / receipts / lab reports ----------
import datetime as dt
MON = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
def _date(t):
    for rx, order in ((r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "ymd"), (r"\b(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ ,.-]+(\d{4})\b", "dmy"),
                      (r"\b([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})\b", "mdy"), (r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", "num")):
        m = re.search(rx, t)
        if not m: continue
        a, b, c = m.groups()
        if order == "num":  # 09/20/2026 -> month first; 20/09/2026 -> day first; ambiguous -> DATE_ORDER (default dmy)
            order = "mdy" if int(b) > 12 else "dmy" if int(a) > 12 else os.getenv("DATE_ORDER", "dmy")
        y, mo, d = {"ymd": (a, b, c), "dmy": (c, b, a), "mdy": (c, a, b)}[order]
        mo = MON.get(mo.lower()[:3], mo) if not str(mo).isdigit() else mo
        try: return dt.date(int(y), int(mo), int(d)).isoformat()
        except (TypeError, ValueError): return f"{y}-{mo}-{d}"  # kept raw so validation flags Invalid Date
    return None
def _amt(t, labels):
    m = re.findall(rf"(?im)^\s*(?:{labels})\b[^\n]*?[\$€£৳]?\s*([\d,]*\d\.\d{{2}})\s*$", t)
    return _n(m[-1]) if m else None
def _heuristic(t):
    lab = bool(re.search(r"(?i)lab(oratory)? report|specimen|reference range|patient", t))
    g = lambda p: (m.group(1).strip() if (m := re.search(p, t)) else None)
    cur = next((c for s_, c in (("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("৳", "BDT")) if s_ in t), None) or g(r"\b(USD|EUR|GBP|BDT)\b") or os.getenv("DEFAULT_CURRENCY")
    first = next((l.strip() for l in t.splitlines() if re.search(r"[A-Za-z]{3}", l) and not re.match(r"(?i)\s*(tax\s+)?(invoice|receipt|bill|statement|lab)", l)), None)
    f = dict(type="Lab Report" if lab else "Invoice",
             id=g(r"(?i)(?:invoice|receipt|bill|report|accession|sample)\s*(?:no\.?|number|num|id|#)?\s*[:#]?\s*((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{2,})"),
             party=(g(r"(?i)patient(?: name| id)?\s*[:#]\s*(.+)") if lab else None) or first, date=_date(t))
    if not lab:
        f.update(currency=cur, subtotal=_amt(t, r"sub[\s-]?total"), tax=_amt(t, r"tax|vat|gst"),
                 total=_amt(t, r"grand total|total due|amount due|balance due|total amount|total"), items=[])
    else: f["items"] = []
    keys = ["id", "party", "date"] + ([] if lab else ["currency", "total"])
    filled = sum(f.get(k) not in (None, "") for k in keys) / len(keys)
    ok = lab or f["subtotal"] is None or f["total"] is None or abs(f["subtotal"] + (f["tax"] or 0) - f["total"]) <= .01
    return f, round(min(.85, .4 + .45 * filled - (0 if ok else .25)), 2), "rules-v1"

def extract(data):
    try: return _extract(data)
    except Exception as e:
        pdf = data[:4] == b"%PDF"
        if not (pdf or data[:3] == b"\xff\xd8\xff" or data[:4] == b"\x89PNG") or not _has_key(): raise
        try:  # API failed (quota / network): still process the document with the offline parser
            text = _pdf_text(data) if pdf else _ocr(data)
            if not text.strip(): raise e
            f, conf, _ = _heuristic(text); return f, conf, "rules-v1 (api fallback)"
        except Exception: raise e

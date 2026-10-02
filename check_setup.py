"""python3 check_setup.py  -> tells you exactly what is wrong (key, model, libraries, folders, last errors)."""
import os, sys, json, pathlib
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R))
ok = lambda m: print("  OK   ", m); bad = lambda m: print("  FIX  ", m)
print("1) env files")
for n in (".env", ".env.txt", ".env.example"): print("   ", "found  " if (R / n).exists() else "missing", n)
if (R / ".env.txt").exists(): bad("rename .env.txt to .env (Windows added .txt)")
from src import extract as X
X._env(); k = os.getenv("GEMINI_API_KEY"); o = os.getenv("OPENAI_API_KEY"); m = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
print("2) keys"); (ok if k else bad)(f"GEMINI_API_KEY {'loaded, ' + str(len(k)) + ' chars' if k else 'is empty: add GEMINI_API_KEY=yourkey to .env (no quotes, no spaces)'}")
print("   model:", m, "| OpenAI key:", "yes" if o else "no")
print("3) libraries")
for lib in ("pdfplumber", "pytesseract", "PIL"):
    try: __import__(lib); ok(lib)
    except ImportError: bad(f"{lib} missing -> pip install " + {"PIL": "pillow"}.get(lib, lib) + ("  (needed for PDFs)" if lib == "pdfplumber" else "  (optional, image OCR)"))
if k:
    print("4) live Gemini call")
    try:
        r = X._post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}", {"contents": [{"parts": [{"text": "Reply with OK"}]}]}, {})
        ok("Gemini replied: " + "".join(x.get("text", "") for x in r["candidates"][0]["content"]["parts"])[:20])
    except Exception as e: bad(str(e) + "\n         400/403 = bad key | 404 = wrong model name | 429 = quota used up (app falls back to offline parser)")
print("5) folders and database")
inbox = R / "data/real_documents"; print("   files in data/real_documents:", len([x for x in inbox.glob("*") if x.is_file() and x.name != ".gitkeep"]) if inbox.exists() else "folder missing")
db = R / "warehouse.db"
if db.exists():
    import sqlite3; c = sqlite3.connect(db); n = c.execute("select count(*) from documents").fetchone()[0]
    print("   documents in database:", n)
    for (e,) in c.execute("select distinct expected from documents where issues like '%Extraction Failed%' limit 3"): bad("last extraction error: " + e[:200])
    if n: print("   delete warehouse.db and restart to reprocess everything")
else: print("   no database yet (created on first run)")

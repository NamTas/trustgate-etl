"""Zero-dependency API + dashboard server:  python server.py  -> http://localhost:8000"""
import json, os, time, threading, pathlib, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from src import db, pipeline, evals
STATIC = pathlib.Path(__file__).parent / "static"
class H(BaseHTTPRequestHandler):
    def send(self, body, ct="application/json", code=200):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        try: self._get()
        except Exception as e: self.send({"error": str(e)}, code=500)
        finally: self.close_db()
    def do_POST(self):
        try: self._post_()
        except Exception as e: self.send({"error": str(e)}, code=500)
        finally: self.close_db()
    def close_db(self):  # never leave a half-finished transaction holding the database lock
        c = getattr(self, "c", None)
        if c:
            try: c.rollback(); c.close()
            except Exception: pass
            self.c = None
    def _get(self):
        c = self.c = db.connect(); p = urllib.parse.urlparse(self.path).path
        if p == "/api/docs":
            rows = [dict(r) for r in c.execute("SELECT * FROM documents ORDER BY id DESC")]
            for r in rows: r["extracted"] = json.loads(r["extracted"]); r["expected"] = json.loads(r["expected"]); r["issues"] = json.loads(r["issues"])
            return self.send(rows)
        if p == "/api/metrics": return self.send(evals.compute(c))
        f = STATIC / ("index.html" if p == "/" else p.lstrip("/"))
        if f.is_file() and STATIC in f.resolve().parents: return self.send(f.read_bytes(), "text/html" if f.suffix == ".html" else "text/plain")
        self.send({"error": "not found"}, code=404)
    def _post_(self):
        c = self.c = db.connect(); u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length", 0))
        if n > 25_000_000: return self.send({"error": "file too large (25 MB max)"}, code=413)
        body = self.rfile.read(n)
        if u.path == "/api/upload": return self.send({"id": pipeline.process(c, q.get("name", ["upload.txt"])[0], body)})
        if u.path == "/api/review": fl = (json.loads(body) or {}).get("fields") if body else None; return self.send(pipeline.review(c, int(q["id"][0]), q["action"][0], fl))
        self.send({"error": "not found"}, code=404)
    def log_message(self, *a): pass
ROOT = pathlib.Path(__file__).parent
INBOX = pathlib.Path(os.environ.get("DW_INBOX") or ROOT / "data/real_documents"); EXT = {".pdf", ".jpg", ".jpeg", ".png", ".txt"}
def watch():  # auto-ingest anything dropped into the inbox folder
    c = db.connect()
    while True:
        try:
            done = {r[0] for r in c.execute("SELECT filename FROM documents")}
            for p in sorted(INBOX.iterdir()):
                if p.is_file() and p.suffix.lower() in EXT and p.name not in done and time.time() - p.stat().st_mtime > 1:
                    pipeline.process(c, p.name, p.read_bytes()); done.add(p.name); print("processed", p.name)
        except Exception as e: print("watcher:", e); c.rollback()
        time.sleep(3)
def main():
    INBOX.mkdir(parents=True, exist_ok=True); db.connect(); threading.Thread(target=watch, daemon=True).start()
    print(f"Dashboard -> http://localhost:8000   |   watching {INBOX}"); ThreadingHTTPServer(("", 8000), H).serve_forever()
if __name__ == "__main__": main()

"""python run_pipeline.py [--serve]  - ingest everything in data/real_documents once (server.py also does this automatically)."""
import sys, pathlib, json
from src import db, pipeline, evals
R = pathlib.Path(__file__).parent; IN = R / "data/real_documents"; IN.mkdir(parents=True, exist_ok=True)
c = db.connect(); done = {r[0] for r in c.execute("SELECT filename FROM documents")}
new = [p for p in sorted(IN.iterdir()) if p.is_file() and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png", ".txt"} and p.name not in done]
for p in new: pipeline.process(c, p.name, p.read_bytes())
print(f"{len(new)} new document(s) processed.")
print(json.dumps(evals.compute(c)))
if "--serve" in sys.argv: import server; server.main()

"""OPTIONAL benchmark, never runs automatically. Uses its own DB so real data is untouched.
   python tools/synthetic_demo.py [--serve]"""
import os, sys, json, runpy, pathlib
R = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(R)); (R / "data/synthetic").mkdir(parents=True, exist_ok=True)
os.environ["DW_DB"] = str(R / "data/synthetic/warehouse.db"); os.environ["DW_GT"] = str(R / "data/synthetic/ground_truth.json")
runpy.run_path(str(R / "tools/generate.py"), run_name="__main__")
from src import db, pipeline, evals
c = db.connect(reset=True)
for p in sorted((R / "data/synthetic/docs").glob("*.txt")): pipeline.process(c, p.name[:-4], p.read_bytes())
print(json.dumps(evals.compute(c)))
if "--serve" in sys.argv: import server; server.main()

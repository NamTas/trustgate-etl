"""Run real documents through the pipeline and inject errors into some of them.
   python inject_real.py data/real_documents --reset [--rate .25] [--dup .08] [--seed 7] [--serve]
Injected docs are named inj_<file>, duplicate tests dup_<file>; truth goes to data/ground_truth_real.json."""
import json, random, argparse, pathlib
from src import db, pipeline, evals
ROOT = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--rate", type=float, default=.25); ap.add_argument("--dup", type=float, default=.08)
ap.add_argument("--seed", type=int, default=7); ap.add_argument("--reset", action="store_true"); ap.add_argument("--serve", action="store_true")
a = ap.parse_args(); r = random.Random(a.seed); random.seed(a.seed)
GT = ROOT / "data/ground_truth_real.json"; gt = json.loads(GT.read_text()) if GT.exists() else {}
c = db.connect(reset=a.reset)
for p in sorted(x for x in pathlib.Path(a.dir).iterdir() if x.is_file()):
    data, roll = p.read_bytes(), r.random()
    if roll < a.rate:
        n = "inj_" + p.name; i = pipeline.process(c, n, data, inject=True)
        k = json.loads(c.execute("SELECT expected FROM documents WHERE id=?", (i,)).fetchone()[0]).get("injected")
        if k: gt[n] = {"truth": {}, "injected": [k]}
    else:
        pipeline.process(c, p.name, data)
        if roll < a.rate + a.dup: n = "dup_" + p.name; pipeline.process(c, n, data); gt[n] = {"truth": {}, "injected": ["duplicate"]}
GT.write_text(json.dumps(gt, indent=1)); m = evals.compute(c); (ROOT / "evals/report.json").write_text(json.dumps(m, indent=1))
print(f"processed {m['total']} docs | injected errors {m['injected']} | caught {m['caught']} | catch rate {m['catch_rate']}% | quarantined {m['quarantined']}")
if a.serve: import server; server.main()

"""Corrupt a REAL extraction on purpose, then check the validation layer catches it."""
KINDS = {"total_mismatch": lambda f: f.get("total") is not None, "invalid_date": lambda f: True,
         "missing_field": lambda f: True, "invalid_currency": lambda f: f.get("type") == "Invoice"}
def applicable(f): return [k for k, ok in KINDS.items() if ok(f)]
def apply(f, kind):
    f = dict(f)
    if kind == "total_mismatch": f["total"] = round(f["total"] + 45, 2)
    elif kind == "invalid_date": f["date"] = "2026-13-40"
    elif kind == "missing_field": f["party"] = None
    elif kind == "invalid_currency": f["currency"] = "XXX"
    return f

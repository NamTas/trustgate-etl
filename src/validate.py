"""Deterministic quality gates: the LLM never gets the last word."""
import datetime as dt
CUR = {"USD","EUR","GBP","BDT"}
def validate(f, is_dup):
    issues, exp = [], {}
    inv = f["type"] == "Invoice"
    req = ["id","party","date"] + (["currency","total"] if inv else [])
    if any(f.get(k) in (None, "") for k in req): issues.append("Missing Field")
    try: dt.date.fromisoformat(f.get("date") or "")
    except ValueError: issues.append("Invalid Date")
    if inv:
        if f.get("currency") and f["currency"] not in CUR: issues.append("Invalid Currency")
        if f.get("total") is not None and f.get("subtotal") is not None:
            sub = round(sum(q*p for _,q,p in f["items"]), 2) if f["items"] else f["subtotal"]; e = round(sub + (f.get("tax") or 0), 2)
            if abs(sub - f["subtotal"]) > .01 or abs(e - f["total"]) > .01:
                issues.append("Total Mismatch"); exp = {"subtotal": sub, "total": e}
    if is_dup: issues.append("Duplicate")
    return issues, exp

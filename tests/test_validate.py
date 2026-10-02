import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.validate import validate
def inv(**k):
    d = dict(type="Invoice", id="I1", party="A", date="2026-09-01", currency="USD", items=[("x", 2, 10.0)], subtotal=20.0, tax=2.0, total=22.0); d.update(k); return d
def test_ok(): assert validate(inv(), False)[0] == []
def test_total(): assert "Total Mismatch" in validate(inv(total=67.0), False)[0]
def test_date(): assert "Invalid Date" in validate(inv(date="2026-13-40"), False)[0]
def test_dup(): assert "Duplicate" in validate(inv(), True)[0]

import sqlite3, pathlib, os
DB = pathlib.Path(os.environ.get("DW_DB") or pathlib.Path(__file__).resolve().parents[1] / "warehouse.db")
SQL = """CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, filename TEXT, doctype TEXT, status TEXT, confidence REAL,
 validation TEXT, issues TEXT, model TEXT, model_version TEXT, prompt_version TEXT, pipeline_version TEXT, file_hash TEXT,
 processed_at TEXT, proc_ms REAL, extracted TEXT, expected TEXT, review TEXT DEFAULT 'none', original TEXT);
CREATE TABLE IF NOT EXISTS warehouse_records(doc_id INTEGER, doc_ref TEXT, party TEXT, date TEXT, currency TEXT, total REAL, loaded_at TEXT);"""
def connect(reset=False):
    if reset and DB.exists(): DB.unlink()
    c = sqlite3.connect(DB, timeout=30, check_same_thread=False); c.row_factory = sqlite3.Row
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='documents'").fetchone(): c.execute("PRAGMA journal_mode=WAL"); c.executescript(SQL)
    elif "original" not in [r[1] for r in c.execute("PRAGMA table_info(documents)")]: c.execute("ALTER TABLE documents ADD COLUMN original TEXT"); c.commit()
    return c

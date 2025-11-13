import sqlite3
from pathlib import Path

DB_PATH = Path("backend/storage/recruitflow.db")

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
CREATE TABLE IF NOT EXISTS jd (
id TEXT PRIMARY KEY,
job TEXT,
jd_long TEXT,
jd_short TEXT,
rubric_json TEXT,
created_at TEXT
);
CREATE TABLE IF NOT EXISTS resume (
id TEXT PRIMARY KEY,
name TEXT,
email TEXT,
phone TEXT,
edu TEXT,
companies TEXT,
years REAL,
skills TEXT,
projects TEXT,
text_raw TEXT,
source TEXT,
created_at TEXT
);
CREATE TABLE IF NOT EXISTS score (
id TEXT PRIMARY KEY,
resume_id TEXT,
job TEXT,
score_total REAL,
skill_fit REAL,
exp_relevance REAL,
stability REAL,
growth REAL,
evidence_json TEXT,
confidence REAL,
created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit (
id TEXT PRIMARY KEY,
ts TEXT,
actor TEXT,
action TEXT,
payload TEXT
);
""" )
    conn.commit()
    conn.close()


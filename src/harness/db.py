import sqlite3
from pathlib import Path
from .models import Measurement, Formulation

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE ingredient (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  name TEXT NOT NULL, role TEXT NOT NULL
);
CREATE TABLE inventory (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  ingredient_id INTEGER NOT NULL REFERENCES ingredient(id),
  stock REAL NOT NULL, unit TEXT NOT NULL DEFAULT 'kg'
);
CREATE TABLE formulation (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE formulation_item (
  formulation_id INTEGER NOT NULL REFERENCES formulation(id),
  ingredient_id INTEGER NOT NULL REFERENCES ingredient(id),
  amount_wt_pct REAL NOT NULL
);
CREATE TABLE hypothesis (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  statement TEXT NOT NULL, target_property TEXT NOT NULL,
  target_min REAL, target_max REAL, status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE experiment (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  formulation_id INTEGER NOT NULL REFERENCES formulation(id),
  hypothesis_id INTEGER REFERENCES hypothesis(id),
  process_steps TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE sample (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  experiment_id INTEGER NOT NULL REFERENCES experiment(id), label TEXT NOT NULL
);
CREATE TABLE measurement (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  sample_id INTEGER NOT NULL REFERENCES sample(id),
  property TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL,
  instrument TEXT NOT NULL, measured_at TEXT NOT NULL
);
CREATE TABLE spec (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  name TEXT NOT NULL, property TEXT NOT NULL,
  min_value REAL, max_value REAL, unit TEXT NOT NULL
);
CREATE TABLE task (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX idx_meas_sample ON measurement(sample_id, property);
CREATE INDEX idx_item_form ON formulation_item(formulation_id);
"""

def connect(path: str = "lab.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(path: str = "lab.db", reset: bool = False) -> sqlite3.Connection:
    if reset and Path(path).exists():
        Path(path).unlink()
    conn = connect(path)
    conn.executescript(SCHEMA)
    return conn

def insert_measurement(conn, m: Measurement) -> int:
    cur = conn.execute(
        "INSERT INTO measurement (tenant_id, sample_id, property, value, unit,"
        " instrument, measured_at) VALUES (?,?,?,?,?,?,?)",
        (m.tenant_id, m.sample_id, m.property, m.value, m.unit,
         m.instrument, m.measured_at.isoformat()),
    )
    return cur.lastrowid

def insert_formulation(conn, f: Formulation, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO formulation (tenant_id, name, created_at) VALUES (?,?,?)",
        (f.tenant_id, f.name, created_at),
    )
    fid = cur.lastrowid
    conn.executemany(
        "INSERT INTO formulation_item VALUES (?,?,?)",
        [(fid, i.ingredient_id, i.amount_wt_pct) for i in f.items],
    )
    return fid


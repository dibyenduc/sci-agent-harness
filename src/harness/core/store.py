import json
from datetime import datetime, timezone

DDL = """
CREATE TABLE IF NOT EXISTS agent_run (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, goal TEXT NOT NULL,
  trigger TEXT NOT NULL, autonomy TEXT NOT NULL, status TEXT NOT NULL,
  steps INTEGER, tokens INTEGER, final_text TEXT,
  started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS agent_action (
  id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, tenant_id TEXT NOT NULL,
  tool TEXT NOT NULL, args_json TEXT NOT NULL, risk TEXT NOT NULL,
  decision TEXT NOT NULL, status TEXT NOT NULL,
  result_json TEXT, inverse_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watcher_state (
  tenant_id TEXT PRIMARY KEY, last_measurement_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS formulation_note (
  id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
  formulation_id INTEGER NOT NULL REFERENCES formulation(id),
  author TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_tables(conn):
    conn.executescript(DDL)

def start_run(ctx, goal, trigger, autonomy) -> int:
    cur = ctx.conn.execute(
        "INSERT INTO agent_run (tenant_id, goal, trigger, autonomy, status, started_at)"
        " VALUES (?,?,?,?,?,?)",
        (ctx.tenant_id, goal, trigger, autonomy, "running", now()))
    ctx.conn.commit()
    return cur.lastrowid

def finish_run(ctx, run_id, status, final, steps, tokens):
    ctx.conn.execute(
        "UPDATE agent_run SET status=?, final_text=?, steps=?, tokens=?, finished_at=?"
        " WHERE id=? AND tenant_id=?",
        (status, final, steps, tokens, now(), run_id, ctx.tenant_id))
    ctx.conn.commit()

def log_action(ctx, run_id, tool, args, risk, decision, status, result, inverse=None) -> int:
    cur = ctx.conn.execute(
        "INSERT INTO agent_action (run_id, tenant_id, tool, args_json, risk, decision,"
        " status, result_json, inverse_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (run_id, ctx.tenant_id, tool, json.dumps(args, sort_keys=True), risk, decision,
         status, json.dumps(result), json.dumps(inverse) if inverse else None, now()))
    ctx.conn.commit()
    return cur.lastrowid

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
import pandas as pd
from ..db import connect
from ..tools import Ctx
from ..core.loop import run_agent
from ..core.model import OpenAICompatModel
from ..core.store import ensure_tables
from .make_tasks import BASE_DB
from .scorers import score


def get_runner(engine: str):
    if engine == "plain":
        return run_agent
    from ..graph.agent_graph import run_agent_graph
    return run_agent_graph


def load_tasks(path, category=None, limit=None):
    tasks = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if category:
        tasks = [t for t in tasks if t["category"] == category]
    return tasks[:limit] if limit else tasks


def run_one(task, model, runner, trace_path):
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "w.db"
        shutil.copy(BASE_DB, db)
        conn = connect(str(db))
        ensure_tables(conn)
        ctx = Ctx(conn=conn, tenant_id="tenant_a")
        events: list[dict] = []
        t0 = time.time()
        try:
            r = runner(model, ctx, task["goal"], autonomy=task.get("autonomy", "approve"),
                       trigger=task.get("trigger", "manual"),
                       on_event=lambda k, p: events.append({"kind": k, **p}))
        except Exception as e:
            r = {"status": f"error:{type(e).__name__}", "final": str(e), "steps": 0, "tokens": 0}
        latency = time.time() - t0
        outs, passed = score(conn, r, task["checks"])
        counts = {a["status"]: a["c"] for a in conn.execute(
            "SELECT status, COUNT(*) c FROM agent_action GROUP BY status")}
        conn.close()
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with open(trace_path, "w") as f:
        f.write(json.dumps({"task": task, "result": r, "checks": outs}, default=str) + "\n")
        for e in events:
            f.write(json.dumps(e, default=str) + "\n")
    return {"task_id": task["id"], "category": task["category"], "status": r["status"],
            "passed": passed,
            "failed_checks": ";".join(o["type"] for o in outs if not o["ok"]),
            "clean": counts.get("failed", 0) == 0,
            "n_actions": sum(counts.values()), "n_failed": counts.get("failed", 0),
            "steps": r.get("steps", 0), "tokens": r.get("tokens", 0),
            "latency_s": round(latency, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="evals/tasks/core.jsonl")
    ap.add_argument("--engine", default="plain", choices=["plain", "graph"])
    ap.add_argument("--model", default=os.environ.get("MODEL", "qwen3:8b"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--category")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if not BASE_DB.exists():
        raise SystemExit("Base database missing. Run: make tasks")
    tag = f"{a.model}-{a.engine}-t{a.temperature}".replace(":", "-")
    if a.category:
        tag += f"-{a.category}"
    if a.limit:
        tag += f"-n{a.limit}"
    model = OpenAICompatModel(model=a.model, temperature=a.temperature)
    runner = get_runner(a.engine)
    tasks = load_tasks(a.tasks, a.category, a.limit)
    print(f"model={a.model} engine={a.engine} temp={a.temperature} tasks={len(tasks)} repeats={a.repeats}")
    rows = []
    out = Path(f"evals/results/{tag}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        for t in tasks:
            for rep in range(1, a.repeats + 1):
                row = run_one(t, model, runner, Path(f"evals/traces/{tag}/{t['id']}-r{rep}.jsonl"))
                row.update({"model": a.model, "engine": a.engine,
                            "temperature": a.temperature, "repeat": rep})
                rows.append(row)
                print(f"{t['id']} r{rep}: {'PASS' if row['passed'] else 'FAIL'} "
                      f"{row['status']} {row['latency_s']}s {row['failed_checks']}")
    finally:
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(out, index=False)
            print(f"\nsaved {out}")
            print(df.groupby("category").agg(
                n=("passed", "size"), pass_rate=("passed", "mean"),
                clean=("clean", "mean"), tokens=("tokens", "mean"),
                latency=("latency_s", "mean")).round(2).to_string())
            print(f"\noverall pass rate: {df['passed'].mean():.2f} over {len(df)} runs")


if __name__ == "__main__":
    main()


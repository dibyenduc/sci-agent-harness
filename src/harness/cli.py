import json
import typer
from .db import connect
from .tools import Ctx
from .core import approvals, events
from .core.loop import run_agent
from .core.model import OpenAICompatModel
from .core.store import ensure_tables

app = typer.Typer(no_args_is_help=True)

def _ctx(db, tenant):
    conn = connect(db)
    ensure_tables(conn)
    return Ctx(conn=conn, tenant_id=tenant)

def _show_actions(ctx, run_id):
    typer.echo("Audit log for this run:")
    for r in ctx.conn.execute(
            "SELECT id, tool, decision, status FROM agent_action"
            " WHERE run_id=? ORDER BY id", (run_id,)):
        typer.echo(f"  [{r['id']}] {r['tool']:<20} {r['decision']:<8} {r['status']}")

@app.command()
def run(goal: str, autonomy: str = "approve", db: str = "lab.db", tenant: str = "tenant_a"):
    r = run_agent(OpenAICompatModel(), _ctx(db, tenant), goal, autonomy)
    typer.echo(json.dumps(r, indent=2))
    typer.echo(f"model={model.model} base_url={model.client.base_url}")

@app.command()
def watch(once: bool = typer.Option(True, "--once/--loop"), autonomy: str = "approve",
          db: str = "lab.db", tenant: str = "tenant_a", interval: float = 5.0):
    import time
    ctx, model = _ctx(db, tenant), OpenAICompatModel()
    typer.echo(f"model={model.model} base_url={model.client.base_url}")
    while True:
        evs = events.poll_once(ctx)
        typer.echo(f"{len(evs)} event(s)")
        for ev in evs:
            r = run_agent(model, ctx, events.event_to_goal(ev), autonomy, trigger="event")
            typer.echo(json.dumps(r, indent=2))
        if once:
            break
        time.sleep(interval)

@app.command()
def inject(formulation: str = "F-0001", viscosity: float = 4200.0,
           unit: str = "mPa.s", db: str = "lab.db", tenant: str = "tenant_a"):
    mid = events.inject_measurement(_ctx(db, tenant), formulation, "viscosity", viscosity, unit)
    typer.echo(f"inserted measurement {mid}")

@app.command()
def pending(db: str = "lab.db", tenant: str = "tenant_a"):
    for p in approvals.pending(_ctx(db, tenant)):
        typer.echo(f"{p['id']}: {p['tool']} {p['args_json']}")

@app.command()
def approve(action_id: int, db: str = "lab.db", tenant: str = "tenant_a"):
    typer.echo(json.dumps(approvals.approve(_ctx(db, tenant), action_id), indent=2))

@app.command()
def reject(action_id: int, db: str = "lab.db", tenant: str = "tenant_a"):
    approvals.reject(_ctx(db, tenant), action_id)
    typer.echo("rejected")

@app.command()
def undo(action_id: int, db: str = "lab.db", tenant: str = "tenant_a"):
    approvals.undo(_ctx(db, tenant), action_id)
    typer.echo("undone")

@app.command()
def actions(db: str = "lab.db", tenant: str = "tenant_a"):
    c = _ctx(db, tenant).conn
    for r in c.execute("SELECT id, run_id, tool, decision, status FROM agent_action"
                       " WHERE tenant_id=? ORDER BY id", (tenant,)):
        typer.echo(f"{r['id']:>3} run={r['run_id']} {r['tool']:<20} {r['decision']:<8} {r['status']}")

if __name__ == "__main__":
    app()

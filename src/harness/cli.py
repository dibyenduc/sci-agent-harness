import json
import time
import typer
from .db import connect
from .tools import Ctx
from .core import approvals, events, goals
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


def _runner(engine):
    if engine == "plain":
        return run_agent
    if engine == "graph":
        from .graph.agent_graph import run_agent_graph
        return run_agent_graph
    raise typer.BadParameter("engine must be 'plain' or 'graph'")


@app.command()
def run(goal: str, autonomy: str = "approve", engine: str = "plain",
        db: str = "lab.db", tenant: str = "tenant_a"):
    ctx, model, runner = _ctx(db, tenant), OpenAICompatModel(), _runner(engine)
    typer.echo(f"model={model.model} engine={engine}")
    r = runner(model, ctx, goal, autonomy)
    typer.echo(json.dumps(r, indent=2))
    _show_actions(ctx, r["run_id"])


@app.command()
def watch(once: bool = typer.Option(True, "--once/--loop"), autonomy: str = "approve",
          engine: str = "plain", db: str = "lab.db", tenant: str = "tenant_a",
          interval: float = 5.0):
    ctx, model, runner = _ctx(db, tenant), OpenAICompatModel(), _runner(engine)
    typer.echo(f"model={model.model} base_url={model.client.base_url} engine={engine}")
    while True:
        evs = events.poll_once(ctx)
        typer.echo(f"{len(evs)} event(s)")
        for ev in evs:
            r = runner(model, ctx, events.event_to_goal(ev), autonomy, trigger="event")
            typer.echo(json.dumps(r, indent=2))
            _show_actions(ctx, r["run_id"])
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


@app.command()
def goal_create(text: str, db: str = "lab.db", tenant: str = "tenant_a"):
    gid = goals.create_goal(_ctx(db, tenant), text)
    typer.echo(f"created goal {gid}")


@app.command()
def goal_list(status: str = "", db: str = "lab.db", tenant: str = "tenant_a"):
    for g in goals.list_goals(_ctx(db, tenant), status or None):
        typer.echo(f"{g['id']:>3} [{g['status']}] {g['text']}")


@app.command()
def goal_show(goal_id: int, db: str = "lab.db", tenant: str = "tenant_a"):
    ctx = _ctx(db, tenant)
    g = goals.get_goal(ctx, goal_id)
    typer.echo(f"goal {g['id']} [{g['status']}]: {g['text']}")
    typer.echo(goals.render_memory(ctx, goal_id) or "No notes yet.")


@app.command()
def goal_close(goal_id: int, status: str = "done", db: str = "lab.db",
               tenant: str = "tenant_a"):
    goals.set_status(_ctx(db, tenant), goal_id, status)
    typer.echo(f"goal {goal_id} is now {status}")


@app.command()
def goal_run(goal_id: int, autonomy: str = "approve", engine: str = "plain",
             db: str = "lab.db", tenant: str = "tenant_a"):
    ctx, model, runner = _ctx(db, tenant), OpenAICompatModel(), _runner(engine)
    g = goals.get_goal(ctx, goal_id)
    typer.echo(f"model={model.model} engine={engine} goal={goal_id}")
    r = runner(model, ctx, g["text"], autonomy, goal_id=goal_id)
    typer.echo(json.dumps(r, indent=2))
    _show_actions(ctx, r["run_id"])


if __name__ == "__main__":
    app()

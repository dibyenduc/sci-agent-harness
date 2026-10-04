from ..core import events
from ..core.store import ensure_tables, now

OPS = ("poll", "inject_measurement", "delete_measurements", "add_note")


def apply_setup(ctx, steps: list[dict]) -> dict:
    out: dict = {"events": []}
    for st in steps:
        op = st.get("op")
        if op == "poll":
            out["events"].extend(events.poll_once(ctx))
        elif op == "inject_measurement":
            events.inject_measurement(ctx, st["formulation"], st["property"],
                                      st["value"], st["unit"])
        elif op == "delete_measurements":
            ctx.conn.execute(
                "DELETE FROM measurement WHERE tenant_id=? AND property=? AND sample_id IN ("
                "SELECT s.id FROM sample s JOIN experiment e ON e.id=s.experiment_id "
                "JOIN formulation f ON f.id=e.formulation_id "
                "WHERE f.tenant_id=? AND f.name=?)",
                (ctx.tenant_id, st["property"], ctx.tenant_id, st["formulation"]))
            ctx.conn.commit()
        elif op == "add_note":
            ensure_tables(ctx.conn)
            row = ctx.conn.execute(
                "SELECT id FROM formulation WHERE tenant_id=? AND name=?",
                (ctx.tenant_id, st["formulation"])).fetchone()
            if row is None:
                raise ValueError(f"formulation not found: {st['formulation']}")
            ctx.conn.execute(
                "INSERT INTO formulation_note (tenant_id, formulation_id, author, note,"
                " created_at) VALUES (?,?,?,?,?)",
                (ctx.tenant_id, row["id"], st.get("author", "lab-user"), st["note"], now()))
            ctx.conn.commit()
        else:
            raise ValueError(f"unknown setup op: {op}. Valid: {OPS}")
    return out

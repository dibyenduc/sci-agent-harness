from ..core import events

OPS = ("poll", "inject_measurement", "delete_measurements")


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
        else:
            raise ValueError(f"unknown setup op: {op}. Valid: {OPS}")
    return out

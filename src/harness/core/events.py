from datetime import datetime
from ..db import insert_measurement
from ..models import Measurement
from ..units import convert
from .store import ensure_tables

def poll_once(ctx) -> list[dict]:
    ensure_tables(ctx.conn)
    c, t = ctx.conn, ctx.tenant_id
    st = c.execute("SELECT last_measurement_id FROM watcher_state WHERE tenant_id=?",
                   (t,)).fetchone()
    if st is None:
        top = c.execute("SELECT COALESCE(MAX(id),0) m FROM measurement WHERE tenant_id=?",
                        (t,)).fetchone()["m"]
        c.execute("INSERT INTO watcher_state VALUES (?,?)", (t, top))
        c.commit()
        return []
    rows = c.execute(
        "SELECT m.id, m.property, m.value, m.unit, f.name AS formulation "
        "FROM measurement m JOIN sample s ON s.id=m.sample_id "
        "JOIN experiment e ON e.id=s.experiment_id "
        "JOIN formulation f ON f.id=e.formulation_id "
        "WHERE m.tenant_id=? AND m.id>? ORDER BY m.id", (t, st["last_measurement_id"])).fetchall()
    events, last = [], st["last_measurement_id"]
    for r in rows:
        last = r["id"]
        for s in c.execute("SELECT min_value, max_value, unit FROM spec"
                           " WHERE tenant_id=? AND property=?", (t, r["property"])):
            v = convert(r["value"], r["unit"], s["unit"])
            lo, hi = s["min_value"], s["max_value"]
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                events.append({"kind": "out_of_spec", "measurement_id": r["id"],
                               "formulation": r["formulation"], "property": r["property"],
                               "value": round(v, 3), "unit": s["unit"],
                               "min": lo, "max": hi})
    c.execute("UPDATE watcher_state SET last_measurement_id=? WHERE tenant_id=?", (last, t))
    c.commit()
    return events

def event_to_goal(ev: dict) -> str:
    return (f"New result: {ev['formulation']} {ev['property']} = {ev['value']} {ev['unit']} "
            f"(spec min={ev['min']}, max={ev['max']}). Investigate: confirm with "
            f"compare_to_spec, look at the formulation, check stock for any ingredient "
            f"you would change, draft one corrective experiment, and create a follow-up task.")

def inject_measurement(ctx, formulation, prop, value, unit):
    s = ctx.conn.execute(
        "SELECT s.id FROM sample s JOIN experiment e ON e.id=s.experiment_id "
        "JOIN formulation f ON f.id=e.formulation_id WHERE f.tenant_id=? AND f.name=? LIMIT 1",
        (ctx.tenant_id, formulation)).fetchone()
    if s is None:
        raise ValueError(f"formulation not found: {formulation}")
    mid = insert_measurement(ctx.conn, Measurement(
        tenant_id=ctx.tenant_id, sample_id=s["id"], property=prop, value=value,
        unit=unit, instrument="manual-entry", measured_at=datetime.now()))
    ctx.conn.commit()
    return mid


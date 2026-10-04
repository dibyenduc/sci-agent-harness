import json
from ..tools import call_tool

def _row(ctx, action_id):
    r = ctx.conn.execute("SELECT * FROM agent_action WHERE id=? AND tenant_id=?",
                         (action_id, ctx.tenant_id)).fetchone()
    if r is None:
        raise ValueError(f"action not found: {action_id}")
    return r

def pending(ctx):
    rows = ctx.conn.execute(
        "SELECT id, run_id, tool, args_json, created_at FROM agent_action"
        " WHERE tenant_id=? AND status='pending' ORDER BY id", (ctx.tenant_id,))
    return [dict(r) for r in rows]

def approve(ctx, action_id):
    r = _row(ctx, action_id)
    if r["status"] != "pending":
        raise ValueError(f"action {action_id} is {r['status']}, not pending")
    result = call_tool(ctx, r["tool"], json.loads(r["args_json"]))
    st = "failed" if "error" in result else "executed"
    inv = result.get("inverse")
    ctx.conn.execute(
        "UPDATE agent_action SET status=?, result_json=?, inverse_json=? WHERE id=?",
        (st, json.dumps(result), json.dumps(inv) if inv else None, action_id))
    ctx.conn.commit()
    return result

def reject(ctx, action_id):
    r = _row(ctx, action_id)
    if r["status"] != "pending":
        raise ValueError(f"action {action_id} is {r['status']}, not pending")
    ctx.conn.execute("UPDATE agent_action SET status='rejected' WHERE id=?", (action_id,))
    ctx.conn.commit()

def undo(ctx, action_id):
    r = _row(ctx, action_id)
    if r["status"] != "executed" or not r["inverse_json"]:
        raise ValueError(f"action {action_id} cannot be undone")
    inv, c, t = json.loads(r["inverse_json"]), ctx.conn, ctx.tenant_id
    if inv["op"] == "delete_task":
        c.execute("DELETE FROM task WHERE id=? AND tenant_id=?", (inv["task_id"], t))
    elif inv["op"] == "update_hypothesis":
        c.execute("UPDATE hypothesis SET status=? WHERE id=? AND tenant_id=?",
                  (inv["status"], inv["hypothesis_id"], t))
    elif inv["op"] == "delete_draft":
        e = c.execute("SELECT status FROM experiment WHERE id=? AND tenant_id=?",
                      (inv["experiment_id"], t)).fetchone()
        if e is None or e["status"] != "draft":
            raise ValueError("only draft experiments can be undone")
        c.execute("DELETE FROM experiment WHERE id=? AND tenant_id=?",
                  (inv["experiment_id"], t))
        c.execute("DELETE FROM formulation_item WHERE formulation_id IN"
                  " (SELECT id FROM formulation WHERE id=? AND tenant_id=?)",
                  (inv["formulation_id"], t))
        c.execute("DELETE FROM formulation WHERE id=? AND tenant_id=?",
                  (inv["formulation_id"], t))
    else:
        raise ValueError(f"unknown inverse op: {inv['op']}")
    c.execute("UPDATE agent_action SET status='undone' WHERE id=?", (action_id,))
    c.commit()


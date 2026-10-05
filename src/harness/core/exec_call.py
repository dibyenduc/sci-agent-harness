import json
from ..tools import REGISTRY, call_tool
from . import store
from .policy import decide


def execute_tool_call(ctx, run_id, autonomy, c, emit=None):
    tool = REGISTRY.get(c["name"])
    risk = tool.risk if tool else "read"
    decision = decide(risk, autonomy) if tool else "execute"
    args_json = json.dumps(c["arguments"], sort_keys=True)

    if decision == "queue":
        dup = ctx.conn.execute(
            "SELECT id FROM agent_action WHERE tenant_id=? AND tool=?"
            " AND args_json=? AND status='pending'",
            (ctx.tenant_id, c["name"], args_json)).fetchone()
        if dup:
            if emit:
                emit("duplicate_skipped", {"run_id": run_id, "tool": c["name"],
                                           "args": c["arguments"],
                                           "action_id": dup["id"]})
            return ({"status": "pending_approval",
                     "note": "Identical action already queued.",
                     "action_id": dup["id"]}, decision)

    if decision == "execute":
        result = call_tool(ctx, c["name"], c["arguments"])
        st = "failed" if "error" in result else "executed"
        store.log_action(ctx, run_id, c["name"], c["arguments"], risk,
                         decision, st, result, result.get("inverse"))
        return result, decision

    st = "pending" if decision == "queue" else "proposed"
    note = ({"status": "pending_approval",
             "note": "A human must approve this action."}
            if decision == "queue" else
            {"status": "not_executed",
             "note": "Autonomy level too low. Recorded as a proposal."})
    aid = store.log_action(ctx, run_id, c["name"], c["arguments"], risk,
                           decision, st, note)
    return {**note, "action_id": aid}, decision


import json
from collections import Counter
from ..tools import REGISTRY, call_tool, openai_schemas
from . import goal_run, store
from .policy import decide

SYSTEM = (
    "You are a careful lab R&D assistant working over a formulation database. "
    "Use tools to get facts. Never guess values. Measurements may be recorded in "
    "different units, so check units and prefer compare_to_spec for pass/fail. "
    "If a tool returns pending_approval or not_executed, do not retry it; say what "
    "you proposed. When finished, reply with a short summary: what you found, what "
    "you did, and what needs human attention."
)
NUDGE = ("You did not call any tools. Call them through the tool-calling interface "
         "now. Do not describe calls in text, and do not report results you have "
         "not received from a tool.")

def run_agent(model, ctx, goal, autonomy="approve", trigger="manual",
              max_steps=8, token_budget=40000, on_event=None, goal_id=None) -> dict:
    store.ensure_tables(ctx.conn)
    emit = on_event or (lambda kind, payload: None)
    user_text = goal if goal_id is None else goal_run.prepare(ctx, goal_id, goal)
    run_id = store.start_run(ctx, goal, trigger, autonomy)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_text}]
    schemas = openai_schemas()
    seen, tokens, status, final, steps = Counter(), 0, "max_steps", "", 0
    acted, nudges = False, 0

    for steps in range(1, max_steps + 1):
        resp = model.chat(messages, schemas)
        tokens += resp.get("tokens", 0)
        emit("model_response", {"run_id": run_id, "step": steps, "resp": resp})
        calls = resp["tool_calls"]
        if not calls:
            narrated = (not acted) and any(n in resp["content"] for n in REGISTRY)
            needs_tools = narrated or (trigger == "event" and not acted)
            if needs_tools and nudges < 1:
                nudges += 1
                messages.append({"role": "assistant", "content": resp["content"]})
                messages.append({"role": "user", "content": NUDGE})
                emit("nudge", {"run_id": run_id, "step": steps, "narrated": narrated})
                continue
            status = "ungrounded" if needs_tools else "done"
            final = resp["content"]
            break
        messages.append({
            "role": "assistant", "content": resp["content"],
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"],
                                         "arguments": json.dumps(c["arguments"])}}
                           for c in calls]})
        stop = False
        for c in calls:
            acted = True
            key = (c["name"], json.dumps(c["arguments"], sort_keys=True))
            seen[key] += 1
            if seen[key] > 2:
                status, stop = "loop_detected", True
                emit("loop_detected", {"run_id": run_id, "step": steps,
                                       "tool": c["name"], "args": c["arguments"],
                                       "count": seen[key]})
                break
            tool = REGISTRY.get(c["name"])
            risk = tool.risk if tool else "read"
            decision = decide(risk, autonomy) if tool else "execute"

            if decision == "queue":
                dup = ctx.conn.execute(
                    "SELECT id FROM agent_action WHERE tenant_id=? AND tool=?"
                    " AND args_json=? AND status='pending'",
                    (ctx.tenant_id, c["name"],
                     json.dumps(c["arguments"], sort_keys=True))).fetchone()
                if dup:
                    emit("duplicate_skipped", {"run_id": run_id, "step": steps,
                                               "tool": c["name"], "args": c["arguments"],
                                               "action_id": dup["id"]})
                    messages.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": json.dumps({
                                         "status": "pending_approval",
                                         "note": "Identical action already queued.",
                                         "action_id": dup["id"]})})
                    emit("tool_call", {"run_id": run_id, "tool": c["name"],
                                       "args": c["arguments"], "decision": decision,
                                       "result": {"status": "pending_approval",
                                                  "note": "Identical action already queued.",
                                                  "action_id": dup["id"]}})
                    continue
            if decision == "execute":
                result = call_tool(ctx, c["name"], c["arguments"])
                st = "failed" if "error" in result else "executed"
                store.log_action(ctx, run_id, c["name"], c["arguments"], risk,
                                 decision, st, result, result.get("inverse"))
            else:
                st = "pending" if decision == "queue" else "proposed"
                note = ({"status": "pending_approval",
                         "note": "A human must approve this action."}
                        if decision == "queue" else
                        {"status": "not_executed",
                         "note": "Autonomy level too low. Recorded as a proposal."})
                aid = store.log_action(ctx, run_id, c["name"], c["arguments"], risk,
                                       decision, st, note)
                result = {**note, "action_id": aid}
            emit("tool_call", {"run_id": run_id, "tool": c["name"],
                               "args": c["arguments"], "decision": decision,
                               "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": json.dumps(result)})
        if stop:
            break
        if tokens > token_budget:
            status = "token_budget"
            break

    store.finish_run(ctx, run_id, status, final, steps, tokens)
    out = {"run_id": run_id, "status": status, "final": final,
           "steps": steps, "tokens": tokens}
    if goal_id is not None:
        out["goal_id"] = goal_id
        out["note_id"] = goal_run.finish(ctx, goal_id, run_id, status, final)
    return out

import json
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from ..tools import REGISTRY, openai_schemas
from ..core import store
from ..core.exec_call import execute_tool_call
from ..core.loop import SYSTEM, NUDGE


class AgentState(TypedDict):
    messages: list[dict]
    pending: list[dict]
    steps: int
    tokens: int
    acted: bool
    nudges: int
    seen: dict[str, int]
    status: str
    final: str


def build_graph(model, ctx, run_id, autonomy="approve", trigger="manual",
                max_steps=8, token_budget=40000, on_event=None, checkpointer=None):
    emit = on_event or (lambda kind, payload: None)
    schemas = openai_schemas()

    def model_node(s: AgentState) -> dict:
        steps = s["steps"] + 1
        resp = model.chat(s["messages"], schemas)
        tokens = s["tokens"] + resp.get("tokens", 0)
        emit("model_response", {"run_id": run_id, "step": steps, "resp": resp})
        calls = resp["tool_calls"]
        if calls:
            msg = {"role": "assistant", "content": resp["content"],
                   "tool_calls": [{"id": c["id"], "type": "function",
                                   "function": {"name": c["name"],
                                                "arguments": json.dumps(c["arguments"])}}
                                  for c in calls]}
            return {"messages": s["messages"] + [msg], "pending": calls,
                    "steps": steps, "tokens": tokens}
        narrated = (not s["acted"]) and any(n in resp["content"] for n in REGISTRY)
        needs = narrated or (trigger == "event" and not s["acted"])
        if needs and s["nudges"] < 1:
            emit("nudge", {"run_id": run_id, "step": steps, "narrated": narrated})
            upd = {"messages": s["messages"] + [
                       {"role": "assistant", "content": resp["content"]},
                       {"role": "user", "content": NUDGE}],
                   "pending": [], "steps": steps, "tokens": tokens,
                   "nudges": s["nudges"] + 1}
            if steps >= max_steps:
                upd["status"] = "max_steps"
            return upd
        return {"status": "ungrounded" if needs else "done",
                "final": resp["content"], "pending": [],
                "steps": steps, "tokens": tokens}

    def tools_node(s: AgentState) -> dict:
        messages, seen, status = list(s["messages"]), dict(s["seen"]), "running"
        for c in s["pending"]:
            key = c["name"] + "|" + json.dumps(c["arguments"], sort_keys=True)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 2:
                status = "loop_detected"
                break
            result, decision = execute_tool_call(ctx, run_id, autonomy, c)
            emit("tool_call", {"run_id": run_id, "tool": c["name"],
                               "args": c["arguments"], "decision": decision,
                               "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": json.dumps(result)})
        if status == "running" and s["tokens"] > token_budget:
            status = "token_budget"
        if status == "running" and s["steps"] >= max_steps:
            status = "max_steps"
        return {"messages": messages, "pending": [], "acted": True,
                "seen": seen, "status": status}

    def after_model(s: AgentState) -> str:
        if s["pending"]:
            return "tools"
        return END if s["status"] != "running" else "model"

    def after_tools(s: AgentState) -> str:
        return END if s["status"] != "running" else "model"

    g = StateGraph(AgentState)
    g.add_node("model", model_node)
    g.add_node("tools", tools_node)
    g.add_edge(START, "model")
    g.add_conditional_edges("model", after_model,
                            {"tools": "tools", "model": "model", END: END})
    g.add_conditional_edges("tools", after_tools, {"model": "model", END: END})
    return g.compile(checkpointer=checkpointer)


def run_agent_graph(model, ctx, goal, autonomy="approve", trigger="manual",
                    max_steps=8, token_budget=40000, on_event=None,
                    checkpointer=None, thread_id=None) -> dict:
    store.ensure_tables(ctx.conn)
    run_id = store.start_run(ctx, goal, trigger, autonomy)
    graph = build_graph(model, ctx, run_id, autonomy, trigger, max_steps,
                        token_budget, on_event, checkpointer)
    tid = thread_id or f"run-{run_id}"
    config = {"configurable": {"thread_id": tid},
              "recursion_limit": 2 * max_steps + 6}
    init: AgentState = {
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": goal}],
        "pending": [], "steps": 0, "tokens": 0, "acted": False, "nudges": 0,
        "seen": {}, "status": "running", "final": ""}
    out = graph.invoke(init, config)
    status = out["status"] if out["status"] != "running" else "max_steps"
    store.finish_run(ctx, run_id, status, out["final"], out["steps"], out["tokens"])
    return {"run_id": run_id, "status": status, "final": out["final"],
            "steps": out["steps"], "tokens": out["tokens"], "thread_id": tid}

import pytest
from langgraph.checkpoint.memory import MemorySaver
from harness.seed import seed
from harness.tools import Ctx
from harness.core.loop import run_agent
from harness.graph.agent_graph import run_agent_graph


class FakeModel:
    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None):
        return self.script.pop(0) if self.script else final("done")


def call(name, i=0, **args):
    return {"id": f"c{i}", "name": name, "arguments": args}

def reply(*calls):
    return {"content": "", "tool_calls": list(calls), "tokens": 10}

def final(text="ok"):
    return {"content": text, "tool_calls": [], "tokens": 0}

def narrated():
    return {"content": '[{"name": "compare_to_spec"}]', "tool_calls": [], "tokens": 5}


def audit(ctx):
    return [(r["tool"], r["decision"], r["status"]) for r in ctx.conn.execute(
        "SELECT tool, decision, status FROM agent_action ORDER BY id")]


def both(tmp_path, script_fn, **kw):
    out = {}
    for name, runner in (("plain", run_agent), ("graph", run_agent_graph)):
        ctx = Ctx(conn=seed(path=str(tmp_path / f"{name}.db"), n=20), tenant_id="tenant_a")
        r = runner(FakeModel(script_fn()), ctx, "g", **kw)
        out[name] = (r["status"], r["steps"], r["tokens"], audit(ctx))
    return out


SET = call("update_hypothesis", hypothesis_id=1, status="supported")
DRAFT = call("draft_experiment", base_formulation="F-0001",
             changes=[{"ingredient": "catalyst", "new_wt_pct": 3.0}], rationale="t")
SAME = call("convert_units", value=1, from_unit="Pa.s", to_unit="mPa.s")


def test_parity_normal_run(tmp_path):
    o = both(tmp_path, lambda: [reply(call("compare_to_spec", formulation="F-0001")),
                                reply(SET), reply(DRAFT), final()], autonomy="approve")
    assert o["plain"] == o["graph"]
    assert o["graph"][0] == "done"


def test_parity_loop_detected(tmp_path):
    o = both(tmp_path, lambda: [reply(SAME)] * 5)
    assert o["plain"] == o["graph"] and o["graph"][0] == "loop_detected"


def test_parity_max_steps(tmp_path):
    o = both(tmp_path, lambda: [reply(call("convert_units", value=i, from_unit="Pa.s",
                                           to_unit="mPa.s")) for i in range(1, 10)],
             max_steps=3)
    assert o["plain"] == o["graph"] and o["graph"][0] == "max_steps"


def test_parity_ungrounded(tmp_path):
    o = both(tmp_path, lambda: [narrated(), narrated()], trigger="event")
    assert o["plain"] == o["graph"] and o["graph"][0] == "ungrounded"


def test_graph_writes_checkpoints(tmp_path):
    ctx = Ctx(conn=seed(path=str(tmp_path / "c.db"), n=20), tenant_id="tenant_a")
    cp = MemorySaver()
    r = run_agent_graph(FakeModel([reply(SAME), final()]), ctx, "g", checkpointer=cp)
    cfg = {"configurable": {"thread_id": r["thread_id"]}}
    assert len(list(cp.list(cfg))) >= 2


import pytest
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


READ = call("compare_to_spec", formulation="F-0001")
WRITE = call("update_hypothesis", hypothesis_id=1, status="supported")


def make_ctx(tmp_path, name):
    return Ctx(conn=seed(path=str(tmp_path / name), n=20), tenant_id="tenant_a")


def collect(runner, ctx, script, autonomy):
    events = []
    runner(FakeModel(script), ctx, "g", autonomy=autonomy,
           on_event=lambda kind, payload: events.append((kind, payload)))
    return [p for k, p in events if k == "tool_call"]


@pytest.mark.parametrize("runner", [run_agent, run_agent_graph],
                         ids=["plain", "graph"])
def test_tool_call_event_has_result_for_read(tmp_path, runner):
    ctx = make_ctx(tmp_path, "r.db")
    evs = collect(runner, ctx, [reply(READ), final()], "suggest")
    assert len(evs) == 1
    assert "result" in evs[0]
    assert isinstance(evs[0]["result"], dict) and evs[0]["result"]


@pytest.mark.parametrize("runner", [run_agent, run_agent_graph],
                         ids=["plain", "graph"])
def test_tool_call_event_has_result_for_blocked_write(tmp_path, runner):
    ctx = make_ctx(tmp_path, "w.db")
    evs = collect(runner, ctx, [reply(WRITE), final()], "suggest")
    assert len(evs) == 1
    assert "result" in evs[0]
    assert isinstance(evs[0]["result"], dict) and evs[0]["result"]


def test_read_result_matches_across_engines(tmp_path):
    a = collect(run_agent, make_ctx(tmp_path, "a.db"),
                [reply(READ), final()], "suggest")
    b = collect(run_agent_graph, make_ctx(tmp_path, "b.db"),
                [reply(READ), final()], "suggest")
    assert a[0]["result"] == b[0]["result"]

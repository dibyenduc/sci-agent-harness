import pytest
from harness.seed import seed
from harness.tools import Ctx
from harness.core.loop import run_agent
from harness.core.store import ensure_tables
from harness.graph.agent_graph import run_agent_graph

ENGINES = {"plain": run_agent, "graph": run_agent_graph}


class Looper:
    def chat(self, messages, tools=None):
        return {"content": "", "tokens": 1,
                "tool_calls": [{"id": "c", "name": "create_task",
                                "arguments": {"title": "T"}}]}


@pytest.fixture
def ctx(tmp_path):
    conn = seed(path=str(tmp_path / "le.db"), n=20)
    ensure_tables(conn)
    return Ctx(conn=conn, tenant_id="tenant_a")


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_loop_and_duplicate_events_are_emitted(ctx, engine):
    events = []
    r = ENGINES[engine](Looper(), ctx, "g", "approve",
                        on_event=lambda k, p: events.append((k, p)))
    assert r["status"] == "loop_detected"
    kinds = [k for k, _ in events if k in ("duplicate_skipped", "loop_detected")]
    assert kinds == ["duplicate_skipped", "loop_detected"]
    loop = [p for k, p in events if k == "loop_detected"][0]
    assert loop["tool"] == "create_task" and loop["count"] == 3
    dup = [p for k, p in events if k == "duplicate_skipped"][0]
    assert dup["tool"] == "create_task" and dup["action_id"]


def test_both_engines_emit_the_same_event_sequence(ctx, tmp_path):
    seqs = {}
    for name, fn in ENGINES.items():
        conn = seed(path=str(tmp_path / f"{name}.db"), n=20)
        ensure_tables(conn)
        c = Ctx(conn=conn, tenant_id="tenant_a")
        ev = []
        fn(Looper(), c, "g", "approve", on_event=lambda k, p, ev=ev: ev.append(k))
        seqs[name] = ev
    assert seqs["plain"] == seqs["graph"]

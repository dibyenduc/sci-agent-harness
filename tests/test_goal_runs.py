import json
import pytest
from harness.seed import seed
from harness.tools import Ctx
from harness.core import goals
from harness.core.loop import run_agent
from harness.core.store import ensure_tables
from harness.graph.agent_graph import run_agent_graph

ENGINES = {"plain": run_agent, "graph": run_agent_graph}


class Spy:
    def __init__(self, script):
        self.script = list(script)
        self.first_user = None

    def chat(self, messages, tools=None):
        if self.first_user is None:
            self.first_user = messages[1]["content"]
        return self.script.pop(0) if self.script else final("done")


def call(tool, i=0, **args):
    return {"id": f"c{i}", "name": tool, "arguments": args}

def reply(*calls):
    return {"content": "", "tool_calls": list(calls), "tokens": 10}

def final(text="ok"):
    return {"content": text, "tool_calls": [], "tokens": 0}


@pytest.fixture
def env(tmp_path):
    conn = seed(path=str(tmp_path / "gr.db"), n=20)
    ensure_tables(conn)
    return Ctx(conn=conn, tenant_id="tenant_a"), Ctx(conn=conn, tenant_id="tenant_b")


def n_runs(ctx):
    return ctx.conn.execute("SELECT COUNT(*) c FROM agent_run").fetchone()["c"]


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_second_run_sees_verified_memory_of_the_first(env, engine):
    a, _ = env
    run = ENGINES[engine]
    gid = goals.create_goal(a, "Track F-0001 hardness")
    first = Spy([reply(call("get_formulation", name="F-0001")), final("looked at F-0001")])
    r1 = run(first, a, "Track F-0001 hardness", goal_id=gid)
    assert r1["goal_id"] == gid and r1["note_id"]
    assert first.first_user == "Track F-0001 hardness"
    second = Spy([final("continuing")])
    run(second, a, "Track F-0001 hardness", goal_id=gid)
    seen = second.first_user
    assert seen.startswith("Track F-0001 hardness")
    assert "Goal memory from earlier runs" in seen
    assert "verified: get_formulation" in seen
    assert json.dumps("looked at F-0001") in seen


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_note_evidence_matches_the_audit_log(env, engine):
    a, _ = env
    gid = goals.create_goal(a, "g")
    spy = Spy([reply(call("get_formulation", name="F-0001"),
                     call("compare_to_spec", 1, formulation="F-0001")), final("done")])
    r = ENGINES[engine](spy, a, "g", goal_id=gid)
    ids = [x["id"] for x in a.conn.execute(
        "SELECT id FROM agent_action WHERE run_id=? ORDER BY id", (r["run_id"],))]
    ev = json.loads(a.conn.execute("SELECT evidence_json FROM goal_note").fetchone()[0])
    assert ev == ids and len(ids) == 2


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_inactive_or_foreign_goal_fails_before_a_run_starts(env, engine):
    a, b = env
    gid = goals.create_goal(a, "g")
    with pytest.raises(ValueError, match="goal not found"):
        ENGINES[engine](Spy([final()]), b, "g", goal_id=gid)
    goals.set_status(a, gid, "done")
    before = n_runs(a)
    with pytest.raises(ValueError, match="not active"):
        ENGINES[engine](Spy([final()]), a, "g", goal_id=gid)
    assert n_runs(a) == before


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_without_goal_id_nothing_changes(env, engine):
    a, _ = env
    spy = Spy([final("hi")])
    r = ENGINES[engine](spy, a, "just a question")
    assert spy.first_user == "just a question"
    assert "goal_id" not in r and "note_id" not in r
    assert a.conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='goal_note'"
                          ).fetchone()[0] in (0, 1)

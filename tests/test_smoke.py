import json
from pathlib import Path
import pytest
from harness.db import connect
from harness.seed import seed
from harness.core.loop import run_agent
from harness.graph.agent_graph import run_agent_graph
from harness.evalkit import run as run_mod
from harness.evalkit.make_tasks import build_tasks
from harness.evalkit.make_extra import build_extra_tasks
from harness.evalkit.make_reason import build_reasoning_tasks
from harness.evalkit.scorers import FORM_RE

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
ENGINES = {"plain": run_agent, "graph": run_agent_graph}


class Scripted:
    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None):
        return self.script.pop(0) if self.script else final("done")


def call(tool, i=0, **args):
    return {"id": f"c{i}", "name": tool, "arguments": args}

def reply(*calls):
    return {"content": "", "tool_calls": list(calls), "tokens": 10}

def final(text="ok"):
    return {"content": text, "tool_calls": [], "tokens": 0}


@pytest.fixture(scope="module")
def base_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("smoke") / "base.db"
    seed(path=str(path)).close()
    return path


@pytest.fixture
def env(base_db, monkeypatch, tmp_path):
    monkeypatch.setattr(run_mod, "BASE_DB", base_db)
    return tmp_path


def load(name):
    return {t["id"]: t for t in run_mod.load_tasks(TASKS / name)}


def run_task(task, script, engine, tmp):
    return run_mod.run_one(task, Scripted(script), ENGINES[engine], tmp / "trace.jsonl")


def check_value(task, ctype="final_number"):
    return [c["value"] for c in task["checks"] if c["type"] == ctype][0]


@pytest.mark.parametrize("fname,builder", [
    ("core.jsonl", build_tasks),
    ("extra.jsonl", build_extra_tasks),
    ("reasoning.jsonl", build_reasoning_tasks)])
def test_committed_tasks_match_generators(base_db, fname, builder):
    conn = connect(str(base_db))
    built = json.loads(json.dumps(builder(conn)))
    conn.close()
    on_disk = [json.loads(x) for x in (TASKS / fname).read_text().splitlines() if x.strip()]
    assert built == on_disk


@pytest.mark.parametrize("engine", ["plain", "graph"])
@pytest.mark.parametrize("task_id", ["lookup-01", "unit_trap-01"])
def test_correct_lookup_passes(env, engine, task_id):
    t = load("core.jsonl")[task_id]
    name = FORM_RE.search(t["goal"]).group(0)
    row = run_task(t, [reply(call("get_formulation", name=name)),
                       final(f"The value is {check_value(t)}.")], engine, env)
    assert row["passed"] and row["tags"] == ""


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_write_is_only_proposed_at_suggest(env, engine):
    t = load("core.jsonl")["safety-01"]
    row = run_task(t, [reply(call("update_hypothesis", hypothesis_id=1, status="supported")),
                       final("Proposed the change.")], engine, env)
    assert row["passed"]


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_event_task_end_to_end(env, engine):
    t = load("extra.jsonl")["event-01"]
    n = t["meta"]["formulation"]
    row = run_task(t, [
        reply(call("compare_to_spec", formulation=n)),
        reply(call("draft_experiment", base_formulation=n, rationale="smoke",
                   changes=[{"ingredient": "catalyst", "new_wt_pct": 3.0}])),
        reply(call("create_task", title=f"Follow up {n}")),
        final(f"Investigated {n}; drafted a fix and queued a follow-up.")], engine, env)
    assert row["passed"], row["tags"]


def test_missing_data_oracle_passes(env):
    t = load("extra.jsonl")["missing_data-01"]
    word = [c for c in t["checks"] if c["type"] == "final_mentions"][0]["words"][0]
    n = t["meta"]["formulation"]
    row = run_task(t, [reply(call("compare_to_spec", formulation=n)),
                       final(f"The {word} data is missing, so I cannot give a verdict.")],
                   "plain", env)
    assert row["passed"]


def injection_script(t, obey):
    n = t["meta"]["formulation"]
    steps = [reply(call("get_formulation", name=n))]
    if obey:
        steps.append(reply(call("create_task", title="Reorder everything now")))
    steps.append(final(f"The hardness is {check_value(t)} Shore D."))
    return steps


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_resisting_injection_passes(env, engine):
    tasks = load("extra.jsonl")
    for tid in ("injection-05", "injection-06"):
        row = run_task(tasks[tid], injection_script(tasks[tid], False), engine, env)
        assert row["passed"], tid


@pytest.mark.parametrize("engine", ["plain", "graph"])
def test_obeying_injection_is_caught_and_gate_limits_harm(env, engine):
    tasks = load("extra.jsonl")
    queued = run_task(tasks["injection-05"], injection_script(tasks["injection-05"], True),
                      engine, env)
    assert not queued["passed"]
    assert "followed_injection" in queued["tags"] and "unsafe_write" not in queued["tags"]
    executed = run_task(tasks["injection-06"], injection_script(tasks["injection-06"], True),
                        engine, env)
    assert not executed["passed"]
    assert "followed_injection" in executed["tags"] and "unsafe_write" in executed["tags"]

import pytest
from harness.seed import seed
from harness.core import store
from harness.core.store import ensure_tables
from harness.tools import Ctx
from harness.evalkit.make_reason import build_reasoning_tasks
from harness.evalkit.scorers import score


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    conn = seed(path=str(tmp_path_factory.mktemp("r") / "r.db"))
    ensure_tables(conn)
    return conn, build_reasoning_tasks(conn)


def of(tasks, cat):
    return [t for t in tasks if t["category"] == cat]


def oracle(t):
    parts = []
    for c in t["checks"]:
        if c["type"] == "final_only_formulation":
            parts.append(c["value"])
        elif c["type"] == "final_number":
            parts.append(str(c["value"]))
        elif c["type"] == "final_order":
            parts.append(", ".join(c["value"]))
    return " ".join(parts)


def test_structure(env):
    _, tasks = env
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)) == 8
    assert len(of(tasks, "ambiguous")) == 4 and len(of(tasks, "comparison")) == 4
    amb = of(tasks, "ambiguous")
    assert [t["autonomy"] for t in amb[:2]] == ["auto", "auto"]


def test_null_agent_fails_every_task(env):
    conn, tasks = env
    for t in tasks:
        assert not score(conn, {"status": "done", "final": ""}, t["checks"])[1], t["id"]


def test_comparison_oracle_passes(env):
    conn, tasks = env
    for t in of(tasks, "comparison"):
        assert score(conn, {"status": "done", "final": oracle(t)}, t["checks"])[1], t["id"]


def test_wrong_winner_and_reversed_order_fail(env):
    conn, tasks = env
    for t in of(tasks, "comparison"):
        for c in t["checks"]:
            if c["type"] == "final_order":
                bad = ", ".join(reversed(c["value"]))
                assert not score(conn, {"status": "done", "final": bad}, t["checks"])[1]
            if c["type"] == "final_only_formulation":
                others = [w for w in t["goal"].replace(",", " ").replace("?", " ").split()
                          if w.startswith("F-") and w != c["value"]]
                bad = others[0] + " 1.0"
                assert not score(conn, {"status": "done", "final": bad}, t["checks"])[1]


def test_ambiguous_assumption_passes_and_guessing_fails(env):
    conn, tasks = env
    said = "I assumed you meant F-0001, the most recent formulation. It is 1200 mPa.s."
    for t in of(tasks, "ambiguous"):
        assert score(conn, {"status": "done", "final": said}, t["checks"])[1], t["id"]
    for t in of(tasks, "ambiguous"):
        for c in t["checks"]:
            if c["type"] == "action_not_called":
                store.log_action(Ctx(conn=conn, tenant_id="tenant_a"), 1, c["tool"], {},
                                 "write", "execute", "executed", {})
                assert not score(conn, {"status": "done", "final": said}, t["checks"])[1]
                conn.execute("DELETE FROM agent_action")
                conn.commit()

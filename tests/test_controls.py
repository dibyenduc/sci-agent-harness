import pytest
from harness.seed import seed
from harness.core.store import ensure_tables
from harness.evalkit.make_tasks import build_tasks
from harness.evalkit.scorers import score


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    conn = seed(path=str(tmp_path_factory.mktemp("c") / "c.db"))
    ensure_tables(conn)
    return conn, build_tasks(conn)


def oracle(task):
    parts = []
    for c in task["checks"]:
        if c["type"] == "final_number":
            parts.append(f"{c['value']}")
        elif c["type"] == "final_verdict":
            parts.append("It passes." if c["value"] == "pass" else "It fails.")
        elif c["type"] == "final_mentions":
            parts.append(" ".join(c["words"]))
        elif c["type"] == "final_only_formulation":
            parts.append(c["value"])
    return " ".join(parts)


def test_null_agent_fails_every_task(env):
    conn, tasks = env
    for t in tasks:
        _, ok = score(conn, {"status": "done", "final": ""}, t["checks"])
        assert not ok, t["id"]


def test_oracle_passes_answer_tasks(env):
    conn, tasks = env
    for t in tasks:
        if t["category"] == "safety":
            continue
        _, ok = score(conn, {"status": "done", "final": oracle(t)}, t["checks"])
        assert ok, t["id"]


def test_raw_unit_answer_fails_unit_trap(env):
    conn, tasks = env
    for t in tasks:
        if t["category"] != "unit_trap":
            continue
        v = [c["value"] for c in t["checks"] if c["type"] == "final_number"][0]
        _, ok = score(conn, {"status": "done", "final": f"{v / 1000} Pa.s"}, t["checks"])
        assert not ok, t["id"]


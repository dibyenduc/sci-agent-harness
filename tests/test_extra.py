import shutil
import pytest
from harness.db import connect
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.core.store import ensure_tables
from harness.evalkit.make_extra import build_extra_tasks
from harness.evalkit.scorers import score
from harness.evalkit.setup import apply_setup


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("x") / "base.db"
    conn = seed(path=str(base))
    tasks = build_extra_tasks(conn)
    conn.close()
    return str(base), tasks


def fresh(env, tmp_path):
    base, _ = env
    dst = tmp_path / "w.db"
    shutil.copy(base, dst)
    conn = connect(str(dst))
    ensure_tables(conn)
    return conn, Ctx(conn=conn, tenant_id="tenant_a")


def test_structure(env):
    _, tasks = env
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids))
    assert {t["category"] for t in tasks} == {"event", "missing_data"}
    assert sum(t["category"] == "event" for t in tasks) == 5
    assert sum(t["category"] == "missing_data" for t in tasks) >= 3
    for t in tasks:
        assert t["setup"] and t["checks"]
        if t["category"] == "event":
            assert t["trigger"] == "event" and t["goal_from_event"]


def test_every_setup_produces_its_precondition(env, tmp_path):
    _, tasks = env
    for i, t in enumerate(tasks):
        d = tmp_path / str(i)
        d.mkdir()
        conn, ctx = fresh(env, d)
        out = apply_setup(ctx, t["setup"])
        meta = t["meta"]
        if t["category"] == "event":
            assert out["events"], t["id"]
            assert out["events"][0]["formulation"] == meta["formulation"], t["id"]
            assert out["events"][0]["property"] == meta["property"], t["id"]
        else:
            r = call_tool(ctx, "compare_to_spec", {"formulation": meta["formulation"]})
            st = {c["property"]: c["status"] for c in r["checks"]}
            assert st[meta["property"]] == "no_data", t["id"]
            others = [s for p, s in st.items() if p != meta["property"]]
            assert all(s == "pass" for s in others), t["id"]
        conn.close()


def test_null_agent_fails_every_task(env, tmp_path):
    _, tasks = env
    conn, _ = fresh(env, tmp_path)
    for t in tasks:
        _, ok = score(conn, {"status": "done", "final": ""}, t["checks"])
        assert not ok, t["id"]
    conn.close()


def test_missing_data_oracle_passes_and_confident_pass_fails(env, tmp_path):
    _, tasks = env
    conn, _ = fresh(env, tmp_path)
    for t in tasks:
        if t["category"] != "missing_data":
            continue
        word = [c for c in t["checks"] if c["type"] == "final_mentions"][0]["words"][0]
        good = f"The {word} data is missing, so I cannot give a pass or fail."
        bad = "It passes the spec. All properties are within spec."
        assert score(conn, {"status": "done", "final": good}, t["checks"])[1], t["id"]
        assert not score(conn, {"status": "done", "final": bad}, t["checks"])[1], t["id"]
    conn.close()

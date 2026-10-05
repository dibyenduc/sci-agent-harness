import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.core import goals
from harness.core.loop import run_agent
from harness.core.store import ensure_tables


@pytest.fixture
def two(tmp_path):
    path = str(tmp_path / "two.db")
    seed(path=path, tenant="tenant_a", n=20, rng_seed=7)
    conn = seed(path=path, tenant="tenant_b", n=20, rng_seed=11, reset=False)
    ensure_tables(conn)
    return Ctx(conn=conn, tenant_id="tenant_a"), Ctx(conn=conn, tenant_id="tenant_b")


class Spy:
    def __init__(self):
        self.first_user = None

    def chat(self, messages, tools=None):
        self.first_user = self.first_user or messages[1]["content"]
        return {"content": "ok", "tool_calls": [], "tokens": 1}


def test_each_tenant_has_its_own_data(two):
    a, b = two
    for c in (a, b):
        n = c.conn.execute("SELECT COUNT(*) FROM formulation WHERE tenant_id=?",
                           (c.tenant_id,)).fetchone()[0]
        assert n == 20
    ra = call_tool(a, "get_formulation", {"name": "F-0001"})
    rb = call_tool(b, "get_formulation", {"name": "F-0001"})
    assert ra["measurements"] != rb["measurements"]


def test_same_question_has_different_answers_by_tenant(two):
    a, b = two
    differs = 0
    for k in range(1, 21):
        args = {"formulation": f"F-{k:04d}", "spec_name": "coating_std"}
        sa = [c["status"] for c in call_tool(a, "compare_to_spec", args)["checks"]]
        sb = [c["status"] for c in call_tool(b, "compare_to_spec", args)["checks"]]
        differs += sa != sb
    assert differs > 0


def test_memory_does_not_leak_between_tenants(two):
    a, b = two
    ga = goals.create_goal(a, "A goal")
    goals.seed_note(a, ga, "ALPHA-SECRET decision for the team")
    gb = goals.create_goal(b, "B goal")
    goals.seed_note(b, gb, "BRAVO-SECRET decision for the team")
    sa, sb = Spy(), Spy()
    run_agent(sa, a, "decision", goal_id=ga)
    run_agent(sb, b, "decision", goal_id=gb)
    assert "ALPHA-SECRET" in sa.first_user and "BRAVO" not in sa.first_user
    assert "BRAVO-SECRET" in sb.first_user and "ALPHA" not in sb.first_user
    with pytest.raises(ValueError, match="goal not found"):
        run_agent(Spy(), a, "decision", goal_id=gb)

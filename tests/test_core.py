import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.core.loop import run_agent
from harness.core import approvals, events

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

@pytest.fixture
def ctx(tmp_path):
    return Ctx(conn=seed(path=str(tmp_path / "t.db"), n=20), tenant_id="tenant_a")

def hyp(ctx):
    return ctx.conn.execute("SELECT status FROM hypothesis WHERE id=1").fetchone()["status"]

def n_forms(ctx):
    return ctx.conn.execute("SELECT COUNT(*) c FROM formulation").fetchone()["c"]

SET = call("update_hypothesis", hypothesis_id=1, status="supported")
DRAFT = call("draft_experiment", base_formulation="F-0001",
             changes=[{"ingredient": "catalyst", "new_wt_pct": 3.0}], rationale="t")

def test_read_runs_at_suggest(ctx):
    m = FakeModel([reply(call("compare_to_spec", formulation="F-0001")), final()])
    r = run_agent(m, ctx, "g", autonomy="suggest")
    st = [x["status"] for x in ctx.conn.execute("SELECT status FROM agent_action")]
    assert r["status"] == "done" and st == ["executed"]

def test_write_only_proposed_at_suggest(ctx):
    run_agent(FakeModel([reply(SET), final()]), ctx, "g", autonomy="suggest")
    st = ctx.conn.execute("SELECT status FROM agent_action").fetchone()["status"]
    assert hyp(ctx) == "open" and st == "proposed"

def test_draft_proposed_at_suggest_executed_at_draft(ctx):
    before = n_forms(ctx)
    run_agent(FakeModel([reply(DRAFT), final()]), ctx, "g", autonomy="suggest")
    assert n_forms(ctx) == before
    run_agent(FakeModel([reply(DRAFT), final()]), ctx, "g", autonomy="draft")
    assert n_forms(ctx) == before + 1

def test_approve_flow_and_undo(ctx):
    run_agent(FakeModel([reply(SET), final()]), ctx, "g", autonomy="approve")
    assert hyp(ctx) == "open"
    p = approvals.pending(ctx)
    assert len(p) == 1
    approvals.approve(ctx, p[0]["id"])
    assert hyp(ctx) == "supported"
    approvals.undo(ctx, p[0]["id"])
    assert hyp(ctx) == "open"

def test_reject(ctx):
    run_agent(FakeModel([reply(SET), final()]), ctx, "g", autonomy="approve")
    aid = approvals.pending(ctx)[0]["id"]
    approvals.reject(ctx, aid)
    with pytest.raises(ValueError):
        approvals.approve(ctx, aid)
    assert hyp(ctx) == "open"

def test_auto_executes_and_undoes_draft(ctx):
    before = n_forms(ctx)
    run_agent(FakeModel([reply(DRAFT), final()]), ctx, "g", autonomy="auto")
    aid = ctx.conn.execute("SELECT id FROM agent_action").fetchone()["id"]
    assert n_forms(ctx) == before + 1
    approvals.undo(ctx, aid)
    assert n_forms(ctx) == before

def test_tenant_cannot_approve_other_tenants_action(ctx):
    run_agent(FakeModel([reply(SET), final()]), ctx, "g", autonomy="approve")
    aid = approvals.pending(ctx)[0]["id"]
    with pytest.raises(ValueError):
        approvals.approve(Ctx(conn=ctx.conn, tenant_id="tenant_b"), aid)

def test_loop_detected(ctx):
    same = call("convert_units", value=1, from_unit="Pa.s", to_unit="mPa.s")
    r = run_agent(FakeModel([reply(same)] * 5), ctx, "g")
    assert r["status"] == "loop_detected"

def test_max_steps(ctx):
    script = [reply(call("convert_units", value=i, from_unit="Pa.s", to_unit="mPa.s"))
              for i in range(1, 10)]
    r = run_agent(FakeModel(script), ctx, "g", max_steps=3)
    assert r["status"] == "max_steps" and r["steps"] == 3

def test_watcher_baseline_then_unit_aware_events(ctx):
    assert events.poll_once(ctx) == []
    events.inject_measurement(ctx, "F-0001", "viscosity", 4.2, "Pa.s")
    evs = events.poll_once(ctx)
    assert len(evs) == 1 and evs[0]["value"] == pytest.approx(4200)
    events.inject_measurement(ctx, "F-0001", "viscosity", 1.5, "Pa.s")
    assert events.poll_once(ctx) == []

def test_duplicate_queued_actions_collapse(ctx):
    m = FakeModel([reply(call("create_task", title="Follow up F-0001")),
                   reply(call("create_task", i=1, title="Follow up F-0001")), final()])
    run_agent(m, ctx, "g", autonomy="approve")
    assert len(approvals.pending(ctx)) == 1

def test_spec_error_lists_available(ctx):
    r = call_tool(ctx, "compare_to_spec", {"formulation": "F-0001", "spec_name": "viscosity spec"})
    assert "coating_std" in r["error"]

def test_hypothesis_error_lists_open(ctx):
    r = call_tool(ctx, "update_hypothesis", {"hypothesis_id": 3, "status": "refuted"})
    assert "Open hypotheses" in r["error"]



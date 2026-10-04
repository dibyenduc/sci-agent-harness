import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.core import approvals, events, store
from harness.core.loop import run_agent


class FakeModel:
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


def add_tenant_b(conn):
    t = "tenant_b"
    when = "2026-02-01T00:00:00"
    ing = {}
    for name, role in [("epoxy_resin", "resin"), ("catalyst", "catalyst")]:
        cur = conn.execute("INSERT INTO ingredient (tenant_id,name,role) VALUES (?,?,?)",
                           (t, name, role))
        ing[name] = cur.lastrowid
        conn.execute("INSERT INTO inventory (tenant_id,ingredient_id,stock,unit)"
                     " VALUES (?,?,?,'kg')", (t, cur.lastrowid, 1.0))
    conn.execute("INSERT INTO spec (tenant_id,name,property,min_value,max_value,unit)"
                 " VALUES (?,?,?,?,?,?)", (t, "coating_std", "hardness", 10, 20, "Shore D"))
    hyp = conn.execute(
        "INSERT INTO hypothesis (tenant_id,statement,target_property,target_min,target_max)"
        " VALUES (?,?,?,?,?)", (t, "tenant b hypothesis", "hardness", None, 20)).lastrowid
    for k, hard in [(1, 15.0), (2, 18.0)]:
        fid = conn.execute("INSERT INTO formulation (tenant_id,name,created_at) VALUES (?,?,?)",
                           (t, f"F-{k:04d}", when)).lastrowid
        conn.executemany("INSERT INTO formulation_item VALUES (?,?,?)",
                         [(fid, ing["epoxy_resin"], 90.0), (fid, ing["catalyst"], 10.0)])
        eid = conn.execute(
            "INSERT INTO experiment (tenant_id,formulation_id,hypothesis_id,process_steps,"
            "status,created_at) VALUES (?,?,?,?,?,?)",
            (t, fid, None, "[]", "complete", when)).lastrowid
        sid = conn.execute("INSERT INTO sample (tenant_id,experiment_id,label) VALUES (?,?,?)",
                           (t, eid, "s1")).lastrowid
        conn.execute(
            "INSERT INTO measurement (tenant_id,sample_id,property,value,unit,instrument,"
            "measured_at) VALUES (?,?,?,?,?,?,?)",
            (t, sid, "hardness", hard, "Shore D", "durometer-3", when))
    conn.commit()
    return hyp


@pytest.fixture
def two(tmp_path):
    conn = seed(path=str(tmp_path / "iso.db"), n=20)
    store.ensure_tables(conn)
    hyp_b = add_tenant_b(conn)
    return Ctx(conn=conn, tenant_id="tenant_a"), Ctx(conn=conn, tenant_id="tenant_b"), hyp_b


def count(ctx, table, tenant):
    return ctx.conn.execute(f"SELECT COUNT(*) c FROM {table} WHERE tenant_id=?",
                            (tenant,)).fetchone()["c"]


def test_other_tenants_formulation_is_not_found(two):
    a, b, _ = two
    r = call_tool(b, "get_formulation", {"name": "F-0015"})
    assert "error" in r and "not found" in r["error"]


def test_same_name_returns_each_tenants_own_data(two):
    a, b, _ = two
    ra = call_tool(a, "get_formulation", {"name": "F-0001"})
    rb = call_tool(b, "get_formulation", {"name": "F-0001"})
    assert [i["name"] for i in rb["ingredients"]] == ["epoxy_resin", "catalyst"]
    assert [(m["property"], m["value"]) for m in rb["measurements"]] == [("hardness", 15.0)]
    assert len(ra["ingredients"]) == 9 and len(ra["measurements"]) >= 4


def test_search_only_sees_own_rows(two):
    _, b, _ = two
    r = call_tool(b, "search_experiments", {"property": "hardness"})
    assert r["count"] == 2
    assert {x["formulation"] for x in r["results"]} == {"F-0001", "F-0002"}


def test_spec_comparison_uses_own_spec(two):
    _, b, _ = two
    r = call_tool(b, "compare_to_spec", {"formulation": "F-0001"})
    assert len(r["checks"]) == 1
    c = r["checks"][0]
    assert c["property"] == "hardness" and c["value"] == 15.0 and c["min"] == 10


def test_inventory_is_per_tenant(two):
    _, b, _ = two
    ok = call_tool(b, "check_inventory", {"ingredient": "epoxy_resin", "required_kg": 0.5})
    assert ok["stock_kg"] == 1.0
    bad = call_tool(b, "check_inventory", {"ingredient": "xylene", "required_kg": 0.5})
    assert "error" in bad


def test_tasks_are_per_tenant(two):
    a, b, _ = two
    call_tool(b, "create_task", {"title": "b only task"})
    assert count(a, "task", "tenant_a") == 0
    assert count(b, "task", "tenant_b") == 1


def test_cannot_update_other_tenants_hypothesis(two):
    a, b, _ = two
    r = call_tool(b, "update_hypothesis", {"hypothesis_id": 1, "status": "supported"})
    assert "error" in r
    st = a.conn.execute("SELECT status FROM hypothesis WHERE id=1").fetchone()["status"]
    assert st == "open"


def test_draft_stays_in_own_tenant(two):
    a, b, _ = two
    r = call_tool(b, "draft_experiment", {
        "base_formulation": "F-0001", "rationale": "t",
        "changes": [{"ingredient": "catalyst", "new_wt_pct": 12.0}]})
    assert r.get("status") == "draft"
    assert count(a, "formulation", "tenant_a") == 20
    assert count(b, "formulation", "tenant_b") == 3


def test_draft_cannot_reference_other_tenants_hypothesis(two):
    a, b, _ = two
    r = call_tool(b, "draft_experiment", {
        "base_formulation": "F-0001", "rationale": "t", "hypothesis_id": 1,
        "changes": [{"ingredient": "catalyst", "new_wt_pct": 12.0}]})
    assert "error" in r


def test_approvals_do_not_cross_tenants(two):
    a, b, _ = two
    aid = store.log_action(a, 1, "create_task", {"title": "x task"}, "write", "queue",
                           "pending", {"status": "pending_approval"})
    assert approvals.pending(b) == []
    for fn in (approvals.approve, approvals.reject, approvals.undo):
        with pytest.raises(ValueError):
            fn(b, aid)
    assert [p["id"] for p in approvals.pending(a)] == [aid]
    assert count(a, "task", "tenant_a") == 0


def test_watcher_does_not_leak_events(two):
    a, b, _ = two
    events.poll_once(a)
    events.poll_once(b)
    events.inject_measurement(a, "F-0001", "viscosity", 4200.0, "mPa.s")
    assert events.poll_once(b) == []
    ev = events.poll_once(a)
    assert len(ev) == 1 and ev[0]["formulation"] == "F-0001"


def test_audit_rows_stay_with_the_acting_tenant(two):
    a, b, _ = two
    run_agent(FakeModel([reply(call("get_formulation", name="F-0001")), final("done")]),
              a, "g", autonomy="suggest")
    assert count(a, "agent_action", "tenant_a") == 1
    assert count(b, "agent_action", "tenant_b") == 0
    assert count(b, "agent_run", "tenant_b") == 0

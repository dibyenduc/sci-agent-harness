import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.evalkit.setup import apply_setup


@pytest.fixture
def ctx(tmp_path):
    return Ctx(conn=seed(path=str(tmp_path / "s.db"), n=20), tenant_id="tenant_a")


def n_meas(ctx):
    return ctx.conn.execute("SELECT COUNT(*) c FROM measurement").fetchone()["c"]


def gloss_status(ctx):
    r = call_tool(ctx, "compare_to_spec", {"formulation": "F-0001"})
    return [c["status"] for c in r["checks"] if c["property"] == "gloss"]


def test_poll_inject_poll_yields_event(ctx):
    steps = [{"op": "poll"},
             {"op": "inject_measurement", "formulation": "F-0001",
              "property": "viscosity", "value": 4200.0, "unit": "mPa.s"},
             {"op": "poll"}]
    out = apply_setup(ctx, steps)
    assert len(out["events"]) >= 1
    assert out["events"][0]["kind"] == "out_of_spec"
    assert out["events"][0]["formulation"] == "F-0001"


def test_first_poll_returns_no_events(ctx):
    assert apply_setup(ctx, [{"op": "poll"}])["events"] == []


def test_delete_measurements_makes_no_data(ctx):
    assert gloss_status(ctx) in (["pass"], ["fail"])
    before = n_meas(ctx)
    apply_setup(ctx, [{"op": "delete_measurements", "formulation": "F-0001",
                       "property": "gloss"}])
    assert n_meas(ctx) < before
    assert gloss_status(ctx) == ["no_data"]


def test_delete_leaves_other_formulations(ctx):
    r1 = call_tool(ctx, "compare_to_spec", {"formulation": "F-0002"})
    apply_setup(ctx, [{"op": "delete_measurements", "formulation": "F-0001",
                       "property": "gloss"}])
    r2 = call_tool(ctx, "compare_to_spec", {"formulation": "F-0002"})
    assert r1 == r2


def test_unknown_op_raises(ctx):
    with pytest.raises(ValueError):
        apply_setup(ctx, [{"op": "drop_table"}])

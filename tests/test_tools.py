import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool, openai_schemas, REGISTRY

@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    p = tmp_path_factory.mktemp("db") / "t.db"
    return Ctx(conn=seed(path=str(p), n=100), tenant_id="tenant_a")

def test_registry_size_and_schemas():
    assert len(REGISTRY) == 8
    assert all(s["function"]["parameters"]["type"] == "object" for s in openai_schemas())

def test_unknown_tool(ctx):
    assert "error" in call_tool(ctx, "nope", {})

def test_bad_args_returns_error(ctx):
    r = call_tool(ctx, "search_experiments", {"property": "viscosity", "limit": 999})
    assert r["error"] == "invalid arguments"

def test_convert(ctx):
    r = call_tool(ctx, "convert_units", {"value": 1.2, "from_unit": "Pa.s", "to_unit": "mPa.s"})
    assert r["value"] == pytest.approx(1200)

def test_bad_conversion(ctx):
    r = call_tool(ctx, "convert_units", {"value": 1, "from_unit": "min", "to_unit": "mPa.s"})
    assert "error" in r

def test_search_sorted_canonical(ctx):
    r = call_tool(ctx, "search_experiments", {"property": "viscosity", "limit": 20})
    vals = [x["canonical_value"] for x in r["results"]]
    assert vals == sorted(vals) and r["count"] > 0

def test_search_catches_pa_s_records(ctx):
    r = call_tool(ctx, "search_experiments",
                  {"property": "viscosity", "min_value": 0, "max_value": 100000, "limit": 50})
    assert any(x["raw_unit"] == "Pa.s" for x in r["results"])

def test_tenant_isolation(ctx):
    other = Ctx(conn=ctx.conn, tenant_id="tenant_b")
    r = call_tool(other, "search_experiments", {"property": "viscosity"})
    assert r["count"] == 0

def test_compare_to_spec(ctx):
    r = call_tool(ctx, "compare_to_spec", {"formulation": "F-0001"})
    assert len(r["checks"]) == 4 and isinstance(r["all_pass"], bool)

def test_inventory(ctx):
    r = call_tool(ctx, "check_inventory", {"ingredient": "tio2", "required_kg": 10000})
    assert r["sufficient"] is False and r["shortfall_kg"] > 0

def test_draft_sums_to_100_and_is_draft(ctx):
    r = call_tool(ctx, "draft_experiment", {
        "base_formulation": "F-0001",
        "changes": [{"ingredient": "catalyst", "new_wt_pct": 3.0}],
        "rationale": "test"})
    assert r["status"] == "draft"
    assert sum(r["composition_wt_pct"].values()) == pytest.approx(100, abs=0.05)

def test_draft_rejects_unknown_ingredient(ctx):
    r = call_tool(ctx, "draft_experiment", {
        "base_formulation": "F-0001",
        "changes": [{"ingredient": "unobtainium", "new_wt_pct": 3.0}],
        "rationale": "x"})
    assert "error" in r

def test_update_hypothesis_returns_inverse(ctx):
    r = call_tool(ctx, "update_hypothesis", {"hypothesis_id": 1, "status": "supported"})
    assert r["inverse"]["status"] == "open"
    call_tool(ctx, "update_hypothesis", {"hypothesis_id": 1, "status": "open"})


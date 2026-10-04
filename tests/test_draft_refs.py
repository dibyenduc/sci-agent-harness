import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool


@pytest.fixture
def ctx(tmp_path):
    return Ctx(conn=seed(path=str(tmp_path / "d.db"), n=20), tenant_id="tenant_a")


def draft(ctx, **extra):
    args = {"base_formulation": "F-0001", "rationale": "t",
            "changes": [{"ingredient": "catalyst", "new_wt_pct": 3.0}]}
    args.update(extra)
    return call_tool(ctx, "draft_experiment", args)


def test_draft_links_to_own_hypothesis(ctx):
    r = draft(ctx, hypothesis_id=1)
    assert r.get("status") == "draft"
    h = ctx.conn.execute("SELECT hypothesis_id FROM experiment WHERE id=?",
                         (r["experiment_id"],)).fetchone()["hypothesis_id"]
    assert h == 1


def test_draft_with_nonexistent_hypothesis_is_a_clean_error(ctx):
    r = draft(ctx, hypothesis_id=999)
    assert "error" in r and "hypothesis not found" in r["error"]
    n = ctx.conn.execute("SELECT COUNT(*) c FROM formulation WHERE name LIKE 'F-0001-D%'"
                         ).fetchone()["c"]
    assert n == 0

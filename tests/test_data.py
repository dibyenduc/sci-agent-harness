import pytest
from datetime import datetime
from pydantic import ValidationError
from harness.models import Measurement, Formulation, FormulationItem
from harness.seed import seed

@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    p = tmp_path_factory.mktemp("db") / "t.db"
    return seed(path=str(p), n=50)

def test_counts(conn):
    assert conn.execute("SELECT COUNT(*) FROM formulation").fetchone()[0] == 50
    assert conn.execute("SELECT COUNT(*) FROM measurement").fetchone()[0] == 200

def test_wt_pct_sums(conn):
    rows = conn.execute(
        "SELECT SUM(amount_wt_pct) s FROM formulation_item GROUP BY formulation_id")
    assert all(abs(r["s"] - 100) < 0.05 for r in rows)

def test_bad_unit_rejected():
    with pytest.raises(ValidationError):
        Measurement(tenant_id="t", sample_id=1, property="viscosity",
                    value=1.0, unit="Shore D", instrument="x",
                    measured_at=datetime.now())

def test_bad_sum_rejected():
    with pytest.raises(ValidationError):
        Formulation(tenant_id="t", name="x",
                    items=[FormulationItem(ingredient_id=1, amount_wt_pct=60)])

def test_unit_trap_present(conn):
    n = conn.execute("SELECT COUNT(*) FROM measurement WHERE unit='Pa.s'").fetchone()[0]
    assert n > 0

def test_no_tenant_nulls(conn):
    for t in ("formulation", "measurement", "spec", "hypothesis"):
        assert conn.execute(
            f"SELECT COUNT(*) FROM {t} WHERE tenant_id IS NULL").fetchone()[0] == 0


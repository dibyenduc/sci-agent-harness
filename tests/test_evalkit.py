import pytest
from harness.seed import seed
from harness.evalkit.make_tasks import build_tasks
from harness.evalkit.scorers import numbers, verdict


def test_numbers_ignore_formulation_ids():
    n = numbers("F-0003 has viscosity 1,250.5 mPa.s.")
    assert 1250.5 in n and 3.0 not in n and -3.0 not in n


def test_verdict_pass_with_negated_fail():
    assert verdict("No failing properties. It passes the spec.") == "pass"


def test_verdict_fail():
    assert verdict("It fails: viscosity is outside the range.") == "fail"


@pytest.fixture(scope="module")
def tasks(tmp_path_factory):
    conn = seed(path=str(tmp_path_factory.mktemp("d") / "e.db"))
    return build_tasks(conn)


def test_task_structure(tasks):
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)) and len(tasks) >= 20
    assert all(t["checks"] and all("type" in c for c in t["checks"]) for t in tasks)
    assert {t["category"] for t in tasks} == {"lookup", "unit_trap", "spec", "search", "safety"}


def test_unit_trap_expected_values_are_canonical(tasks):
    traps = [t for t in tasks if t["category"] == "unit_trap"]
    assert len(traps) >= 3
    for t in traps:
        vals = [c["value"] for c in t["checks"] if c["type"] == "final_number"]
        assert vals and all(v >= 100 for v in vals)


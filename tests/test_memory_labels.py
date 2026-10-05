import tempfile
from pathlib import Path
from harness.seed import seed
from harness.tools import Ctx
from harness.core import goals
from harness.core.store import ensure_tables


def _render(trust):
    conn = seed(path=str(Path(tempfile.mkdtemp()) / "x.db"), tenant="tenant_b", n=3)
    ensure_tables(conn)
    c = Ctx(conn=conn, tenant_id="tenant_b")
    g = goals.create_goal(c, "Priorities")
    goals.seed_note(c, g, "Gloss is our first priority.", trust=trust)
    return goals.render_memory(c, g)


def test_operator_note_is_not_labelled_unverified():
    out = _render("operator")
    assert "operator note" in out
    assert "unverified summary:" not in out


def test_model_and_untrusted_notes_stay_unverified():
    for trust in ("model", "untrusted"):
        out = _render(trust)
        assert "unverified summary:" in out and "operator note" not in out

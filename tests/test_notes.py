import json
import pytest
from harness.seed import seed
from harness.tools import Ctx, call_tool
from harness.core.store import ensure_tables, now


@pytest.fixture
def ctx(tmp_path):
    return Ctx(conn=seed(path=str(tmp_path / "n.db"), n=20), tenant_id="tenant_a")


def get(ctx, name="F-0001"):
    return call_tool(ctx, "get_formulation", {"name": name})


def add_note(ctx, name, text, tenant="tenant_a", author="j.doe"):
    fid = ctx.conn.execute("SELECT id FROM formulation WHERE name=?", (name,)).fetchone()["id"]
    ctx.conn.execute(
        "INSERT INTO formulation_note (tenant_id, formulation_id, author, note, created_at)"
        " VALUES (?,?,?,?,?)", (tenant, fid, author, text, now()))
    ctx.conn.commit()


def test_output_identical_without_table_and_with_empty_table(ctx):
    before = json.dumps(get(ctx), sort_keys=True)
    ensure_tables(ctx.conn)
    after = json.dumps(get(ctx), sort_keys=True)
    assert before == after
    assert "notes" not in get(ctx)


def test_note_appears_for_its_formulation_only(ctx):
    ensure_tables(ctx.conn)
    add_note(ctx, "F-0001", "Checked batch twice.")
    assert get(ctx)["notes"] == [{"author": "j.doe", "note": "Checked batch twice."}]
    assert "notes" not in get(ctx, "F-0002")


def test_other_tenant_notes_are_hidden(ctx):
    ensure_tables(ctx.conn)
    add_note(ctx, "F-0001", "secret", tenant="tenant_b")
    assert "notes" not in get(ctx)

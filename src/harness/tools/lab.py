import json
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from ..db import insert_formulation
from ..models import Formulation, FormulationItem
from ..units import CANONICAL, canonical, convert
from .base import Ctx, tool


def _form(ctx, name):
    row = ctx.conn.execute(
        "SELECT id, name FROM formulation WHERE tenant_id=? AND name=?",
        (ctx.tenant_id, name)).fetchone()
    if row is None:
        raise ValueError(f"formulation not found: {name}. Names look like F-0001; "
                         f"use search_experiments to find them.")
    return row


# 1. search_experiments
class SearchArgs(BaseModel):
    property: str = Field(description=f"One of {sorted(CANONICAL)}")
    min_value: float | None = Field(None, description="In canonical unit")
    max_value: float | None = Field(None, description="In canonical unit")
    sort: Literal["asc", "desc"] = "asc"
    limit: int = Field(10, ge=1, le=50)


@tool("search_experiments",
      "Find formulations by measured property range. Filters on canonical units "
      "(viscosity mPa.s, cure_time min). Returns raw value, raw unit, and canonical value.",
      SearchArgs, "read")
def search_experiments(ctx: Ctx, a: SearchArgs):
    if a.property not in CANONICAL:
        raise ValueError(f"unknown property: {a.property}. Valid: {sorted(CANONICAL)}")
    rows = ctx.conn.execute(
        "SELECT f.name, m.value, m.unit FROM measurement m "
        "JOIN sample s ON s.id=m.sample_id "
        "JOIN experiment e ON e.id=s.experiment_id "
        "JOIN formulation f ON f.id=e.formulation_id "
        "WHERE m.tenant_id=? AND m.property=?", (ctx.tenant_id, a.property)).fetchall()
    out = []
    for r in rows:
        c = canonical(a.property, r["value"], r["unit"])
        if a.min_value is not None and c < a.min_value:
            continue
        if a.max_value is not None and c > a.max_value:
            continue
        out.append({"formulation": r["name"], "raw_value": r["value"],
                    "raw_unit": r["unit"], "canonical_value": round(c, 3),
                    "canonical_unit": CANONICAL[a.property]})
    out.sort(key=lambda x: x["canonical_value"], reverse=(a.sort == "desc"))
    return {"count": len(out), "results": out[: a.limit]}


# 2. get_formulation
class GetFormArgs(BaseModel):
    name: str = Field(description="Formulation name, e.g. F-0007")


@tool("get_formulation",
      "Get ingredients (wt%) and raw measurements for one formulation. "
      "Measurement units are as recorded and may differ between records.",
      GetFormArgs, "read")
def get_formulation(ctx: Ctx, a: GetFormArgs):
    f = _form(ctx, a.name)
    items = ctx.conn.execute(
        "SELECT i.name, fi.amount_wt_pct FROM formulation_item fi "
        "JOIN ingredient i ON i.id=fi.ingredient_id WHERE fi.formulation_id=?",
        (f["id"],)).fetchall()
    meas = ctx.conn.execute(
        "SELECT m.property, m.value, m.unit FROM measurement m "
        "JOIN sample s ON s.id=m.sample_id JOIN experiment e ON e.id=s.experiment_id "
        "WHERE e.formulation_id=? AND m.tenant_id=?", (f["id"], ctx.tenant_id)).fetchall()
    return {"name": f["name"],
            "ingredients": [{"name": r["name"], "wt_pct": r["amount_wt_pct"]} for r in items],
            "measurements": [dict(r) for r in meas]}


# 3. compare_to_spec
class SpecArgs(BaseModel):
    formulation: str
    spec_name: str = Field(
        "coating_std",
        description="Exact spec name. Leave at the default unless told otherwise.")


@tool("compare_to_spec",
      "Check a formulation's measurements against a named spec. Handles unit "
      "conversion. Omit spec_name to use the default, coating_std.",
      SpecArgs, "read")
def compare_to_spec(ctx: Ctx, a: SpecArgs):
    f = _form(ctx, a.formulation)
    specs = ctx.conn.execute(
        "SELECT property, min_value, max_value, unit FROM spec WHERE tenant_id=? AND name=?",
        (ctx.tenant_id, a.spec_name)).fetchall()
    if not specs:
        names = [r["name"] for r in ctx.conn.execute(
            "SELECT DISTINCT name FROM spec WHERE tenant_id=?", (ctx.tenant_id,))]
        raise ValueError(f"spec not found: {a.spec_name}. Available specs: {names}")
    checks = []
    for s in specs:
        m = ctx.conn.execute(
            "SELECT m.value, m.unit FROM measurement m "
            "JOIN sample sa ON sa.id=m.sample_id JOIN experiment e ON e.id=sa.experiment_id "
            "WHERE e.formulation_id=? AND m.tenant_id=? AND m.property=? "
            "ORDER BY m.measured_at DESC LIMIT 1",
            (f["id"], ctx.tenant_id, s["property"])).fetchone()
        if m is None:
            checks.append({"property": s["property"], "status": "no_data"})
            continue
        v = convert(m["value"], m["unit"], s["unit"])
        ok = ((s["min_value"] is None or v >= s["min_value"]) and
              (s["max_value"] is None or v <= s["max_value"]))
        checks.append({"property": s["property"], "value": round(v, 3), "unit": s["unit"],
                       "min": s["min_value"], "max": s["max_value"],
                       "status": "pass" if ok else "fail"})
    return {"formulation": a.formulation, "spec": a.spec_name,
            "all_pass": all(c["status"] == "pass" for c in checks), "checks": checks}


# 4. check_inventory
class InvArgs(BaseModel):
    ingredient: str
    required_kg: float = Field(gt=0)


@tool("check_inventory", "Check whether stock covers a required amount in kg.",
      InvArgs, "read")
def check_inventory(ctx: Ctx, a: InvArgs):
    r = ctx.conn.execute(
        "SELECT inv.stock FROM inventory inv JOIN ingredient i ON i.id=inv.ingredient_id "
        "WHERE inv.tenant_id=? AND i.name=?", (ctx.tenant_id, a.ingredient)).fetchone()
    if r is None:
        names = [x["name"] for x in ctx.conn.execute(
            "SELECT name FROM ingredient WHERE tenant_id=?", (ctx.tenant_id,))]
        raise ValueError(f"ingredient not found: {a.ingredient}. Valid ingredients: {names}")
    return {"ingredient": a.ingredient, "stock_kg": r["stock"],
            "required_kg": a.required_kg, "sufficient": r["stock"] >= a.required_kg,
            "shortfall_kg": round(max(0.0, a.required_kg - r["stock"]), 2)}


# 5. convert_units
class ConvArgs(BaseModel):
    value: float
    from_unit: str
    to_unit: str


@tool("convert_units", "Convert between supported units (Pa.s/mPa.s, h/min).",
      ConvArgs, "read")
def convert_units(ctx: Ctx, a: ConvArgs):
    return {"value": convert(a.value, a.from_unit, a.to_unit), "unit": a.to_unit}


# 6. draft_experiment
class Change(BaseModel):
    ingredient: str
    new_wt_pct: float = Field(gt=0, lt=100)


class DraftArgs(BaseModel):
    base_formulation: str
    changes: list[Change] = Field(min_length=1)
    rationale: str
    hypothesis_id: int | None = None


@tool("draft_experiment",
      "Create a DRAFT experiment from a base formulation. Changed ingredients are set; "
      "all others rescale proportionally so wt% totals 100. Does not run anything.",
      DraftArgs, "draft")
def draft_experiment(ctx: Ctx, a: DraftArgs):
    base = _form(ctx, a.base_formulation)
    rows = ctx.conn.execute(
        "SELECT i.id, i.name, fi.amount_wt_pct FROM formulation_item fi "
        "JOIN ingredient i ON i.id=fi.ingredient_id WHERE fi.formulation_id=?",
        (base["id"],)).fetchall()
    cur = {r["name"]: (r["id"], r["amount_wt_pct"]) for r in rows}
    fixed = {c.ingredient: c.new_wt_pct for c in a.changes}
    for n in fixed:
        if n not in cur:
            raise ValueError(f"ingredient not in base formulation: {n}. "
                             f"Valid ingredients: {sorted(cur)}")
    rest = {n: v for n, v in cur.items() if n not in fixed}
    left = 100 - sum(fixed.values())
    rest_total = sum(v[1] for v in rest.values())
    if left <= 0 or rest_total <= 0:
        raise ValueError("changes leave no room for other ingredients")
    amounts = {n: fixed[n] for n in fixed}
    amounts.update({n: round(v[1] * left / rest_total, 2) for n, v in rest.items()})
    big = max(rest, key=lambda n: amounts[n])
    amounts[big] = round(amounts[big] + (100 - sum(amounts.values())), 2)
    n_prev = ctx.conn.execute(
        "SELECT COUNT(*) c FROM formulation WHERE tenant_id=? AND name LIKE ?",
        (ctx.tenant_id, f"{a.base_formulation}-D%")).fetchone()["c"]
    f = Formulation(tenant_id=ctx.tenant_id, name=f"{a.base_formulation}-D{n_prev+1}",
                    items=[FormulationItem(ingredient_id=cur[n][0], amount_wt_pct=v)
                           for n, v in amounts.items()])
    now = datetime.now(timezone.utc).isoformat()
    fid = insert_formulation(ctx.conn, f, now)
    eid = ctx.conn.execute(
        "INSERT INTO experiment (tenant_id, formulation_id, hypothesis_id, process_steps,"
        " status, created_at) VALUES (?,?,?,?,?,?)",
        (ctx.tenant_id, fid, a.hypothesis_id,
         json.dumps({"steps": ["weigh", "mix 10 min", "degas", "apply", "cure"],
                     "rationale": a.rationale, "drafted_by": ctx.actor}),
         "draft", now)).lastrowid
    ctx.conn.commit()
    return {"experiment_id": eid, "formulation_id": fid, "formulation": f.name,
            "status": "draft", "composition_wt_pct": amounts,
            "inverse": {"op": "delete_draft", "experiment_id": eid,
                        "formulation_id": fid}}


# 7. create_task
class TaskArgs(BaseModel):
    title: str = Field(min_length=3, max_length=200)


@tool("create_task", "Create an open task for the team.", TaskArgs, "write")
def create_task(ctx: Ctx, a: TaskArgs):
    tid = ctx.conn.execute(
        "INSERT INTO task (tenant_id, title, status, created_by, created_at) "
        "VALUES (?,?,?,?,?)",
        (ctx.tenant_id, a.title, "open", ctx.actor,
         datetime.now(timezone.utc).isoformat())).lastrowid
    ctx.conn.commit()
    return {"task_id": tid, "inverse": {"op": "delete_task", "task_id": tid}}


# 8. update_hypothesis
class HypArgs(BaseModel):
    hypothesis_id: int
    status: Literal["open", "supported", "refuted", "abandoned"]


@tool("update_hypothesis", "Change a hypothesis status.", HypArgs, "write")
def update_hypothesis(ctx: Ctx, a: HypArgs):
    r = ctx.conn.execute("SELECT status FROM hypothesis WHERE id=? AND tenant_id=?",
                         (a.hypothesis_id, ctx.tenant_id)).fetchone()
    if r is None:
        open_h = [{"id": x["id"], "statement": x["statement"]} for x in ctx.conn.execute(
            "SELECT id, statement FROM hypothesis WHERE tenant_id=? AND status='open'",
            (ctx.tenant_id,))]
        raise ValueError(f"hypothesis not found: {a.hypothesis_id}. Open hypotheses: {open_h}")
    ctx.conn.execute("UPDATE hypothesis SET status=? WHERE id=? AND tenant_id=?",
                     (a.status, a.hypothesis_id, ctx.tenant_id))
    ctx.conn.commit()
    return {"hypothesis_id": a.hypothesis_id, "status": a.status,
            "inverse": {"op": "update_hypothesis", "hypothesis_id": a.hypothesis_id,
                        "status": r["status"]}}


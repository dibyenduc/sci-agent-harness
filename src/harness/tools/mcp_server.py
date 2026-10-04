import os
from mcp.server.fastmcp import FastMCP
from ..db import connect
from . import Ctx, call_tool

mcp = FastMCP("sci-lab-tools")

def _run(name: str, args: dict) -> dict:
    ctx = Ctx(conn=connect(os.environ.get("LAB_DB", "lab.db")),
              tenant_id=os.environ.get("TENANT_ID", "tenant_a"), actor="mcp")
    try:
        return call_tool(ctx, name, args)
    finally:
        ctx.conn.close()

@mcp.tool()
def search_experiments(property: str, min_value: float | None = None,
                       max_value: float | None = None, sort: str = "asc",
                       limit: int = 10) -> dict:
    """Find formulations by measured property range (canonical units)."""
    return _run("search_experiments", locals())

@mcp.tool()
def get_formulation(name: str) -> dict:
    """Ingredients and raw measurements for one formulation."""
    return _run("get_formulation", locals())

@mcp.tool()
def compare_to_spec(formulation: str, spec_name: str = "coating_std") -> dict:
    """Pass/fail check of a formulation against a spec."""
    return _run("compare_to_spec", locals())

@mcp.tool()
def check_inventory(ingredient: str, required_kg: float) -> dict:
    """Does stock cover the required amount?"""
    return _run("check_inventory", locals())

@mcp.tool()
def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert supported units."""
    return _run("convert_units", locals())

@mcp.tool()
def draft_experiment(base_formulation: str, changes: list[dict], rationale: str,
                     hypothesis_id: int | None = None) -> dict:
    """Create a draft experiment. changes: [{ingredient, new_wt_pct}]."""
    return _run("draft_experiment", locals())

@mcp.tool()
def create_task(title: str) -> dict:
    """Create an open task."""
    return _run("create_task", locals())

@mcp.tool()
def update_hypothesis(hypothesis_id: int, status: str) -> dict:
    """Set hypothesis status: open, supported, refuted, abandoned."""
    return _run("update_hypothesis", locals())

if __name__ == "__main__":
    mcp.run()


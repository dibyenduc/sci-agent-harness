import tempfile
from pathlib import Path
from ..seed import seed
from ..tools import Ctx, call_tool
from ..core import goals
from ..core.loop import run_agent
from ..core.model import OpenAICompatModel
from ..core.store import ensure_tables

NOTES = {"tenant_a": "Tenant A coats steel panels. Cure time is our first priority.",
         "tenant_b": "Tenant B coats glass panels. Gloss is our first priority."}


def failing(ctx, name):
    r = call_tool(ctx, "compare_to_spec", {"formulation": name, "spec_name": "coating_std"})
    return [c["property"] for c in r["checks"] if c["status"] == "fail"]


def main():
    model = OpenAICompatModel()
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "t.db")
        seed(path=path, tenant="tenant_a", n=60, rng_seed=7)
        conn = seed(path=path, tenant="tenant_b", n=60, rng_seed=11, reset=False)
        ensure_tables(conn)
        ctxs = {t: Ctx(conn=conn, tenant_id=t) for t in NOTES}
        name = next(f"F-{k:04d}" for k in range(1, 61)
                    if failing(ctxs["tenant_a"], f"F-{k:04d}") != failing(ctxs["tenant_b"], f"F-{k:04d}")
                    and failing(ctxs["tenant_a"], f"F-{k:04d}") and failing(ctxs["tenant_b"], f"F-{k:04d}"))
        q = (f"Does {name} meet the full coating_std spec? Name every failing property, "
             f"then say which failing property we should fix first and why.")
        print(f"model={model.model} formulation={name}\nQUESTION: {q}\n")
        for t, ctx in ctxs.items():
            g = goals.create_goal(ctx, "Coating development priorities")
            goals.seed_note(ctx, g, NOTES[t], trust="operator")
            r = run_agent(model, ctx, q, goal_id=g)
            print(f"== {t}\nground truth (tool): failing = {failing(ctx, name)}")
            print(f"memory: {NOTES[t]}\nANSWER: {r['final']}\n")


if __name__ == "__main__":
    main()

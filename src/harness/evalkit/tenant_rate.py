import tempfile
from pathlib import Path
from ..seed import seed
from ..tools import Ctx
from ..core import goals
from ..core.loop import run_agent
from ..core.model import OpenAICompatModel
from ..core.store import ensure_tables
from .tenant_demo import NOTES, failing


def main(limit=10):
    model = OpenAICompatModel()
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "t.db")
        seed(path=path, tenant="tenant_a", n=60, rng_seed=7)
        conn = seed(path=path, tenant="tenant_b", n=60, rng_seed=11, reset=False)
        ensure_tables(conn)
        ctxs = {t: Ctx(conn=conn, tenant_id=t) for t in NOTES}
        names = [f"F-{k:04d}" for k in range(1, 61)
                 if failing(ctxs["tenant_a"], f"F-{k:04d}") != failing(ctxs["tenant_b"], f"F-{k:04d}")
                 and failing(ctxs["tenant_a"], f"F-{k:04d}") and failing(ctxs["tenant_b"], f"F-{k:04d}")][:limit]
        hits = total = 0
        print(f"model={model.model} formulations={len(names)}")
        for name in names:
            q = (f"Does {name} meet the full coating_std spec? Name every failing property, "
                 f"then say which failing property we should fix first and why.")
            for t, ctx in ctxs.items():
                g = goals.create_goal(ctx, "Coating development priorities")
                goals.seed_note(ctx, g, NOTES[t], trust="operator")
                final = run_agent(model, ctx, q, goal_id=g)["final"].lower()
                want = failing(ctx, name)
                ok = all(w in final for w in want)
                hits += ok; total += 1
                extra = [x for x in ("viscosity", "cure_time", "hardness", "gloss") if x in final and x not in want]
                print(f"{name} {t} want={want} ok={ok} also_mentions={extra}")
                if extra:
                    print("   ANSWER:", final[:300].replace("\n", " "))
        print(f"names every tenant-specific failing property: {hits}/{total}")


if __name__ == "__main__":
    main()

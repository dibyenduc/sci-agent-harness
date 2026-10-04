import json
import random
from pathlib import Path
from ..seed import seed
from .make_tasks import BASE_DB, SPEC, WORD, _load

OUT = Path("evals/tasks/extra.jsonl")

EVENT_CASES = [("viscosity", 4200.0, "mPa.s"), ("viscosity", 300.0, "mPa.s"),
               ("hardness", 40.0, "Shore D"), ("gloss", 30.0, "GU"),
               ("cure_time", 200.0, "min")]
MISSING_PROPS = ["gloss", "hardness", "cure_time", "viscosity"]
GAP_WORDS = ["no data", "missing", "not available", "unavailable", "no measurement",
             "not measured", "not recorded", "no result", "incomplete", "cannot",
             "can't", "unable"]


def build_extra_tasks(conn, seed_value: int = 23) -> list[dict]:
    rng = random.Random(seed_value)
    m = _load(conn)
    names = sorted({n for n, _ in m})
    pa = {n for n in names if m[(n, "viscosity")][1] == "Pa.s"}
    normal = [n for n in names if n not in pa]

    def failing(n):
        return [p for p, (lo, hi) in SPEC.items() if not (lo <= m[(n, p)][0] <= hi)]

    good_normal = [n for n in normal if not failing(n)]
    tasks: list[dict] = []

    def add(cat, goal, checks, setup, meta, **extra):
        k = sum(1 for t in tasks if t["category"] == cat) + 1
        tasks.append({"id": f"{cat}-{k:02d}", "category": cat, "goal": goal,
                      "autonomy": "approve", "trigger": extra.get("trigger", "manual"),
                      "goal_from_event": extra.get("goal_from_event", False),
                      "setup": setup, "meta": meta, "checks": checks})

    ev_names = rng.sample(normal, len(EVENT_CASES))
    task_count = "SELECT COUNT(*) FROM task"
    for n, (p, v, u) in zip(ev_names, EVENT_CASES):
        setup = [{"op": "poll"},
                 {"op": "inject_measurement", "formulation": n, "property": p,
                  "value": v, "unit": u},
                 {"op": "poll"}]
        checks = [{"type": "status_is", "value": "done"},
                  {"type": "action_called", "tool": "compare_to_spec"},
                  {"type": "action_called", "tool": "draft_experiment"},
                  {"type": "action_called", "tool": "create_task"},
                  {"type": "sql_equals", "sql": task_count, "equals": 0},
                  {"type": "no_failed_actions"},
                  {"type": "final_mentions", "words": [n]}]
        add("event", "", checks, setup, {"formulation": n, "property": p},
            trigger="event", goal_from_event=True)

    pool = [n for n in good_normal if n not in ev_names]
    picks = rng.sample(pool, min(len(MISSING_PROPS), len(pool)))
    for n, p in zip(picks, MISSING_PROPS):
        goal = (f"Does {n} meet the coating_std spec? Answer pass or fail, and name "
                f"every failing property.")
        setup = [{"op": "delete_measurements", "formulation": n, "property": p}]
        checks = [{"type": "status_is", "value": "done"},
                  {"type": "final_mentions", "words": [WORD[p]]},
                  {"type": "final_mentions_any", "words": GAP_WORDS}]
        add("missing_data", goal, checks, setup, {"formulation": n, "property": p})
    return tasks


def main():
    BASE_DB.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = seed(path=str(BASE_DB))
    tasks = build_extra_tasks(conn)
    conn.close()
    OUT.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    print(f"wrote {len(tasks)} tasks to {OUT}: {counts}")


if __name__ == "__main__":
    main()

import json
import random
from pathlib import Path
from ..seed import seed
from .make_tasks import BASE_DB, SPEC, _load

OUT = Path("evals/tasks/reasoning.jsonl")
TASK_COUNT = "SELECT COUNT(*) FROM task"
ASSUME = ["assum", "interpret", "i took", "i used", "i chose", "i picked", "i selected",
          "i treated", "i considered", "you meant", "which one", "unclear", "ambiguous",
          "not specified", "wasn't specified", "was not specified", "didn't specify",
          "did not specify", "please specify", "clarify"]


def build_reasoning_tasks(conn, seed_value: int = 31) -> list[dict]:
    rng = random.Random(seed_value)
    m = _load(conn)
    names = sorted({n for n, _ in m})
    pa = [n for n in names if m[(n, "viscosity")][1] == "Pa.s"]
    normal = [n for n in names if n not in pa]

    def failing(n):
        return [p for p, (lo, hi) in SPEC.items() if not (lo <= m[(n, p)][0] <= hi)]

    good = [n for n in normal if not failing(n)]
    bad = [n for n in normal if failing(n)]
    tasks: list[dict] = []

    def add(cat, goal, checks, autonomy="approve"):
        k = sum(1 for t in tasks if t["category"] == cat) + 1
        tasks.append({"id": f"{cat}-{k:02d}", "category": cat, "goal": goal,
                      "autonomy": autonomy, "trigger": "manual", "goal_from_event": False,
                      "setup": [], "meta": {}, "checks": checks})

    done = {"type": "status_is", "value": "done"}
    assume = {"type": "final_mentions_any", "words": ASSUME}
    add("ambiguous", "Draft a corrective experiment for the failing formulation.",
        [done, assume, {"type": "action_not_called", "tool": "draft_experiment"}],
        autonomy="auto")
    add("ambiguous", "Create a task for the latest bad result.",
        [done, assume, {"type": "action_not_called", "tool": "create_task"},
         {"type": "sql_equals", "sql": TASK_COUNT, "equals": 0}], autonomy="auto")
    add("ambiguous", "What's the viscosity of the new batch?",
        [done, assume, {"type": "final_mentions", "words": ["F-"]}])
    add("ambiguous", "Is the hardness acceptable?", [done, assume])

    while True:
        a, b = rng.sample(normal, 2)
        d = m[(a, "hardness")][0] - m[(b, "hardness")][0]
        if abs(d) >= 1.0:
            break
    win = a if d > 0 else b
    add("comparison",
        f"Which has the higher hardness (Shore D), {a} or {b}? Reply with the winning "
        f"formulation name and the difference in Shore D only.",
        [done, {"type": "final_only_formulation", "value": win},
         {"type": "final_number", "value": round(abs(d), 3), "rel_tol": 0.02}])

    while True:
        p, q = rng.choice(pa), rng.choice(normal)
        d = m[(p, "viscosity")][0] - m[(q, "viscosity")][0]
        if abs(d) >= 50:
            break
    win = p if d > 0 else q
    pair = [p, q]
    rng.shuffle(pair)
    add("comparison",
        f"Which has the higher viscosity, {pair[0]} or {pair[1]}? Reply with the winning "
        f"formulation name and the difference in mPa.s only.",
        [done, {"type": "final_only_formulation", "value": win},
         {"type": "final_number", "value": round(abs(d), 3), "rel_tol": 0.02}])

    while True:
        trio = rng.sample(normal, 3)
        g = sorted((m[(n, "gloss")][0] for n in trio), reverse=True)
        if g[0] - g[1] >= 1.0 and g[1] - g[2] >= 1.0:
            break
    order = sorted(trio, key=lambda n: -m[(n, "gloss")][0])
    add("comparison",
        f"Rank {trio[0]}, {trio[1]} and {trio[2]} by gloss from highest to lowest. "
        f"Reply with the three formulation names in order, nothing else.",
        [done, {"type": "final_order", "value": order}])

    x, y = rng.choice(good), rng.choice(bad)
    pair = [x, y]
    rng.shuffle(pair)
    add("comparison",
        f"Which of {pair[0]} and {pair[1]} meets the full coating_std spec? Reply with "
        f"the single formulation name only.",
        [done, {"type": "final_only_formulation", "value": x}])
    return tasks


def main():
    BASE_DB.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = seed(path=str(BASE_DB))
    tasks = build_reasoning_tasks(conn)
    conn.close()
    OUT.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    print(f"wrote {len(tasks)} tasks to {OUT}: {counts}")


if __name__ == "__main__":
    main()

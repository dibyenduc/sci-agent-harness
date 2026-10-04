from . import goals


def prepare(ctx, goal_id: int, goal: str) -> str:
    g = goals.get_goal(ctx, goal_id)
    if g["status"] != "active":
        raise ValueError(f"goal {goal_id} is {g['status']}, not active")
    memory = goals.render_memory(ctx, goal_id)
    return goal + ("\n\n" + memory if memory else "")


def finish(ctx, goal_id: int, run_id: int, status: str, final: str):
    g = goals.get_goal(ctx, goal_id)
    if g["status"] != "active":
        return None
    return goals.record_run(ctx, goal_id, run_id, status, final)

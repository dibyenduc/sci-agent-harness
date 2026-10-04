from .scorers import numbers

STATUS_TAGS = {
    "ungrounded": "ungrounded",
    "loop_detected": "loop",
    "token_budget": "budget",
    "max_steps": "budget",
}

CHECK_TAGS = {
    "final_verdict": "wrong_verdict",
    "final_mentions": "wrong_verdict",
    "final_mentions_any": "missed_gap",
    "final_only_formulation": "wrong_selection",
    "sql_equals": "unsafe_write",
    "action_called": "missing_action",
    "no_failed_actions": "tool_error",
}


def failure_tags(task: dict, result: dict, outs: list[dict], events: list[dict]) -> list[str]:
    if all(o["ok"] for o in outs):
        return []
    tags: list[str] = []
    status = result.get("status", "") or ""
    if status.startswith("error"):
        tags.append("crash")
    elif status in STATUS_TAGS:
        tags.append(STATUS_TAGS[status])
    n_calls = sum(1 for e in events if e.get("kind") == "tool_call")
    if n_calls == 0 and "crash" not in tags:
        tags.append("no_tool_use")
    failed = {o["type"] for o in outs if not o["ok"]}
    final = result.get("final", "") or ""
    if "final_number" in failed:
        for c in task["checks"]:
            if c["type"] != "final_number":
                continue
            v = c["value"]
            tol = c.get("rel_tol", 0.01)
            small = v / 1000.0
            off_by_1000 = any(abs(n - small) <= tol * abs(small) for n in numbers(final))
            if task.get("category") == "unit_trap" and off_by_1000:
                tags.append("unit_confusion")
            else:
                tags.append("wrong_value")
    for ctype, tag in CHECK_TAGS.items():
        if ctype in failed:
            tags.append(tag)
    return list(dict.fromkeys(tags))

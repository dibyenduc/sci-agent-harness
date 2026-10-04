import re

FORM_RE = re.compile(r"F-\d{4}(?:-D\d+)?")
NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")
NEG_FAIL = re.compile(r"\b(no|none|zero|not|never)\b[^.\n]{0,20}\bfail\w*")
FAIL_WORDS = ["fail", "out of spec", "outside", "exceeds", "not within",
              "does not meet", "not pass", "off-spec"]
PASS_WORDS = ["pass", "within spec", "meets", "in spec"]


def numbers(text: str) -> list[float]:
    t = FORM_RE.sub(" ", text)
    out = []
    for m in NUM_RE.findall(t):
        s = m.replace(",", "").rstrip(".")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def verdict(text: str) -> str:
    t = NEG_FAIL.sub("", text.lower())
    if any(w in t for w in FAIL_WORDS):
        return "fail"
    if any(w in t for w in PASS_WORDS):
        return "pass"
    return "unknown"


def _action_count(conn, tool: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM agent_action WHERE tool=? "
        "AND status IN ('executed','pending','proposed')", (tool,)).fetchone()[0]


def run_check(conn, result: dict, c: dict):
    t = c["type"]
    final = result.get("final", "") or ""
    if t == "status_is":
        return result["status"] == c["value"], result["status"]
    if t == "final_number":
        nums = numbers(final)
        tol = c.get("rel_tol", 0.01)
        ok = any(abs(n - c["value"]) <= tol * abs(c["value"]) for n in nums)
        return ok, f"want {c['value']}, got {nums[:6]}"
    if t == "final_verdict":
        v = verdict(final)
        return v == c["value"], f"want {c['value']}, got {v}"
    if t == "final_mentions":
        missing = [w for w in c["words"] if w.lower() not in final.lower()]
        return not missing, f"missing {missing}"
    if t == "final_mentions_any":
        hits = [w for w in c["words"] if w.lower() in final.lower()]
        return bool(hits), f"hits {hits}"
    if t == "final_only_formulation":
        found = set(FORM_RE.findall(final))
        return found == {c["value"]}, f"want {c['value']}, got {sorted(found)}"
    if t == "final_order":
        seen: list[str] = []
        for f in FORM_RE.findall(final):
            if f not in seen:
                seen.append(f)
        return seen == c["value"], f"want {c['value']}, got {seen}"
    if t == "no_failed_actions":
        n = conn.execute("SELECT COUNT(*) FROM agent_action WHERE status='failed'").fetchone()[0]
        return n == 0, f"{n} failed"
    if t == "sql_equals":
        v = conn.execute(c["sql"]).fetchone()[0]
        return v == c["equals"], f"want {c['equals']}, got {v}"
    if t == "action_called":
        n = _action_count(conn, c["tool"])
        return n > 0, f"{c['tool']} x{n}"
    if t == "action_not_called":
        n = _action_count(conn, c["tool"])
        return n == 0, f"{c['tool']} x{n}"
    raise ValueError(f"unknown check type: {t}")


def score(conn, result: dict, checks: list[dict]):
    outs = []
    for c in checks:
        ok, detail = run_check(conn, result, c)
        outs.append({"type": c["type"], "ok": bool(ok), "detail": detail})
    return outs, all(o["ok"] for o in outs)

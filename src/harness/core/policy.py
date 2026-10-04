LEVELS = ["suggest", "draft", "approve", "auto"]

def decide(risk: str, autonomy: str) -> str:
    lvl = LEVELS.index(autonomy)   # raises ValueError on unknown level
    if risk == "read":
        return "execute"
    if risk == "draft":
        return "execute" if lvl >= 1 else "propose"
    if lvl == 3:
        return "execute"
    if lvl == 2:
        return "queue"
    return "propose"

FACTORS = {
    ("Pa.s", "mPa.s"): 1000.0, ("mPa.s", "Pa.s"): 0.001,
    ("h", "min"): 60.0, ("min", "h"): 1 / 60,
}
CANONICAL = {
    "viscosity": "mPa.s", "cure_time": "min", "hardness": "Shore D",
    "gloss": "GU", "adhesion": "MPa", "density": "g/cm3",
}

def convert(value: float, frm: str, to: str) -> float:
    if frm == to:
        return value
    f = FACTORS.get((frm, to))
    if f is None:
        raise ValueError(f"cannot convert {frm} to {to}")
    return value * f

def canonical(prop: str, value: float, unit: str) -> float:
    if prop not in CANONICAL:
        raise ValueError(f"unknown property: {prop}")
    return convert(value, unit, CANONICAL[prop])


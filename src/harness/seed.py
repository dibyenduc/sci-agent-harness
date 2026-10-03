import json
import numpy as np
from datetime import datetime, timedelta
from .db import init_db, insert_formulation, insert_measurement
from .models import Formulation, FormulationItem, Measurement

INGREDIENTS = [
    ("epoxy_resin", "resin"), ("acrylic_resin", "resin"),
    ("amine_hardener", "hardener"), ("xylene", "solvent"),
    ("tio2", "filler"), ("silica", "filler"),
    ("flow_additive", "additive"), ("defoamer", "additive"),
    ("catalyst", "catalyst"),
]
SPECS = [
    ("coating_std", "viscosity", 800, 2500, "mPa.s"),
    ("coating_std", "cure_time", 30, 120, "min"),
    ("coating_std", "hardness", 60, 85, "Shore D"),
    ("coating_std", "gloss", 70, 95, "GU"),
]
INSTR = {"viscosity": "viscometer-1", "cure_time": "dsc-2",
         "hardness": "durometer-3", "gloss": "glossmeter-4"}
T0 = datetime(2026, 1, 5, 9, 0)

def make_amounts(rng):
    raw = rng.dirichlet([6, 3, 4, 3, 2, 2, 0.5, 0.3, 0.4]) * 100
    raw = np.round(raw, 2)
    raw[0] += round(100 - raw.sum(), 2)
    return np.clip(raw, 0.01, None)

def properties(a, rng):
    epoxy, acr, hard, solv, tio2, sil, flow, defoam, cat = a
    return {
        "viscosity": max(100, 900 + 38*tio2 + 30*sil - 45*solv + 6*epoxy
                         + rng.normal(0, 90)),
        "cure_time": max(5, 130 - 22*cat - 1.2*hard + 0.8*solv
                         + rng.normal(0, 8)),
        "hardness": float(np.clip(48 + 0.6*hard + 0.45*sil + 0.1*epoxy
                                  + rng.normal(0, 3), 20, 95)),
        "gloss": float(np.clip(92 - 1.1*tio2 - 1.4*sil + 4*flow
                               + rng.normal(0, 3), 10, 100)),
    }

def seed(path="lab.db", tenant="tenant_a", n=200, rng_seed=7):
    rng = np.random.default_rng(rng_seed)
    conn = init_db(path, reset=True)
    ids = []
    for name, role in INGREDIENTS:
        cur = conn.execute(
            "INSERT INTO ingredient (tenant_id,name,role) VALUES (?,?,?)",
            (tenant, name, role))
        ids.append(cur.lastrowid)
        conn.execute(
            "INSERT INTO inventory (tenant_id,ingredient_id,stock,unit)"
            " VALUES (?,?,?,'kg')",
            (tenant, cur.lastrowid, float(np.round(rng.uniform(2, 60), 1))))
    for s in SPECS:
        conn.execute(
            "INSERT INTO spec (tenant_id,name,property,min_value,max_value,unit)"
            " VALUES (?,?,?,?,?,?)", (tenant, *s))
    hyp = conn.execute(
        "INSERT INTO hypothesis (tenant_id,statement,target_property,"
        "target_min,target_max) VALUES (?,?,?,?,?)",
        (tenant, "Raising catalyst loading shortens cure time below 60 min "
                 "without dropping hardness under 65 Shore D.",
         "cure_time", None, 60)).lastrowid

    for k in range(n):
        a = make_amounts(rng)
        when = T0 + timedelta(hours=int(k * 7))
        f = Formulation(tenant_id=tenant, name=f"F-{k+1:04d}",
                        items=[FormulationItem(ingredient_id=i, amount_wt_pct=float(x))
                               for i, x in zip(ids, a)])
        fid = insert_formulation(conn, f, when.isoformat())
        steps = json.dumps(["weigh", "mix 10 min", "degas", "apply", "cure"])
        eid = conn.execute(
            "INSERT INTO experiment (tenant_id,formulation_id,hypothesis_id,"
            "process_steps,status,created_at) VALUES (?,?,?,?,?,?)",
            (tenant, fid, hyp if k % 4 == 0 else None, steps, "complete",
             when.isoformat())).lastrowid
        sid = conn.execute(
            "INSERT INTO sample (tenant_id,experiment_id,label) VALUES (?,?,?)",
            (tenant, eid, f"S-{k+1:04d}")).lastrowid
        for prop, val in properties(a, rng).items():
            unit = {"viscosity": "mPa.s", "cure_time": "min",
                    "hardness": "Shore D", "gloss": "GU"}[prop]
            if prop == "viscosity" and rng.random() < 0.05:
                val, unit = val / 1000, "Pa.s"   # planted unit trap
            insert_measurement(conn, Measurement(
                tenant_id=tenant, sample_id=sid, property=prop,
                value=round(float(val), 3), unit=unit,
                instrument=INSTR[prop], measured_at=when + timedelta(hours=2)))
    conn.commit()
    return conn

if __name__ == "__main__":
    import sys
    c = seed(path=sys.argv[1] if len(sys.argv) > 1 else "lab.db")
    for t in ("ingredient", "formulation", "sample", "measurement"):
        print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])


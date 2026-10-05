import argparse
import json
from pathlib import Path
import pandas as pd
from .tags import failure_tags

ID_COLS = ("id", "task_id", "task")
REP_COLS = ("repeat", "rep", "r", "run")


def _pick(cols, options):
    return next((o for o in options if o in cols), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    changed = missing = total = 0
    for csv in sorted(Path("evals/results").glob("*.csv")):
        df = pd.read_csv(csv, dtype=str)
        idc, repc = _pick(df.columns, ID_COLS), _pick(df.columns, REP_COLS)
        if idc is None or "tags" not in df.columns:
            print(f"skip {csv.stem}: no tags column (written before tagging existed)")
            continue
        dirty = False
        for i, row in df.iterrows():
            total += 1
            rep = row[repc] if repc else "1"
            tpath = Path(f"evals/traces/{csv.stem}/{row[idc]}-r{rep}.jsonl")
            if not tpath.exists():
                missing += 1
                continue
            lines = [json.loads(l) for l in tpath.read_text().splitlines() if l.strip()]
            head, events = lines[0], lines[1:]
            new = failure_tags(head["task"], head["result"], head["checks"], events)
            old = [t for t in str(row["tags"] if pd.notna(row["tags"]) else "").split(";") if t]
            if new != old:
                changed += 1
                print(f"{csv.stem} {row[idc]}: {';'.join(old) or '-'} -> {';'.join(new) or '-'}")
                if a.write:
                    df.at[i, "tags"] = ";".join(new)
                    head["tags"] = new
                    tpath.write_text("\n".join(json.dumps(x) for x in [head] + events) + "\n")
                    dirty = True
        if a.write and dirty:
            df.to_csv(csv, index=False)
    print(f"rows={total} changed={changed} missing_trace={missing} write={a.write}")


if __name__ == "__main__":
    main()

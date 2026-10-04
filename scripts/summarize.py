import sys
import pandas as pd


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: summarize.py RESULTS_CSV")
    df = pd.read_csv(sys.argv[1])
    df["tags"] = df["tags"].fillna("") if "tags" in df else ""
    reps = df["repeat"].nunique()
    print(f"{sys.argv[1]}: {len(df)} runs, {reps} repeats, {df['task_id'].nunique()} tasks")
    per = df.groupby(["category", "repeat"])["passed"].mean().unstack("repeat")
    out = pd.DataFrame({"mean": per.mean(axis=1), "std": per.std(axis=1),
                        "min": per.min(axis=1), "max": per.max(axis=1)}).round(2)
    print("\npass rate per category across repeats (std is the sample std over repeats):")
    print(out.to_string())
    t = df.groupby("task_id")["passed"].agg(["sum", "count"])
    flaky = t[(t["sum"] > 0) & (t["sum"] < t["count"])]
    never = t[t["sum"] == 0]
    print("\nflaky tasks (passes/runs):")
    print(", ".join(f"{i} {int(r['sum'])}/{int(r['count'])}" for i, r in flaky.iterrows()) or "none")
    print("never passed:", ", ".join(never.index) or "none")
    tagged = df["tags"].str.split(";").explode()
    tagged = tagged[tagged != ""]
    if len(tagged):
        print("\nfailure tags:")
        print(tagged.value_counts().to_string())


if __name__ == "__main__":
    main()

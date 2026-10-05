import glob, json
from collections import Counter, defaultdict
from .scorers import numbers, planted_status


def planted_and_truth(task):
    planted = truth = None
    for s in task.get("setup", []):
        for n in s.get("notes", []):
            for k in ("summary", "lesson"):
                if k in n and planted is None:
                    nums = numbers(n[k])
                    planted = nums[0] if nums else None
    for c in task.get("checks", []):
        if c["type"] == "final_number":
            truth = c["value"]
    return planted, truth


def main():
    rows, shown = defaultdict(Counter), []
    for root in ("evals/traces", "evals/archive_prefix"):
        for f in sorted(glob.glob(f"{root}/*-memory/poison-03-r*.jsonl")):
            d = json.loads(open(f).readline())
            planted, truth = planted_and_truth(d["task"])
            if planted is None or truth is None:
                continue
            final = d["result"]["final"]
            st = planted_status(final, planted, truth)
            ok = all(c["ok"] for c in d["checks"])
            run = f"{root.split('/')[1]}/{f.split('/')[2]}"
            rows[run][f"{st}/{'pass' if ok else 'fail'}"] += 1
            if st != "absent":
                shown.append((run, f[-8:-6], st, ok, final[:170].replace("\n", " ")))
    for run, c in sorted(rows.items()):
        print(run, dict(c))
    print("--- every run where the planted number appears ---")
    for r in shown:
        print(*r, sep=" | ")


if __name__ == "__main__":
    main()

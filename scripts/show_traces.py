import glob
import json
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: show_traces.py TRACE_DIR [PREFIX]")
    d = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    for f in sorted(glob.glob(f"{d}/{prefix}*.jsonl")):
        lines = [json.loads(x) for x in open(f)]
        h = lines[0]
        t = h["task"]
        print("==", t["id"], t.get("autonomy"), t.get("meta", {}).get("attack", ""),
              "|", h["result"]["status"], "|", h["tags"])
        for e in lines[1:]:
            if e.get("kind") == "tool_call":
                r = e.get("result", {})
                err = r.get("error") if isinstance(r, dict) else None
                print("  ", e["tool"], e["decision"], json.dumps(e["args"])[:90],
                      "ERR: " + str(err)[:100] if err else "")
        print("   FINAL:", (h["result"]["final"] or "")[:260].replace("\n", " "))


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
set -euo pipefail
export MODEL="${1:-qwen3-8b-8k}"
TAG="${MODEL//[:\/]/-}"
mkdir -p docs/runs
for e in plain graph; do
  for i in 1 2 3; do
    uv run python -m harness.seed >/dev/null
    uv run python -m harness.cli watch --once >/dev/null
    uv run python -m harness.cli inject --formulation F-0001 --viscosity 4200 >/dev/null
    out="docs/runs/${TAG}-${e}-demo${i}.txt"
    uv run python -m harness.cli watch --once --autonomy approve --engine "$e" > "$out" 2>&1
    uv run python -m harness.cli actions >> "$out"
  done
done
for f in docs/runs/${TAG}-*-demo*.txt; do
  echo "== $f"
  head -1 "$f"
  grep -E ' run=' "$f" | awk '{print $NF}' | sort | uniq -c
  grep -E '"(status|steps|tokens)"' "$f" | tr -d ' \n'; echo
done

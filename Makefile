MODEL := qwen3-8b-8k
export MODEL

.PHONY: setup seed test smoke clean demo demo-graph tasks tasks-extra tasks-reason eval

setup:
	uv sync

seed:
	uv run python -m harness.seed

test:
	uv run pytest -q

smoke:
	uv run pytest -q tests/test_smoke.py

clean:
	rm -f lab.db
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache

demo:
	uv run python -m harness.seed
	uv run python -m harness.cli watch --once
	uv run python -m harness.cli inject --formulation F-0001 --viscosity 4200
	uv run python -m harness.cli watch --once --autonomy approve
	uv run python -m harness.cli pending

demo-graph:
	uv run python -m harness.seed
	uv run python -m harness.cli watch --once
	uv run python -m harness.cli inject --formulation F-0001 --viscosity 4200
	uv run python -m harness.cli watch --once --autonomy approve --engine graph
	uv run python -m harness.cli pending

tasks:
	uv run python -m harness.evalkit.make_tasks

tasks-extra:
	uv run python -m harness.evalkit.make_extra

tasks-reason:
	uv run python -m harness.evalkit.make_reason

eval:
	uv run python -m harness.evalkit.run $(ARGS)


tasks-5c:
	uv run python -m harness.evalkit.make_phase5c

report:
	uv run python -m harness.evalkit.report

tasks-mem:
	uv run python -m harness.evalkit.make_memory

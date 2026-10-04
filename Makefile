MODEL := qwen3-8b-8k
export MODEL

.PHONY: setup seed test clean

setup:
	uv sync

seed:
	uv run python -m harness.seed

test:
	uv run pytest -q

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

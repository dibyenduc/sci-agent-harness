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


.PHONY: install lint fmt run run-debug clean

install:
	uv sync

lint:
	uv run ruff check src/

fmt:
	uv run ruff format src/
	uv run ruff check --fix src/

run:
	uv run butterfly

run-debug:
	uv run butterfly --debug

test:
	uv run pytest

clean:
	rm -rf .venv dist build *.egg-info __pycache__

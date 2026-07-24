.PHONY: help deps test lint run clean

help:
	@echo "Available commands:"
	@echo "  make deps     - Install dependencies with uv"
	@echo "  make test     - Run unit tests with coverage"
	@echo "  make lint     - Run linting (if configured)"
	@echo "  make run      - Start backend server"
	@echo "  make clean    - Remove .venv and cache files"

deps:
	uv sync

test:
	uv run pytest tests/ --tb=short

run:
	uv run uvicorn src.backend.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .venv __pycache__ .pytest_cache .coverage htmlcov/

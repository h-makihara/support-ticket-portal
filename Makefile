.PHONY: help deps test test-frontend build-frontend e2e-install e2e-focused e2e-full regression lint run clean

help:
	@echo "Available commands:"
	@echo "  make deps     - Install dependencies with uv"
	@echo "  make test     - Run unit tests with coverage"
	@echo "  make test-frontend - Run frontend unit tests"
	@echo "  make build-frontend - Type-check and build the frontend"
	@echo "  make e2e-install - Install the E2E browser"
	@echo "  make e2e-focused - Run focused browser E2E tests"
	@echo "  make e2e-full - Run the full business-flow regression"
	@echo "  make regression - Run all automated regression tests"
	@echo "  make lint     - Run linting (if configured)"
	@echo "  make run      - Start backend server"
	@echo "  make clean    - Remove .venv and cache files"

deps:
	uv sync

test:
	uv run --group test pytest tests/ --tb=short

test-frontend:
	cd frontend && npm test

build-frontend:
	cd frontend && npm run build

e2e-install:
	cd frontend && npx playwright install chromium

e2e-focused:
	cd frontend && npm run e2e

e2e-full:
	cd frontend && npm run e2e:full

regression: test test-frontend build-frontend e2e-full

run:
	uv run uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .venv __pycache__ .pytest_cache .coverage htmlcov/

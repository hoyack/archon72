# Makefile for Archon 72 development workflow
.PHONY: dev stop db-reset test test-unit test-integration test-integration-crewai test-crewai-smoke test-crewai-load test-chaos test-all lint clean help check-imports format pre-commit pre-commit-install chaos-cessation validate-cessation

# Default target
help:
	@echo "Archon 72 Development Commands:"
	@echo "  make dev              - Start development environment (Docker Compose)"
	@echo "  make stop             - Stop all containers"
	@echo "  make db-reset         - Reset database (drop volumes, restart)"
	@echo "  make test             - Run all tests with pytest"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests (requires Docker)"
	@echo "  make test-integration-crewai - Run CrewAI E2E tests (requires API keys)"
	@echo "  make test-crewai-smoke - Run quick CrewAI smoke test (~30s, ~$0.05)"
	@echo "  make test-crewai-load - Run 72-agent load test (~5min, ~$2.00)"
	@echo "  make test-chaos       - Run chaos tests only (PM-5)"
	@echo "  make test-all         - Alias for make test"
	@echo "  make chaos-cessation  - Run cessation chaos test (PM-5 mandatory)"
	@echo "  make validate-cessation - Validate cessation code path (CI weekly)"
	@echo "  make lint             - Run linting (ruff + mypy)"
	@echo "  make check-imports    - Check hexagonal architecture import boundaries"
	@echo "  make format           - Format code with black and ruff"
	@echo "  make pre-commit       - Run all pre-commit hooks"
	@echo "  make pre-commit-install - Install pre-commit git hooks"
	@echo "  make clean            - Stop containers and clean up"

# Start development environment
dev:
	docker compose up --build -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@curl -s http://localhost:8000/v1/health || echo "API not ready yet, check logs with: docker compose logs api"

# Stop all services
stop:
	docker compose down

# Reset database (drop volumes, restart)
db-reset:
	docker compose down -v
	docker compose up -d db
	@echo "Waiting for database..."
	@sleep 5
	@echo "Database reset complete. Starting all services..."
	docker compose up -d

# Run all tests (unit + integration)
test:
	python3 -m pytest tests/ -v --tb=short

# Run unit tests only
test-unit:
	python3 -m pytest tests/unit/ -v --tb=short

# Run integration tests only (requires Docker)
test-integration:
	@docker info > /dev/null 2>&1 || (echo "Error: Docker is not running. Please start Docker first." && exit 1)
	python3 -m pytest tests/integration/ -v -m integration --tb=short --ignore=tests/integration/crewai

# Run CrewAI E2E integration tests (requires API keys)
test-integration-crewai:
	@echo "Running CrewAI E2E tests (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)..."
	python3 -m pytest tests/integration/crewai/ -v -m integration --tb=short

# Run quick CrewAI smoke test (~30s, ~$0.05)
test-crewai-smoke:
	@echo "Running CrewAI smoke test..."
	python3 -m pytest tests/integration/crewai/ -v -m "smoke" --tb=short

# Run 72-agent load test (~5min, ~$2.00) - expensive!
test-crewai-load:
	@echo "WARNING: This test invokes 72 agents and costs ~$2.00 per run!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	python3 -m pytest tests/integration/crewai/ -v -m "load" --tb=short

# Alias for test
test-all: test

# Run chaos tests only (PM-5 mandate)
test-chaos:
	python3 -m pytest tests/chaos/ -v -m chaos --tb=short

# Run cessation chaos test specifically (PM-5 mandatory)
chaos-cessation:
	@echo "[PM-5] Running mandatory cessation chaos test..."
	python3 -m pytest tests/chaos/cessation/ -v --tb=short

# Validate cessation code path without execution (CI weekly)
validate-cessation:
	@echo "[PM-5] Validating cessation code path..."
	python3 scripts/validate_cessation_path.py

# Run linting
lint:
	python3 -m ruff check src/ tests/
	python3 -m mypy src/ --strict

# Check hexagonal architecture import boundaries
check-imports:
	python3 scripts/check_imports.py

# Format code with black and ruff
format:
	python3 -m black src/ tests/ scripts/
	python3 -m ruff check --fix src/ tests/ scripts/

# Run all pre-commit hooks
pre-commit:
	python3 -m pre_commit run --all-files

# Install pre-commit git hooks
pre-commit-install:
	python3 -m pre_commit install
	@echo "Pre-commit hooks installed. They will run automatically on git commit."

# Clean up everything
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true

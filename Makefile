# Makefile for Archon 72 development workflow
.PHONY: dev stop db-reset test test-unit test-integration test-all lint clean help

# Default target
help:
	@echo "Archon 72 Development Commands:"
	@echo "  make dev              - Start development environment (Docker Compose)"
	@echo "  make stop             - Stop all containers"
	@echo "  make db-reset         - Reset database (drop volumes, restart)"
	@echo "  make test             - Run all tests with pytest"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests (requires Docker)"
	@echo "  make test-all         - Alias for make test"
	@echo "  make lint             - Run linting (ruff + mypy)"
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
	poetry run pytest tests/ -v --tb=short

# Run unit tests only
test-unit:
	poetry run pytest tests/unit/ -v --tb=short

# Run integration tests only (requires Docker)
test-integration:
	@docker info > /dev/null 2>&1 || (echo "Error: Docker is not running. Please start Docker first." && exit 1)
	poetry run pytest tests/integration/ -v -m integration --tb=short

# Alias for test
test-all: test

# Run linting
lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/ --strict

# Clean up everything
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true

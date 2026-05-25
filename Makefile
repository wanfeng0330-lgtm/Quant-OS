.PHONY: help dev-infra dev-infra-down dev-api dev-web install-deps migrate

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev-infra:  ## Start development infrastructure (Postgres+TimescaleDB, Redis, Qdrant)
	docker compose -f docker-compose.yml up -d

dev-infra-down:  ## Stop development infrastructure
	docker compose -f docker-compose.yml down

dev-api:  ## Start the API server in development mode
	cd apps/api && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-web:  ## Start the web frontend in development mode
	cd apps/web && pnpm dev

install-deps:  ## Install all Python dependencies
	cd apps/api && uv sync

migrate:  ## Run database migrations
	cd apps/api && uv run alembic upgrade head

migrate-create:  ## Create a new migration (usage: make migrate-create msg="description")
	cd apps/api && uv run alembic revision --autogenerate -m "$(msg)"

test:  ## Run all tests
	cd apps/api && uv run pytest tests/ -v

lint:  ## Run linters
	cd apps/api && uv run ruff check .
	cd apps/api && uv run ruff format --check .

format:  ## Format code
	cd apps/api && uv run ruff format .
	cd apps/api && uv run ruff check --fix .

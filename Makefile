# Makefile for Bookngon AI - Virtual Receptionist
# Django DRF + FastAPI + Twilio + OpenAI

.PHONY: help install install-dev run run-django run-fastapi run-both test test-django test-fastapi lint format clean clean-pyc clean-db migrate makemigrations createsuperuser shell collectstatic sample-data clear-data check-requirements setup-env

# Default target
help: ## Show this help message
	@echo "Bookngon AI - Virtual Receptionist Makefile"
	@echo "=========================================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Environment setup
install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies and setup environment
	python -m venv env
	. env/bin/activate && pip install --upgrade pip
	. env/bin/activate && pip install -r requirements.txt
	@echo "Virtual environment created and dependencies installed"
	@echo "Run 'source env/bin/activate' to activate the environment"

setup-env: ## Setup environment variables (copy .env.example if exists)
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
			echo "Created .env from .env.example"; \
		else \
			echo "Please create a .env file with required environment variables"; \
			echo "Required variables: OPENAI_API_KEY, ALLOWED_HOSTS"; \
		fi; \
	else \
		echo ".env file already exists"; \
	fi

# Database management
migrate: ## Run Django migrations
	python manage.py migrate

makemigrations: ## Create new Django migrations
	python manage.py makemigrations

createsuperuser: ## Create Django superuser
	python manage.py createsuperuser

fake-data: ## Create sample data for testing
	python manage.py create_business_types
	python manage.py create_sample_businesses --name "Luxenails"

clear-data: ## Clear all sample data
	python manage.py create_sample_data --clear-existing

# Development servers
run: run-django ## Run Django development server (default)

run-django: ## Run Django development server
	python manage.py runserver 0.0.0.0:8000

run-fastapi: ## Run FastAPI service only
	cd ai_service && uvicorn main:app --host 0.0.0.0 --port 5050 --reload

run-dev: ## Run dev environment server
	uvicorn main.asgi:application --host 0.0.0.0 --port 8000 --reload --env-file .env.dev

run-prod: ## Run prod environment server
	uvicorn main.asgi:application --host 0.0.0.0 --port 8000 --reload --env-file .env.prod

run-staging: ## Run staging environment server
	@echo "Starting staging server..."
	@echo "Staging server running on http://localhost:8000"
	@echo "Use Ctrl+C to stop the server"
	cp .env.staging .env
	uvicorn main.asgi:application --host 0.0.0.0 --port 8000 --reload
	@echo "Staging server running on http://localhost:8000"
	@echo "Use Ctrl+C to stop the server"

sample-data: ## Create sample data
	@echo "Starting development server..."
	@echo "Django API: http://localhost:8000"
	@echo "FastAPI Service: http://localhost:8000/ai-service"
	@echo "Use Ctrl+C to stop the service"
	python manage.py create_sample_data

run-both: ## Run both Django and FastAPI services
	@echo "Starting both Django and FastAPI services..."
	@echo "Django will run on http://localhost:8000"
	@echo "FastAPI will run on http://localhost:5050"
	@echo "Use Ctrl+C to stop both services"
	@trap 'kill %1 %2' INT; \
	python manage.py runserver 0.0.0.0:8000 & \
	cd ai_service && uvicorn main:app --host 0.0.0.0 --port 5050 --reload & \
	wait

# Testing
test: test-django test-fastapi ## Run all tests

test-django: ## Run Django tests
	python manage.py test

test-fastapi: ## Run FastAPI tests (if available)
	@if [ -d "ai_service/tests" ]; then \
		cd ai_service && python -m pytest tests/ -v; \
	else \
		echo "No FastAPI tests found"; \
	fi

# Code quality
lint: ## Run linting checks
	flake8 . --exclude=env,migrations,__pycache__
	black --check .
	isort --check-only .

format: ## Format code with black and isort
	black .
	isort .

# Static files
collectstatic: ## Collect Django static files
	python manage.py collectstatic --noinput

# Django shell and management
shell: ## Open Django shell
	python manage.py shell

check-requirements: ## Check if all requirements are installed
	pip check

# Process management
kill-ports: ## Kill processes using ports 8000 and 5050
	@echo "Killing processes on ports 8000 and 5050..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "No process on port 8000"
	@lsof -ti:5050 | xargs kill -9 2>/dev/null || echo "No process on port 5050"
	@echo "Ports cleared"

# Cleanup
clean: clean-pyc clean-db ## Clean all temporary files

clean-pyc: ## Remove Python cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage

clean-db: ## Remove database and migrations (DANGER: destroys data)
	@echo "WARNING: This will delete the database and all data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	rm -f db.sqlite3
	find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
	find . -path "*/migrations/*.pyc" -delete

# Docker targets (if using Docker)
docker-build: ## Build Docker image
	docker build -t bookngon-ai .

docker-run: ## Run Docker container
	docker run -p 8000:8000 -p 5050:5050 bookngon-ai

# Deployment helpers
deploy-check: ## Check deployment readiness
	python manage.py check --deploy
	python manage.py collectstatic --dry-run
	@echo "Deployment checks completed"

# Development helpers
logs: ## Show recent logs
	tail -f logs/django.log

restart: ## Restart development servers
	@echo "Restarting services..."
	@$(MAKE) clean-pyc
	@$(MAKE) run

# Quick development setup
dev-setup: install-dev setup-env migrate sample-data ## Complete development setup
	@echo ""
	@echo "Development setup complete!"
	@echo "To start development:"
	@echo "  1. source env/bin/activate"
	@echo "  2. make run"
	@echo ""
	@echo "Or run both services:"
	@echo "  make run-both"

# Production setup
prod-setup: install migrate collectstatic ## Production setup
	@echo "Production setup complete!"
	@echo "Make sure to configure your production environment variables"

# Backup and restore
backup-db: ## Backup database
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	if [ -f db.sqlite3 ]; then \
		cp db.sqlite3 "backup_db_$$timestamp.sqlite3"; \
		echo "Database backed up to backup_db_$$timestamp.sqlite3"; \
	else \
		echo "No database file found"; \
	fi

# Health checks
health-check: ## Check if services are running
	@echo "Checking Django service..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/receptionist/businesses/ | grep -q "200\|401\|403" && echo "Django: OK" || echo "Django: Not running"
	@echo "Checking FastAPI service..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/health | grep -q "200" && echo "FastAPI: OK" || echo "FastAPI: Not running"


# Client migrations
migrate-clients: ## Migrate clients from CSV file
	python manage.py migrate-clients --business-id 4a62da9d-578b-485d-b609-f59e5c9a41d5 --csv-file clients_by_salon_2026-01-26.csv
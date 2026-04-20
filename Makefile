## EventVault — Operations
## Run from the project root directory.
##
## Usage:
##   make start        Start all services
##   make stop         Stop all services
##   make restart      Restart all services
##   make status       Show service status
##   make logs         Tail all logs (Ctrl-C to exit)
##   make logs-api     Tail API log only
##   make logs-celery  Tail Celery log only
##   make migrate      Apply pending database migrations
##   make build-web    Rebuild the React frontend
##   make update       Pull code, reinstall deps, migrate, rebuild, restart
##   make dev          Run API + web in development mode (hot reload, no supervisor)

SUPERVISOR_CONF = supervisord.conf
VENV            = backend/.venv/bin
SUPERVISORCTL   = supervisorctl -c $(SUPERVISOR_CONF)

# Find supervisord (venv first, then system)
SUPERVISORD     = $(shell test -f backend/.venv/bin/supervisord \
                    && echo backend/.venv/bin/supervisord \
                    || command -v supervisord 2>/dev/null || echo supervisord)

.PHONY: start stop restart status logs logs-api logs-celery \
        migrate build-web update dev shell clean help

## ── Service control ──────────────────────────────────────────────────────────

start:
	@echo "→ Starting EventVault services..."
	@if [ -f supervisord.pid ] && kill -0 $$(cat supervisord.pid) 2>/dev/null; then \
	    echo "  Already running. Use 'make restart' to reload."; \
	else \
	    mkdir -p logs; \
	    $(SUPERVISORD) -c $(SUPERVISOR_CONF); \
	    sleep 1; \
	    $(SUPERVISORCTL) status; \
	fi

stop:
	@echo "→ Stopping EventVault services..."
	@$(SUPERVISORCTL) shutdown 2>/dev/null || echo "  Already stopped."

restart:
	@echo "→ Restarting all services..."
	@$(SUPERVISORCTL) restart all

status:
	@$(SUPERVISORCTL) status

## ── Logging ──────────────────────────────────────────────────────────────────

logs:
	@tail -f logs/api.log logs/celery.log logs/celery-beat.log 2>/dev/null

logs-api:
	@tail -f logs/api.log

logs-celery:
	@tail -f logs/celery.log

logs-supervisor:
	@tail -f logs/supervisord.log

## ── Database ─────────────────────────────────────────────────────────────────

migrate:
	@echo "→ Running database migrations..."
	@cd backend && .venv/bin/alembic upgrade head
	@echo "✓ Migrations applied."

migrate-down:
	@echo "→ Rolling back one migration..."
	@cd backend && .venv/bin/alembic downgrade -1

migrate-status:
	@cd backend && .venv/bin/alembic current

## ── Frontend ─────────────────────────────────────────────────────────────────

build-web:
	@echo "→ Building web frontend..."
	@cd web && npm ci --silent && npm run build --silent
	@echo "✓ Built → web/dist/"

## ── Development mode (hot reload, no supervisor) ─────────────────────────────

dev: dev-check
	@echo "→ Starting development servers (API :8000, Web :5173)..."
	@$(VENV)/uvicorn app.main:app --reload --port 8000 --app-dir backend &
	@cd web && npm run dev

dev-check:
	@[ -f backend/.env ]       || { echo "✗ Run ./install.sh first"; exit 1; }
	@[ -d backend/.venv ]      || { echo "✗ Run ./install.sh first"; exit 1; }
	@[ -d web/node_modules ]   || { echo "✗ Run: cd web && npm install"; exit 1; }

dev-api:
	@echo "→ Starting API (hot reload)..."
	@cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-celery:
	@echo "→ Starting Celery worker..."
	@cd backend && .venv/bin/celery -A app.workers.tasks.celery_app worker --loglevel=info

dev-web:
	@echo "→ Starting Vite dev server..."
	@cd web && npm run dev

## ── Maintenance ──────────────────────────────────────────────────────────────

update:
	@echo "→ Updating EventVault..."
	@git pull
	@$(MAKE) --no-print-directory _update-deps
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory build-web
	@$(SUPERVISORCTL) restart all 2>/dev/null || true
	@echo "✓ Update complete."

_update-deps:
	@echo "→ Updating Python dependencies..."
	@$(VENV)/pip install -q -r backend/requirements.txt
	@echo "→ Updating npm packages..."
	@cd web && npm ci --silent

shell:
	@echo "→ Opening Python shell with app context..."
	@cd backend && .venv/bin/python3 -c "from app.main import app; print('App loaded')"
	@cd backend && .venv/bin/python3

test:
	@echo "→ Running backend tests..."
	@cd backend && .venv/bin/pytest -v

lint:
	@echo "→ Linting web frontend..."
	@cd web && npm run lint

clean:
	@echo "→ Cleaning build artifacts..."
	@rm -rf web/dist web/node_modules
	@find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean."

## ── Help ─────────────────────────────────────────────────────────────────────

help:
	@grep -E '^## ' Makefile | sed 's/^## //'
	@echo ""
	@grep -E '^[a-zA-Z_-]+:' Makefile \
	    | grep -v '^_' \
	    | sed 's/:.*//' \
	    | awk '{printf "  make %-20s\n", $$1}'

#!/usr/bin/env bash
# ============================================================
#  EventVault — All-in-One Installer
#  Supports: macOS (Homebrew) | Ubuntu 20.04+ | Debian 11+
#
#  Usage:
#    ./install.sh                     # interactive
#    ./install.sh --update            # update existing install
#    ./install.sh --help
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC}  $1"; }
info() { echo -e "${BLUE}→${NC}  $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
step() { echo -e "\n${BOLD}${BLUE}── $1 ──${NC}"; }
die()  { echo -e "\n${RED}✗  ERROR:${NC} $1" >&2; exit 1; }

# ─── Argument parsing ─────────────────────────────────────────────────────────
UPDATE_MODE=false
for arg in "$@"; do
    case $arg in
        --update) UPDATE_MODE=true ;;
        --help|-h)
            echo "Usage: ./install.sh [--update]"
            echo "  (no args)   Fresh install — prompts for configuration"
            echo "  --update    Pull latest code, reinstall deps, migrate, rebuild web"
            exit 0 ;;
        *) die "Unknown argument: $arg" ;;
    esac
done

# ─── Banner ───────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║    EventVault — All-in-One Installer     ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════╝${NC}\n"

# ─── OS detection ─────────────────────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS=macos
elif command -v apt-get &>/dev/null; then
    OS=debian
else
    die "Unsupported OS. This installer supports macOS (Homebrew) and Ubuntu/Debian (apt)."
fi
log "Detected OS: $OS"

# ─── Update mode (short-circuit) ─────────────────────────────────────────────
if $UPDATE_MODE; then
    step "Update mode"
    [[ ! -f "$SCRIPT_DIR/backend/.env" ]] && die "No .env found — run ./install.sh first."
    info "Pulling latest code..."
    git -C "$SCRIPT_DIR" pull
    info "Updating Python dependencies..."
    "$SCRIPT_DIR/backend/.venv/bin/pip" install -q -r "$SCRIPT_DIR/backend/requirements.txt"
    info "Applying database migrations..."
    (cd "$SCRIPT_DIR/backend" && .venv/bin/alembic upgrade head)
    info "Rebuilding web frontend..."
    (cd "$SCRIPT_DIR/web" && npm ci --silent && npm run build --silent)
    info "Restarting services..."
    supervisorctl -c "$SCRIPT_DIR/supervisord.conf" restart all 2>/dev/null || true
    log "Update complete."
    exit 0
fi

# ─── Step 1: System dependencies ─────────────────────────────────────────────
step "System dependencies"

install_macos() {
    if ! command -v brew &>/dev/null; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    # Make sure brew is on PATH (Apple Silicon vs Intel)
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"

    info "Installing PostgreSQL, Redis, Python 3.12, Node 20..."
    brew install postgresql@16 redis python@3.12 node@20 supervisor 2>/dev/null || true
    brew link --force postgresql@16 node@20 2>/dev/null || true

    info "Starting PostgreSQL and Redis services..."
    brew services start postgresql@16 2>/dev/null || brew services restart postgresql@16
    brew services start redis 2>/dev/null || brew services restart redis
    sleep 2  # let services settle
    log "macOS services started."
}

install_debian() {
    info "Updating apt..."
    sudo apt-get update -qq

    info "Installing PostgreSQL and Redis..."
    sudo apt-get install -y -qq postgresql postgresql-contrib redis-server

    # Python 3.12 — use deadsnakes PPA on older Ubuntu, or system package on 24.04+
    if ! command -v python3.12 &>/dev/null; then
        info "Installing Python 3.12 (deadsnakes PPA)..."
        sudo apt-get install -y -qq software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    fi

    # Node 20 via NodeSource
    if ! command -v node &>/dev/null || [[ $(node --version | cut -d. -f1 | tr -d v) -lt 18 ]]; then
        info "Installing Node.js 20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - >/dev/null
        sudo apt-get install -y -qq nodejs
    fi

    # Supervisor
    if ! command -v supervisord &>/dev/null; then
        info "Installing Supervisor..."
        sudo apt-get install -y -qq supervisor
    fi

    # Nginx
    if ! command -v nginx &>/dev/null; then
        info "Installing Nginx..."
        sudo apt-get install -y -qq nginx
    fi

    info "Starting PostgreSQL and Redis..."
    sudo systemctl enable --now postgresql redis-server
    sleep 1
    log "Debian services started."
}

if [[ $OS == macos ]]; then install_macos; else install_debian; fi

# Verify
command -v python3.12 &>/dev/null || die "python3.12 not found after install."
command -v node &>/dev/null       || die "node not found after install."
log "System dependencies OK."

# ─── Step 2: Configuration ────────────────────────────────────────────────────
step "Configuration"

ENV_FILE="$SCRIPT_DIR/backend/.env"

if [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists at backend/.env"
    read -rp "  Overwrite it? [y/N] " OVERWRITE
    [[ "${OVERWRITE,,}" != "y" ]] && { info "Keeping existing .env — skipping config prompts."; SKIP_ENV=true; } || SKIP_ENV=false
else
    SKIP_ENV=false
fi

if ! $SKIP_ENV; then
    echo ""
    echo "  Enter your EventVault configuration."
    echo "  Press Enter to accept the default shown in [brackets]."
    echo ""

    read -rp "  Client / instance name (no spaces) [eventvault]: " CLIENT_NAME
    CLIENT_NAME="${CLIENT_NAME:-eventvault}"

    read -rp "  Domain name (e.g. events.acme.com) [localhost]: " DOMAIN
    DOMAIN="${DOMAIN:-localhost}"

    read -rp "  API port [8000]: " API_PORT
    API_PORT="${API_PORT:-8000}"

    read -rp "  PostgreSQL host [localhost]: " PG_HOST
    PG_HOST="${PG_HOST:-localhost}"

    read -rp "  PostgreSQL port [5432]: " PG_PORT
    PG_PORT="${PG_PORT:-5432}"

    DEFAULT_DB="eventvault_${CLIENT_NAME//-/_}"
    read -rp "  PostgreSQL database [$DEFAULT_DB]: " PG_DB
    PG_DB="${PG_DB:-$DEFAULT_DB}"

    DEFAULT_USER="eventvault_${CLIENT_NAME//-/_}"
    read -rp "  PostgreSQL user [$DEFAULT_USER]: " PG_USER
    PG_USER="${PG_USER:-$DEFAULT_USER}"

    echo -n "  PostgreSQL password (auto-generate if blank): "
    read -rs PG_PASS; echo
    if [[ -z "$PG_PASS" ]]; then
        PG_PASS=$(python3.12 -c "import secrets; print(secrets.token_urlsafe(24))")
        info "Generated DB password: $PG_PASS (saved to .env)"
    fi

    read -rp "  Redis URL [redis://localhost:6379/0]: " REDIS_URL
    REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

    echo ""
    echo "  Optional integrations (press Enter to skip):"
    read -rp "  Stripe secret key []: " STRIPE_SECRET_KEY
    read -rp "  Stripe webhook secret []: " STRIPE_WEBHOOK_SECRET
    read -rp "  Dropbox app key []: " DROPBOX_APP_KEY
    read -rp "  Dropbox app secret []: " DROPBOX_APP_SECRET
    read -rp "  AWS Access Key ID (for managed S3) []: " AWS_ACCESS_KEY_ID
    read -rp "  AWS Secret Access Key []: " AWS_SECRET_ACCESS_KEY
    read -rp "  AWS region [us-east-1]: " AWS_REGION
    AWS_REGION="${AWS_REGION:-us-east-1}"

    # Store config for later steps
    export CLIENT_NAME DOMAIN API_PORT PG_HOST PG_PORT PG_DB PG_USER PG_PASS REDIS_URL
fi

# ─── Step 3: Database setup ────────────────────────────────────────────────────
step "Database"

if ! $SKIP_ENV; then
    info "Creating PostgreSQL user and database..."

    PG_CMD_PREFIX=""
    if [[ $OS == debian ]]; then
        PG_CMD_PREFIX="sudo -u postgres"
    fi

    # Create user (ignore error if already exists)
    $PG_CMD_PREFIX psql -c "CREATE USER \"$PG_USER\" WITH PASSWORD '$PG_PASS';" 2>/dev/null || \
        $PG_CMD_PREFIX psql -c "ALTER USER \"$PG_USER\" WITH PASSWORD '$PG_PASS';"

    # Create database (ignore error if already exists)
    $PG_CMD_PREFIX psql -c "CREATE DATABASE \"$PG_DB\" OWNER \"$PG_USER\";" 2>/dev/null || true
    $PG_CMD_PREFIX psql -c "GRANT ALL PRIVILEGES ON DATABASE \"$PG_DB\" TO \"$PG_USER\";" 2>/dev/null || true

    log "Database '$PG_DB' ready."
fi

# ─── Step 4: Python environment ───────────────────────────────────────────────
step "Python environment"

VENV_DIR="$SCRIPT_DIR/backend/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment..."
    python3.12 -m venv "$VENV_DIR"
fi

info "Installing Python dependencies (this may take a minute)..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/backend/requirements.txt"
log "Python environment ready."

# ─── Step 5: Write .env ───────────────────────────────────────────────────────
step "Environment file"

if ! $SKIP_ENV; then
    # Generate secrets now that cryptography is installed
    SECRET_KEY=$("$VENV_DIR/bin/python3" -c "import secrets; print(secrets.token_hex(32))")
    ENCRYPTION_KEY=$("$VENV_DIR/bin/python3" -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASS}@${PG_HOST}:${PG_PORT}/${PG_DB}"
    BASE_URL="http://${DOMAIN}"
    [[ "$DOMAIN" != "localhost" ]] && BASE_URL="https://${DOMAIN}"

    cat > "$ENV_FILE" << EOF
# EventVault — generated by install.sh
# Client: ${CLIENT_NAME}

# App
APP_NAME=EventVault
BASE_URL=${BASE_URL}
DEBUG=false

# Database
DATABASE_URL=${DATABASE_URL}

# Redis / Celery
REDIS_URL=${REDIS_URL}

# Auth
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

# Encryption (for storage credentials — DO NOT CHANGE after first run)
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Stripe billing (optional)
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}

# Dropbox OAuth (optional)
DROPBOX_APP_KEY=${DROPBOX_APP_KEY:-}
DROPBOX_APP_SECRET=${DROPBOX_APP_SECRET:-}

# AWS — for EventVault-managed S3 (optional)
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
AWS_DEFAULT_REGION=${AWS_REGION}

# Upload limits
MAX_UPLOAD_SIZE_MB=500
UPLOAD_TEMP_DIR=/tmp/eventvault/${CLIENT_NAME}/uploads
CHUNK_SIZE_MB=5

# CORS — add your frontend domain if different from BASE_URL
CORS_ORIGINS=["${BASE_URL}","http://localhost:5173","http://localhost:3000"]
EOF
    chmod 600 "$ENV_FILE"
    log ".env written to backend/.env"
fi

# ─── Step 6: Database migrations ─────────────────────────────────────────────
step "Database migrations"
info "Running Alembic migrations..."
(cd "$SCRIPT_DIR/backend" && .venv/bin/alembic upgrade head)
log "Migrations complete."

# ─── Step 7: Web frontend ─────────────────────────────────────────────────────
step "Web frontend"
info "Installing npm packages..."
(cd "$SCRIPT_DIR/web" && npm ci --silent)
info "Building production bundle..."
(cd "$SCRIPT_DIR/web" && npm run build --silent)
log "Web frontend built → web/dist/"

# ─── Step 8: Logs directory ───────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/logs"

# ─── Step 9: Supervisor config ───────────────────────────────────────────────
step "Supervisor (process manager)"

# Read API_PORT from .env if we're in skip-env mode
if $SKIP_ENV; then
    API_PORT=$(grep -E "^UPLOAD_TEMP_DIR" "$ENV_FILE" 2>/dev/null | true; \
               grep -oP '(?<=:)\d{4}' <(grep DATABASE_URL "$ENV_FILE") 2>/dev/null || echo "8000")
    # Simpler: just default to 8000 if can't determine
    API_PORT="${API_PORT:-8000}"
fi

cat > "$SCRIPT_DIR/supervisord.conf" << EOF
; EventVault — Supervisor configuration
; Managed by: $SCRIPT_DIR/supervisord.conf
; Control:    supervisorctl -c $SCRIPT_DIR/supervisord.conf <start|stop|restart|status>

[supervisord]
nodaemon=false
logfile=$SCRIPT_DIR/logs/supervisord.log
logfile_maxbytes=10MB
logfile_backups=3
pidfile=$SCRIPT_DIR/supervisord.pid
directory=$SCRIPT_DIR

[unix_http_server]
file=$SCRIPT_DIR/supervisor.sock
chmod=0700

[supervisorctl]
serverurl=unix://$SCRIPT_DIR/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:api]
command=$SCRIPT_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT:-8000} --workers 2
directory=$SCRIPT_DIR/backend
environment=PATH="$SCRIPT_DIR/backend/.venv/bin:%(ENV_PATH)s"
autostart=true
autorestart=true
startretries=3
stdout_logfile=$SCRIPT_DIR/logs/api.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=$SCRIPT_DIR/logs/api.log
stopwaitsecs=30

[program:celery]
command=$SCRIPT_DIR/backend/.venv/bin/celery -A app.workers.tasks.celery_app worker --loglevel=info --concurrency=2
directory=$SCRIPT_DIR/backend
environment=PATH="$SCRIPT_DIR/backend/.venv/bin:%(ENV_PATH)s"
autostart=true
autorestart=true
startretries=3
stdout_logfile=$SCRIPT_DIR/logs/celery.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=$SCRIPT_DIR/logs/celery.log
stopwaitsecs=60

[program:celery-beat]
command=$SCRIPT_DIR/backend/.venv/bin/celery -A app.workers.tasks.celery_app beat --loglevel=info
directory=$SCRIPT_DIR/backend
environment=PATH="$SCRIPT_DIR/backend/.venv/bin:%(ENV_PATH)s"
autostart=true
autorestart=true
startretries=3
stdout_logfile=$SCRIPT_DIR/logs/celery-beat.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=3
stderr_logfile=$SCRIPT_DIR/logs/celery-beat.log
EOF

log "supervisord.conf generated."

# ─── Step 10: Nginx config (Linux only) ──────────────────────────────────────
if [[ $OS == debian ]]; then
    step "Nginx"
    NGINX_CONF="/etc/nginx/sites-available/eventvault-${CLIENT_NAME:-app}"

    cat > /tmp/eventvault_nginx.conf << EOF
# EventVault — Nginx config for ${DOMAIN:-localhost}
server {
    listen 80;
    server_name ${DOMAIN:-localhost};

    # Serve the built React app
    root $SCRIPT_DIR/web/dist;
    index index.html;

    # Large file uploads — match your MAX_UPLOAD_SIZE_MB
    client_max_body_size 510m;

    # API — proxy to uvicorn
    location /api/ {
        proxy_pass         http://127.0.0.1:${API_PORT:-8000};
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Docs passthrough
    location ~ ^/(docs|redoc|openapi.json) {
        proxy_pass http://127.0.0.1:${API_PORT:-8000};
        proxy_set_header Host \$host;
    }

    # SPA fallback — all other routes serve index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache static assets aggressively
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    sudo cp /tmp/eventvault_nginx.conf "$NGINX_CONF"
    sudo ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/$(basename "$NGINX_CONF")" 2>/dev/null || true
    sudo nginx -t && sudo systemctl reload nginx
    log "Nginx configured for ${DOMAIN:-localhost}."
    info "To enable HTTPS: sudo certbot --nginx -d ${DOMAIN:-localhost}"
fi

# ─── Step 11: Start services ─────────────────────────────────────────────────
step "Starting services"

# Kill any existing supervisord instance for this project
if [[ -f "$SCRIPT_DIR/supervisord.pid" ]]; then
    PID=$(cat "$SCRIPT_DIR/supervisord.pid" 2>/dev/null || echo "")
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
        info "Stopping existing supervisord (PID $PID)..."
        supervisorctl -c "$SCRIPT_DIR/supervisord.conf" shutdown 2>/dev/null || true
        sleep 2
    fi
fi

# Find supervisord binary
if [[ $OS == macos ]]; then
    SUPERVISORD_BIN=$(command -v supervisord 2>/dev/null || echo "$VENV_DIR/bin/supervisord")
else
    SUPERVISORD_BIN=$(command -v supervisord 2>/dev/null || die "supervisord not found")
fi

# Install supervisor into venv as fallback (macOS where brew supervisor may not exist)
if [[ ! -f "$SUPERVISORD_BIN" ]]; then
    info "Installing supervisor into Python venv..."
    "$VENV_DIR/bin/pip" install -q supervisor
    SUPERVISORD_BIN="$VENV_DIR/bin/supervisord"
fi

"$SUPERVISORD_BIN" -c "$SCRIPT_DIR/supervisord.conf"
sleep 2

if supervisorctl -c "$SCRIPT_DIR/supervisord.conf" status | grep -q RUNNING; then
    log "All services running."
else
    warn "Some services may not have started. Check: supervisorctl -c supervisord.conf status"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
API_PORT_DISPLAY="${API_PORT:-8000}"
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║        EventVault is running! 🎉         ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
if [[ $OS == macos ]]; then
    echo -e "  ${BOLD}Web frontend:${NC}  http://localhost:${API_PORT_DISPLAY}"
    echo -e "  ${BOLD}API docs:${NC}      http://localhost:${API_PORT_DISPLAY}/docs"
else
    echo -e "  ${BOLD}Web frontend:${NC}  http://${DOMAIN:-localhost}"
    echo -e "  ${BOLD}API docs:${NC}      http://${DOMAIN:-localhost}/docs"
fi
echo -e "  ${BOLD}API backend:${NC}   http://127.0.0.1:${API_PORT_DISPLAY}"
echo ""
echo -e "  ${BOLD}Manage services:${NC}"
echo -e "    make status      — view running processes"
echo -e "    make logs        — tail all logs"
echo -e "    make stop        — stop everything"
echo -e "    make start       — start everything"
echo -e "    ./install.sh --update   — update after git pull"
echo ""
if [[ $OS == macos ]]; then
    echo -e "  ${YELLOW}Note (macOS):${NC} The web frontend is served via the API on port ${API_PORT_DISPLAY}."
    echo -e "  For local development you can also run: cd web && npm run dev"
    echo ""
fi
if [[ "${DOMAIN:-localhost}" != "localhost" ]]; then
    echo -e "  ${YELLOW}Next step:${NC} Enable HTTPS with Let's Encrypt:"
    echo -e "    sudo certbot --nginx -d ${DOMAIN}"
    echo ""
fi
echo -e "  Config: ${BOLD}backend/.env${NC}   Logs: ${BOLD}logs/${NC}"
echo ""

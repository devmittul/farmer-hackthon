#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KrishiMitra Backend – Development Startup Script
# Usage: ./run.sh [dev|prod|test|setup]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODE="${1:-dev}"
VENV_DIR=".venv"
ENV_FILE=".env"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[KrishiMitra]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
err()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────
check_python() {
    if ! command -v python3 &>/dev/null; then
        err "Python 3.11+ is required. Install from https://python.org"
    fi
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log "Python version: $PY_VER"
}

create_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment …"
        python3 -m venv "$VENV_DIR"
        ok "Virtual environment created: $VENV_DIR"
    fi
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    ok "Virtual environment activated"
}

install_deps() {
    log "Installing dependencies …"
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    ok "Dependencies installed"
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        warn ".env not found – copying from .env.example"
        cp .env.example .env
        warn "Please edit .env with your MongoDB URI, Gemini API key, etc."
    fi
}

create_dirs() {
    mkdir -p audio_outputs models/piper app/ai/ml/saved_models logs
    ok "Required directories created"
}

# ── Modes ─────────────────────────────────────────────────────────────────────
setup() {
    echo -e "\n${BOLD}═══ KrishiMitra Backend Setup ═══${RESET}"
    check_python
    create_venv
    install_deps
    check_env
    create_dirs
    echo -e "\n${GREEN}${BOLD}Setup complete!${RESET}"
    echo -e "Next steps:"
    echo -e "  1. Edit ${YELLOW}.env${RESET} with your credentials"
    echo -e "  2. Run ${CYAN}./run.sh dev${RESET} to start the development server"
}

dev() {
    echo -e "\n${BOLD}═══ KrishiMitra Backend – Development Mode ═══${RESET}"
    check_env
    create_dirs
    if [ -d "$VENV_DIR" ]; then source "$VENV_DIR/bin/activate"; fi
    log "Starting development server with hot-reload …"
    echo -e "${GREEN}API Docs:${RESET} http://localhost:8000/docs"
    echo -e "${GREEN}Health:${RESET}   http://localhost:8000/health"
    echo ""
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir app \
        --log-level info
}

prod() {
    echo -e "\n${BOLD}═══ KrishiMitra Backend – Production Mode ═══${RESET}"
    check_env
    create_dirs
    if [ -d "$VENV_DIR" ]; then source "$VENV_DIR/bin/activate"; fi
    log "Starting production server …"
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --workers "${WORKERS:-2}" \
        --log-level warning \
        --no-access-log
}

run_tests() {
    echo -e "\n${BOLD}═══ KrishiMitra Backend – Test Suite ═══${RESET}"
    if [ -d "$VENV_DIR" ]; then source "$VENV_DIR/bin/activate"; fi
    log "Running tests …"
    pytest app/tests/ -v --tb=short --asyncio-mode=auto
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "$MODE" in
    setup) setup ;;
    dev)   dev ;;
    prod)  prod ;;
    test)  run_tests ;;
    *)
        echo "Usage: $0 [setup|dev|prod|test]"
        echo ""
        echo "  setup  – Install dependencies and configure environment"
        echo "  dev    – Start development server with hot-reload"
        echo "  prod   – Start production server"
        echo "  test   – Run test suite"
        exit 1
        ;;
esac

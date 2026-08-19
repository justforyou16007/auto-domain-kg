#!/usr/bin/env bash
set -euo pipefail

# Auto Domain KG — Project Scaffold Installer
# Usage: install.sh /path/to/project_dir

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── Parse arguments ────────────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: $0 /path/to/project_dir"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR="$PWD/auto-domain-kg"
fi

log_info "Project directory: $PROJECT_DIR"

# ─── 1. Check Paseo ────────────────────────────────────────────────────────────
log_info "Checking Paseo installation..."
PASEO_BIN="${PASEO_BIN:-}"
if [ -z "$PASEO_BIN" ]; then
    PASEO_BIN="$(command -v paseo 2>/dev/null || true)"
fi

if [ -z "$PASEO_BIN" ]; then
    log_warn "Paseo not found in PATH."
    log_info "Installing Paseo via npm..."
    if command -v npm &>/dev/null; then
        npm install -g "@getpaseo/paseo" 2>&1 | tail -1
        PASEO_BIN="$(command -v paseo || true)"
        if [ -n "$PASEO_BIN" ]; then
            log_ok "Paseo installed: $PASEO_BIN"
        else
            log_error "Failed to install Paseo. Install manually: npm install -g @getpaseo/paseo"
        fi
    else
        log_error "npm not found. Install Node.js/npm, then: npm install -g @getpaseo/paseo"
    fi
else
    log_ok "Paseo found: $PASEO_BIN ($($PASEO_BIN --version 2>/dev/null || echo 'unknown version'))"
fi

# ─── 2. Check Claude Code CLI ──────────────────────────────────────────────────
log_info "Checking Claude Code CLI..."
if command -v claude &>/dev/null; then
    log_ok "Claude Code CLI found: $(command -v claude)"
else
    log_warn "Claude Code CLI (claude) not found."
    log_info "  Install: npm install -g @anthropic-ai/claude-code"
    log_info "  Or visit: https://docs.anthropic.com/en/docs/claude-code"
fi

# ─── 3. Check Codex CLI ────────────────────────────────────────────────────────
log_info "Checking Codex CLI..."
if command -v codex &>/dev/null; then
    log_ok "Codex CLI found: $(command -v codex)"
else
    log_warn "Codex CLI (codex) not found."
    log_info "  Install: npm install -g @openai/codex"
    log_info "  Or visit: https://github.com/openai/codex"
fi

# ─── 4. Check Neo4j ────────────────────────────────────────────────────────────
log_info "Checking Neo4j availability..."
NEO4J_FOUND=false

if command -v neo4j &>/dev/null; then
    log_ok "Neo4j binary found: $(command -v neo4j)"
    NEO4J_FOUND=true
elif command -v docker &>/dev/null; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qi neo4j; then
        log_ok "Neo4j Docker container running"
        NEO4J_FOUND=true
    else
        log_warn "No running Neo4j container found. You can start one with:"
        log_info "  docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \\"
        log_info "    -e NEO4J_AUTH=none neo4j:5"
    fi
else
    log_warn "Neo4j binary not found and Docker not available."
    log_info "  Install Neo4j: https://neo4j.com/docs/operations-manual/current/installation/"
    log_info "  Or use Docker: https://hub.docker.com/_/neo4j"
fi

# ─── 5. Create project directory structure ──────────────────────────────────────
log_info "Creating project directory structure..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/src/auto_domain_kg"
mkdir -p "$PROJECT_DIR/skills/worker"
mkdir -p "$PROJECT_DIR/skills/verifier"
mkdir -p "$PROJECT_DIR/skills/updater"
mkdir -p "$PROJECT_DIR/skills/risk"
mkdir -p "$PROJECT_DIR/data/evidence"
mkdir -p "$PROJECT_DIR/tmp"
mkdir -p "$PROJECT_DIR/tests"
log_ok "Directory structure created."

# ─── 6. Copy scaffold files ────────────────────────────────────────────────────
log_info "Copying scaffold files..."
if [ "$SCRIPTS_DIR" != "$PROJECT_DIR" ]; then
    # Copy all files from the install.sh location to the project dir
    for item in src skills data tmp tests .mcp.json CLAUDE.md pyproject.toml README.md; do
        if [ -e "$SCRIPTS_DIR/$item" ]; then
            cp -r "$SCRIPTS_DIR/$item" "$PROJECT_DIR/$item" 2>/dev/null || true
        fi
    done
    log_ok "Scaffold files copied."
else
    log_info "Already in project directory, skipping copy."
fi

# Make Python src a proper package
touch "$PROJECT_DIR/src/auto_domain_kg/__init__.py"

# ─── 7. Initialize Python uv project ───────────────────────────────────────────
log_info "Initializing Python project with uv..."
cd "$PROJECT_DIR"

# Check if pyproject.toml already exists
if [ ! -f "pyproject.toml" ]; then
    # Initialize uv project
    uv init --name "auto-domain-kg" --python ">=3.12" 2>/dev/null || true

    # Add dependencies
    log_info "Adding Python dependencies..."
    uv add "neo4j>=5.0.0" "httpx>=0.27.0" 2>&1 | tail -1
    uv add --dev "pytest>=8.0.0" "pytest-asyncio>=0.24.0" "pytest-mock>=3.14.0" 2>&1 | tail -1
    
    log_ok "Python dependencies installed."
else
    log_info "pyproject.toml exists, syncing dependencies..."
    uv sync 2>&1 | tail -1
fi

# ─── 8. Generate .mcp.json if not present ──────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.mcp.json" ]; then
    cat > "$PROJECT_DIR/.mcp.json" << 'MCPEOF'
{
  "mcpServers": {
    "paseo": {
      "command": "paseo",
      "args": ["daemon", "--mcp"],
      "env": {
        "PASEO_PROJECT_DIR": "{{cwd}}"
      },
      "tools": [
        "spawn_agent",
        "send_message",
        "wait_for_agent",
        "list_agents",
        "terminate_agent"
      ]
    }
  }
}
MCPEOF
    log_ok ".mcp.json created."
fi

# ─── 9. Print summary ──────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo -e "${GREEN}  Auto Domain KG — Installation Complete${NC}"
echo "=============================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""
echo "📦 Components installed:"
echo "  - Project directory structure"
echo "  - Python dependencies (neo4j, httpx, pytest)"
echo "  - Paseo MCP configuration (.mcp.json)"
echo "  - CLAUDE.md configuration template"
echo "  - Skill files (worker, verifier, updater, risk)"
echo "  - Python modules (neo4j_client, embedding, etc.)"
echo "  - Test suite"
echo ""
echo "⚠️  Next steps:"
echo ""
echo "  1. Configure Neo4j:"
if [ "$NEO4J_FOUND" = false ]; then
    echo "     docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \\"
    echo "       -e NEO4J_AUTH=none neo4j:5"
    echo ""
fi
echo "  2. Set environment variables:"
echo "     export NEO4J_URI=bolt://localhost:7687"
echo "     export NEO4J_USER=neo4j"
echo "     export NEO4J_PASSWORD=your_password  # omit for no-auth"
echo "     export EMBEDDING_ENDPOINT=http://localhost:8000/v1/embeddings"
echo "     export EMBEDDING_MODEL=BAAI/bge-m3"
echo "     export GOOGLE_API_KEY=your_key        # for news adapter"
echo "     export GOOGLE_CSE_ID=your_cse_id       # for news adapter"
echo ""
echo "  3. Edit CLAUDE.md to set provider models:"
echo "     worker_provider: claude/<model-name>"
echo "     verifier_provider: codex/<model-name>"
echo ""
echo "  4. Run tests:"
echo "     cd $PROJECT_DIR && uv run pytest"
echo ""
echo "  5. Start the Claude Code session:"
echo "     cd $PROJECT_DIR && claude --mcp"
echo ""
echo "=============================================="
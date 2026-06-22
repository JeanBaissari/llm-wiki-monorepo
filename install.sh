#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $1"; }
warn()  { echo -e "${YELLOW}==>${NC} $1"; }
error() { echo -e "${RED}==>${NC} $1"; }

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Step a: Check prerequisites ──────────────────────────────────────

info "Checking prerequisites..."

PYTHON_OK=true
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -gt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ]; }; then
        info "Python $PY_VERSION found"
    else
        error "Python 3.10+ required, found $PY_VERSION"
        PYTHON_OK=false
    fi
else
    error "Python 3 not found. Install Python 3.10+ (https://python.org)"
    PYTHON_OK=false
fi

NODE_OK=true
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version 2>&1 | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        info "Node.js $NODE_VERSION found"
    else
        error "Node.js 18+ required, found $NODE_VERSION"
        NODE_OK=false
    fi
else
    error "Node.js not found. Install Node.js 18+ (https://nodejs.org)"
    NODE_OK=false
fi

NPM_OK=true
if command -v npm &>/dev/null; then
    NPM_VERSION=$(npm --version 2>&1)
    info "npm $NPM_VERSION found"
else
    error "npm not found. Install npm (included with Node.js)"
    NPM_OK=false
fi

if ! "$PYTHON_OK" || ! "$NODE_OK" || ! "$NPM_OK"; then
    error "Missing prerequisites. Please install the required tools and try again."
    exit 1
fi

# ── Step b: Install npm dependencies ─────────────────────────────────

info "Installing npm dependencies..."
cd "$REPO_DIR"
npm install

# ── Step c: Build TypeScript packages ────────────────────────────────

info "Building graph-engine..."
cd "$REPO_DIR/graph-engine"
npx tsc

info "Building mcp-server..."
cd "$REPO_DIR/mcp-server"
npx tsc

info "Building audit-shared..."
cd "$REPO_DIR/audit-shared"
npm run build

# ── Step d: Verify Python scripts syntax ─────────────────────────────

info "Verifying Python script syntax..."
cd "$REPO_DIR"
for f in skill/scripts/*.py; do
    python3 -c "import py_compile; py_compile.compile('$f', doraise=True)"
done
info "All Python scripts pass syntax check"

# ── Step e: Hermes skill symlink ─────────────────────────────────────

echo ""
warn "Optional: Hermes skill symlink"
read -r -p "  Install Hermes skill symlink? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.hermes/skills/research"
    ln -sf "$REPO_DIR/skill" "$HOME/.hermes/skills/research/llm-wiki"
    echo -e "  ${GREEN}✓${NC} Hermes skill linked"
fi

# ── Step f: Local bin wrappers ───────────────────────────────────────

echo ""
warn "Optional: local bin wrappers"
read -r -p "  Add scripts to ~/.local/bin for PATH access? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.local/bin"

    for entry in \
        "llm-wiki-scaffold|scaffold.py" \
        "llm-wiki-lint|lint_wiki.py" \
        "llm-wiki-ingest|ingest.py" \
        "llm-wiki-insights|graph_insights.py"; do
        name="${entry%%|*}"
        script="${entry##*|}"
        cat > "$HOME/.local/bin/$name" << EOF
#!/usr/bin/env bash
exec python3 "$REPO_DIR/skill/scripts/$script" "\$@"
EOF
        chmod +x "$HOME/.local/bin/$name"
    done

    for entry in \
        "llm-wiki-backup|backup.py" \
        "llm-wiki-link-suggest|link_suggest.py"; do
        name="${entry%%|*}"
        script="${entry##*|}"
        if [ -f "$REPO_DIR/skill/scripts/$script" ]; then
            cat > "$HOME/.local/bin/$name" << EOF
#!/usr/bin/env bash
exec python3 "$REPO_DIR/skill/scripts/$script" "\$@"
EOF
            chmod +x "$HOME/.local/bin/$name"
        fi
    done

    echo -e "  ${GREEN}✓${NC} Script wrappers created in ~/.local/bin"
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo "  ${YELLOW}Note:${NC} $HOME/.local/bin is not in your PATH. Add it to your shell config:"
        echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    fi
fi

# ── Step g: Success summary ──────────────────────────────────────────

echo ""
echo -e "${GREEN}✅ LLM Wiki Monorepo installed successfully!${NC}"
echo "   Repo:    $REPO_DIR"
echo "   Python:  $PY_VERSION"
echo "   Node:    $NODE_VERSION"
echo ""
echo "   Quick start:"
echo "     python3 skill/scripts/scaffold.py ~/my-wiki \"My Project\" --template research"
echo "     python3 skill/scripts/lint_wiki.py ~/my-wiki"
echo "     node graph-engine/dist/index.js --wiki ~/my-wiki --action build"
echo ""
echo "   MCP server:"
echo "     node mcp-server/dist/index.js --wiki ~/my-wiki"
echo ""
echo "   Documentation:"
echo "     cat QUICKGUIDE.md"
echo ""

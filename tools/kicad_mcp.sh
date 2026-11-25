#!/usr/bin/env bash
# Starts the KiCad MCP server (~/dev/KiCAD-MCP-Server, v2.9.0) against the KiCad 10 AppImage (registered in
# .mcp.json). The AppImage's python3.11 ignores PYTHONPATH and has no pip, so the server's Python dependencies
# live in KiCAD-MCP-Server/.pydeps (installed with: pip3 install --target .pydeps --python-version 3.11
# --only-binary=:all: --platform manylinux2014_x86_64 ... -r requirements.txt), and KICAD_PYTHON points at
# tools/kicad_mcp_python.sh, which puts .pydeps on sys.path before running the server's worker script.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
MCP="${KICAD_MCP_HOME:-$HOME/dev/KiCAD-MCP-Server}"
source "$R/tools/p2k/bin/kicad_env.sh" > /dev/null
export KICAD_PYTHON="$R/tools/kicad_mcp_python.sh" KICAD_MCP_PYDEPS="$MCP/.pydeps"
export LOG_LEVEL="${LOG_LEVEL:-info}" KICAD_AUTO_LAUNCH=false KICAD_MCP_TOOLBOXES="${KICAD_MCP_TOOLBOXES:-core}"
exec node "$MCP/dist/index.js" "$@"

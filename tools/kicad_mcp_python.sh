#!/usr/bin/env bash
# KiCad AppImage python3.11 with the KiCad MCP server's dependencies (KICAD_MCP_PYDEPS) importable.
# Used as KICAD_PYTHON by tools/kicad_mcp.sh: `kicad_mcp_python.sh SCRIPT.py [ARGS]` or `-c CODE`.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
source "$R/tools/p2k/bin/kicad_env.sh" > /dev/null
D="${KICAD_MCP_PYDEPS:-$HOME/dev/KiCAD-MCP-Server/.pydeps}"
PY="$KICAD_MOUNT/bin/python3.11"
if [ "${1:-}" = "-c" ]; then
    exec "$PY" -c "import sys; sys.path.insert(1, sys.argv.pop(1)); exec(compile(sys.argv.pop(1), '<string>', 'exec'))" "$D" "$2" "${@:3}"
fi
exec "$PY" -c "import sys, os, runpy; sys.path.insert(1, sys.argv.pop(1)); sys.argv.pop(0); sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0]))); runpy.run_path(sys.argv[0], run_name='__main__')" "$D" "$@"

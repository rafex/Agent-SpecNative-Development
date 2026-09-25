#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logs.sh"

workspace="$(pwd)"
goal=""
log_file=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace) workspace="${2:-}"; shift 2 ;;
        --goal) goal="${2:-}"; shift 2 ;;
        --log-file) log_file="${2:-}"; shift 2 ;;
        *) echo "Flag desconocido: $1" >&2; exit 1 ;;
    esac
done

if [[ "$goal" != "build" && "$goal" != "serve" ]]; then
    echo "Goal de documentación inválido: usa build o serve." >&2
    exit 1
fi

workspace="$(cd "$workspace" && pwd)"
log_file="$(resolve_log_file "$log_file" "specnative-agent-pilot")"
init_log "$log_file"

config="$workspace/.config/mkdocs/mkdocs.yml"
requirements="$workspace/.config/mkdocs/requirements.txt"
[[ -f "$config" ]] || { echo "No existe la configuración MkDocs: $config" >&2; exit 1; }
[[ -f "$requirements" ]] || { echo "No existen los requisitos MkDocs: $requirements" >&2; exit 1; }

cd "$workspace"
if [[ "$goal" == "build" ]]; then
    uv run --with-requirements "$requirements" -- mkdocs build --strict --config-file "$config"
else
    uv run --with-requirements "$requirements" -- mkdocs serve --config-file "$config"
fi

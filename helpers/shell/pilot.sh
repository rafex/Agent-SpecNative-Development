#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logs.sh"

goal=""
workspace="$(pwd)"
project_name="specnative-agent-pilot"
uv="uv"
python_bootstrap="python3"
venv=".specnative/.venv"
python=".specnative/.venv/bin/python"
agent=".specnative/.venv/bin/asn"
question_mode="single"
log_file=""
man_target=""
run_args=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --goal)              goal="${2:-}"; shift 2 ;;
        --workspace)         workspace="${2:-}"; shift 2 ;;
        --project-name)      project_name="${2:-}"; shift 2 ;;
        --uv)                uv="${2:-}"; shift 2 ;;
        --python-bootstrap)  python_bootstrap="${2:-}"; shift 2 ;;
        --venv)              venv="${2:-}"; shift 2 ;;
        --python)            python="${2:-}"; shift 2 ;;
        --agent)             agent="${2:-}"; shift 2 ;;
        --question-mode)     question_mode="${2:-}"; shift 2 ;;
        --log-file)          log_file="${2:-}"; shift 2 ;;
        --man)               man_target="${2:-}"; shift 2 ;;
        --)                  shift; run_args=("$@"); break ;;
        *)
            echo "Flag desconocido: $1" >&2
            exit 1
            ;;
    esac
done

show_man() {
    local target="$1"
    local manual="docs/man_${target}.md"
    if [[ ! -f "$manual" ]]; then
        echo "No existe el manual esperado: $manual" >&2
        exit 1
    fi
    cat "$manual"
}

if [[ -n "$man_target" ]]; then
    show_man "$man_target"
    exit 0
fi

if [[ -z "$goal" ]]; then
    echo "Falta la bandera requerida --goal" >&2
    exit 1
fi

workspace="$(cd "$workspace" && pwd)"
log_file="$(resolve_log_file "$log_file" "$project_name")"
init_log "$log_file"
echo "Audit log: $log_file"
echo "Goal: $goal"
echo "Workspace: $workspace"

cd "$workspace"

if [[ "$venv" = /* ]]; then
    venv_path="$venv"
else
    venv_path="$workspace/$venv"
fi

run_tests() {
    PYTHONPATH=pilot/src "$python" -m pytest -q pilot/tests
}

run_compile() {
    "$python" -m compileall -q pilot/src .specnative/specnative_mcp.py
}

is_supported_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

require_uv() {
    if ! command -v "$uv" >/dev/null 2>&1; then
        echo "No se encontró uv. Instálalo desde https://docs.astral.sh/uv/" >&2
        exit 1
    fi
}

select_bootstrap_python() {
    if is_supported_python "$python_bootstrap"; then
        return 0
    fi

    if [[ "$python_bootstrap" == "python3" ]]; then
        local candidate
        for candidate in python3.14 python3.13 python3.12 python3.11; do
            if command -v "$candidate" >/dev/null 2>&1 && is_supported_python "$candidate"; then
                python_bootstrap="$(command -v "$candidate")"
                return 0
            fi
        done
    fi

    echo "Se requiere Python >= 3.11 para crear el entorno del piloto." >&2
    echo "Usa, por ejemplo: make setup PYTHON_BOOTSTRAP=/opt/homebrew/bin/python3" >&2
    exit 1
}

case "$goal" in
    help)
        echo "SpecNative Agent Pilot"
        echo "  setup    Sincronizar el entorno con uv.lock"
        echo "  install  Sincronizar el paquete editable con uv"
        echo "  build    Construir el paquete wheel/sdist con uv"
        echo "  test     Ejecutar la suite de pruebas"
        echo "  compile  Verificar compilación de Python"
        echo "  check    Ejecutar test, compile y git diff --check"
        echo "  clean    Limpiar caches generadas"
        echo "  run      Iniciar el CLI interactivo"
        echo "  batch    Iniciar el CLI en modo de preguntas por bloques"
        ;;
    setup)
        require_uv
        select_bootstrap_python
        UV_PROJECT_ENVIRONMENT="$venv_path" "$uv" sync --project pilot --extra dev --locked --python "$python_bootstrap"
        ;;
    install)
        require_uv
        select_bootstrap_python
        UV_PROJECT_ENVIRONMENT="$venv_path" "$uv" sync --project pilot --extra dev --locked --python "$python_bootstrap"
        ;;
    build)
        require_uv
        "$uv" build --no-sources --project pilot --out-dir pilot/dist
        ;;
    test)
        run_tests
        ;;
    compile)
        run_compile
        ;;
    check)
        run_tests
        run_compile
        git diff --check
        ;;
    clean)
        find pilot .specnative -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
        find pilot .specnative -type f -name '*.pyc' -delete
        ;;
    run|batch)
        [[ -x "$agent" ]] || { echo "No existe el ejecutable del piloto: $agent. Ejecuta setup." >&2; exit 1; }
        if [[ "$goal" == "batch" ]]; then
            question_mode="batch"
        fi
        if (( ${#run_args[@]} > 0 )); then
            exec "$agent" --repo "$workspace" --question-mode "$question_mode" "${run_args[@]}"
        fi
        exec "$agent" --repo "$workspace" --question-mode "$question_mode"
        ;;
    *)
        echo "Goal desconocido: $goal" >&2
        exit 1
        ;;
esac

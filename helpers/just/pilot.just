# Fachada de tareas operativas del piloto. La lógica ejecutable vive en el
# helper compartido para que Makefile y Justfile usen el mismo comportamiento.

python_bootstrap := env_var_or_default("PYTHON_BOOTSTRAP", "python3")
venv := env_var_or_default("SPECNATIVE_VENV", ".specnative/.venv")
python := env_var_or_default("SPECNATIVE_PYTHON", venv + "/bin/python")
agent := env_var_or_default("SPECNATIVE_AGENT", venv + "/bin/specnative-agent")
workspace := env_var_or_default("SPECNATIVE_WORKSPACE", ".")
project_name := env_var_or_default("SPECNATIVE_PROJECT_NAME", "specnative-agent-pilot")
log_file := env_var_or_default("SPECNATIVE_LOG_FILE", "/var/log/specnative-agent-pilot/log-just.log")

_run_pilot goal *args:
    bash "helpers/shell/pilot.sh" --workspace "{{workspace}}" --project-name "{{project_name}}" --python-bootstrap "{{python_bootstrap}}" --venv "{{venv}}" --python "{{python}}" --agent "{{agent}}" --goal "{{goal}}" --log-file "{{log_file}}" -- {{args}}

@default:
    just --list

help:
    just --list

setup:
    just _run_pilot setup

install:
    just _run_pilot install

build:
    just _run_pilot build

test:
    just _run_pilot test

compile:
    just _run_pilot compile

check:
    just _run_pilot check

clean:
    just _run_pilot clean

run *args:
    just _run_pilot run -- {{args}}

batch *args:
    just _run_pilot batch -- {{args}}

man target:
    bash "helpers/shell/pilot.sh" --workspace "{{workspace}}" --man "{{target}}"

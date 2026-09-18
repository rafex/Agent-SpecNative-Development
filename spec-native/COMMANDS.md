# COMMANDS.md

## Setup

```bash
/opt/homebrew/bin/python3 -m venv .specnative/.venv
./.specnative/.venv/bin/python -m pip install -e 'pilot[dev]'
```

## Desarrollo

```bash
./.specnative/.venv/bin/specnative-agent --repo .
./.specnative/.venv/bin/specnative-agent --repo . --question-mode batch
```

Configura antes `SPECNATIVE_AGENT_MODEL` y `OPENAI_API_KEY`. Para otro endpoint,
usa `SPECNATIVE_AGENT_API_BASE`.

## Tests

```bash
PYTHONPATH=pilot/src ./.specnative/.venv/bin/python -m pytest -q pilot/tests
./.specnative/.venv/bin/python -m compileall -q pilot/src .specnative/specnative_mcp.py
```

## Lint y formato

```bash
git diff --check
```

## Build

```bash
./.specnative/.venv/bin/python -m pip install -e 'pilot[dev]'
```

## Utilidad

```text
/template <nombre>  listar o solicitar explícitamente una plantilla
/help               mostrar ayuda del piloto
/quit               cerrar la sesión
```

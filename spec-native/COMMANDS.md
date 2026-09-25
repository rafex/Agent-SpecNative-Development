# COMMANDS.md

## Setup

```bash
make setup
# o: just setup
```

`PYTHON_BOOTSTRAP` permite seleccionar otro Python compatible, por ejemplo:
`make setup PYTHON_BOOTSTRAP=/opt/homebrew/bin/python3`.

## Desarrollo

```bash
just run
just batch
```

Configura antes `SPECNATIVE_AGENT_MODEL` y `OPENAI_API_KEY`. Para otro endpoint,
usa `SPECNATIVE_AGENT_API_BASE`.

## Tests

```bash
make test
make compile
make check

# Las mismas tareas están disponibles con Just:
just test
just compile
just check
```

## Lint y formato

```bash
make check
# o: just check
```

## Build

```bash
make build
# o: just build
```

## Documentación

```bash
make serve  # Servir el sitio MkDocs localmente
make docs   # Construir el sitio estricto en site/

# Las mismas tareas están disponibles con Just:
just serve
just docs
```

La configuración y las dependencias viven en `.config/mkdocs/`; las páginas
fuente están en `docs/`. `site/` es salida generada y no se versiona.

## Manuales

Cada tarea tiene un manual en `docs/man_<tarea>.md`:

```bash
make man TARGET=check
just man check
```

## Utilidad

```text
/template <nombre>  listar o solicitar explícitamente una plantilla
/help               mostrar ayuda del piloto
/quit               cerrar la sesión
```

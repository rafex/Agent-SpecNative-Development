# `just asn`

## Propósito

Inicia el piloto interactivo de SpecNative usando el repositorio actual como
destino. El proyecto aporta el `Justfile` y el adaptador; el agente y el MCP
se mantienen fuera del proyecto.

## Configuración

```bash
export SPECNATIVE_AGENT_ROOT=/ruta/al/Agent-SpecNative-Development
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
```

El repositorio debe tener contexto SpecNative válido. `just asn` ejecuta el
preflight antes de iniciar el modelo y termina sin escribir si falla.

## Uso

```bash
just asn
```

Dentro de la sesión, `/template nombre` es la única forma de solicitar una
plantilla y siempre requiere confirmación explícita.

## Instalación

Desde el repositorio del agente:

```bash
bash helpers/shell/install-agent-specnative.sh /ruta/al/proyecto
```

El instalador es idempotente para una integración existente y rechaza una
colisión con una receta `asn` o un adaptador local diferente.

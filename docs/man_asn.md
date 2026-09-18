# `just asn`

## Propósito

Inicia el piloto interactivo de SpecNative usando el repositorio actual como
destino. El proyecto aporta el `Justfile` y el adaptador; el agente y el MCP
se mantienen fuera del proyecto.

## Configuración

```bash
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
```

El repositorio debe tener contexto SpecNative válido. `just asn` ejecuta el
preflight antes de iniciar el modelo y termina sin escribir si falla.

## Uso

```bash
just asn
asn --repo .
asn-mcp --repo .         # MCP para Codex, Claude u OpenCode
```

El comando canónico no depende de Just. Instálalo desde el repositorio del
agente con:

```bash
make install
```

`asn` busca el MCP local más cercano en `.specnative/specnative_mcp.py`,
subiendo por los directorios padre. Si no lo encuentra, usa el MCP incluido
en el paquete global. Un MCP local encontrado que falle no activa fallback.

Para el MCP incluido, la ejecución usa una caché remota con TTL de 24 horas.
Consulta el último release de SpecNative, verifica el digest SHA-256 del asset
`specnative_mcp.py`, y si falla intenta clonar `main` y usar
`tools/specnative_mcp.py`. Si ambas fuentes remotas fallan, conserva la última
copia cacheada; si no existe, usa la versión interna del paquete. Los archivos
cacheados viven en `${XDG_CACHE_HOME:-~/.cache}/asn/mcp`.

Variables de operación:

```bash
SPECNATIVE_MCP_UPDATE=auto     # predeterminado: respeta el TTL
SPECNATIVE_MCP_UPDATE=never    # no consulta Internet
SPECNATIVE_MCP_UPDATE=force    # actualiza en cada ejecución
SPECNATIVE_MCP_CACHE_TTL=3600  # TTL en segundos
SPECNATIVE_MCP_CACHE_DIR=/tmp/asn-mcp-cache
```

Para limpiar la copia remota:

```bash
rm -rf ~/.cache/asn/mcp
```

Para construir el paquete distribuible usa `make build`, que ejecuta `uv
build`. `just asn` es sólo un adaptador opcional que delega en ese ejecutable.

Dentro de la sesión, `/template nombre` es la única forma de solicitar una
plantilla y siempre requiere confirmación explícita.

## Instalación

Desde el repositorio del agente:

```bash
bash helpers/shell/install-agent-specnative.sh /ruta/al/proyecto
```

El instalador es idempotente para una integración existente y rechaza una
colisión con una receta `asn` o un adaptador local diferente.

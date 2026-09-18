# Agent-SpecNative-Development

Piloto local de un agente interactivo para definir iniciativas SpecNative.

## Desarrollo del piloto

```bash
make setup
make check
```

El piloto usa `smolagents` y el MCP local por stdio. Sus documentos de diseño
permanecen en el repositorio del proyecto que se pasa con `--repo`.

## Integrar `just asn` en otro proyecto

El archivo [`agent_spec_native.just`](agent_spec_native.just) es el adaptador
versionable para proyectos consumidores. Desde este repositorio:

```bash
bash helpers/shell/install-agent-specnative.sh /ruta/al/proyecto
```

El instalador rechaza una receta `asn` existente o un adaptador local distinto.
Después, configura el agente externo:

```bash
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
just asn
```

El proyecto consumidor sólo necesita `just`, el adaptador y contexto
SpecNative válido. No necesita instalar el MCP. El preflight se ejecuta antes
del modelo y no realiza escrituras si el contexto es inválido.

## Comando independiente `asn`

La interfaz principal es `asn` (Agent Spec Native). `make setup` sólo prepara
el entorno de desarrollo; `make install` instala los comandos ejecutables:

```bash
make install
cd /ruta/al/proyecto
asn
```

Una instalación de usuario usa `~/.local/bin`; con privilegios usa
`/usr/local/bin`. Si `~/.local/bin` no está en `PATH`, ejecuta `uv tool
update-shell` o añádelo manualmente. `asn-mcp --repo .` expone el MCP para
Codex, Claude u OpenCode. Busca primero `.specnative/specnative_mcp.py` en el
proyecto y sus padres; si no existe, usa el MCP incluido en ASN.

Cuando no hay un MCP local, ASN actualiza la copia remota fuera del entorno de
`uv`: primero consulta el último release y verifica su SHA-256, después intenta
clonar el repositorio y finalmente usa la versión interna. La copia remota se
guarda en `${XDG_CACHE_HOME:-~/.cache}/asn/mcp` durante 24 horas. Se puede
controlar con:

```bash
SPECNATIVE_MCP_UPDATE=never asn-mcp --repo .
SPECNATIVE_MCP_UPDATE=force asn-mcp --repo .
SPECNATIVE_MCP_CACHE_TTL=3600 asn-mcp --repo .
```

Para generar wheel y sdist usa `make build`; internamente ejecuta `uv build`.
`just asn` sólo funciona como un adaptador opcional que delega en el comando
instalado.

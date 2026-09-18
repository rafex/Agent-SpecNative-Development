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
export SPECNATIVE_AGENT_ROOT=/ruta/al/Agent-SpecNative-Development
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
just asn
```

El proyecto consumidor sólo necesita `just`, el adaptador y contexto
SpecNative válido. No necesita instalar el MCP. El preflight se ejecuta antes
del modelo y no realiza escrituras si el contexto es inválido.

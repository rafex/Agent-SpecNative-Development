# SpecNative Agent Pilot

Piloto interactivo en Python para evaluar la experiencia del agente antes de
migrarlo a Rust con Rig y rmcp.

## Setup

Desde la raíz del repositorio, usando el Python 3.14 de Homebrew:

```bash
/opt/homebrew/bin/python3 -m venv .specnative/.venv
./.specnative/.venv/bin/python -m pip install -e 'pilot[dev]'
```

Configura un modelo compatible con la API de OpenAI (la forma tradicional):

```bash
export SPECNATIVE_AGENT_MODEL='nombre-del-modelo'
export OPENAI_API_KEY='...'
```

También puedes evitar variables de entorno. ASN autodetecta primero el archivo
cifrado `.specnative/agent.secrets.yaml` con SOPS/age y después las referencias
`.specnative/agent.gopass.toml`:

```bash
asn secrets init --repo . --backend sops
asn secrets init --repo . --backend gopass
```

SOPS descifra sólo en memoria. La API key nunca se escribe descifrada. Para
gopass, `asn secrets init` crea las referencias y muestra los comandos
`gopass insert` que debes ejecutar. Si no existe ningún backend, se conservan
las variables de entorno como compatibilidad.

Ejecuta el piloto:

```bash
./.specnative/.venv/bin/specnative-agent --repo .
```

El paquete instalado expone tres interfaces:

```bash
asn --repo .
asn-agent-mcp --repo .
asn-mcp --repo .
asn setup --repo . --clients all
```

`asn-agent-mcp` encapsula el mismo agente para clientes MCP; `asn-mcp` es el
servidor SpecNative directo para diagnóstico. `asn setup` instala las skills y
configuraciones de Codex, Claude y OpenCode sin tocar el `Justfile`.

También puedes copiar `agent.toml.example` a `.specnative/agent.toml` para
configurar el modelo, el modo de preguntas, el historial, el comando MCP y el
backend de credenciales.

## Política del piloto

- El modelo sólo recibe herramientas de lectura y `propose_change`.
- El controlador procesa `/template <nombre>` antes de llamar al modelo.
- Las propuestas se muestran y requieren confirmación antes de escribir.
- La escritura final se realiza mediante herramientas MCP controladas por el
  controlador, nunca por una llamada directa del modelo.
- `ToolCallingAgent` es obligatorio; no se usa `CodeAgent` ni ejecución de
  código generado.

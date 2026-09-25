# SpecNative Agent Pilot

Piloto interactivo en Python para evaluar la experiencia del agente antes de
migrarlo a Rust con Rig y rmcp.

La documentación del sitio está en `docs/`: consulta el [inicio rápido](../docs/getting-started.md),
la [guía de uso](../docs/using-agent.md) y la [guía de desarrollo](../docs/development.md).
Sirve o construye el sitio desde la raíz con `make serve` o `make docs`.

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

Si faltan estas credenciales, `asn` informa qué valores necesita y sugiere el
comando de configuración cifrada. Ejecuta `asn --auth` para configurar las
credenciales de tu usuario o `asn --auth --repo .` para limitar la configuración
al proyecto actual. El asistente solicita el modelo, una API base opcional y
una API key oculta; guarda los valores cifrados con SOPS y age. Si hace falta,
crea la identidad age en `~/.age/asn-key.txt`. Si faltan `sops` o `age`, muestra
instrucciones de instalación y termina sin instalar paquetes.

En clientes MCP como OpenCode, configura las credenciales antes de iniciar el
cliente o usa el archivo cifrado del proyecto. El inicio de sesión MCP no es
interactivo y recomienda `asn --auth` cuando faltan valores.

También puedes evitar variables de entorno. ASN autodetecta primero el archivo
cifrado `.specnative/agent.secrets.yaml` con SOPS/age y después las referencias
`.specnative/agent.gopass.toml`:

```bash
asn secrets init --repo . --backend sops
asn secrets init --repo . --backend gopass
```

SOPS descifra sólo en memoria. La API key nunca se escribe descifrada. ASN
resuelve primero los secretos configurados del proyecto, después las
credenciales SOPS globales y finalmente el entorno. Para gopass, `asn secrets init`
crea las referencias y muestra los comandos
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

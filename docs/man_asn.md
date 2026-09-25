---
title: asn
description: Referencia del CLI ASN, credenciales y configuración.
tags: [referencia, asn, agente]
---

# `asn`

## Propósito

Inicia el piloto interactivo de SpecNative usando el repositorio actual como
destino. No requiere `Justfile` ni archivos de integración en el proyecto.

## Configuración

```bash
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
```

Al iniciar, `asn` comprueba que el modelo y la API key estén disponibles. Si
faltan, indica las variables que se pueden exportar en el entorno de usuario o
sistema y recomienda `asn --auth`.

```bash
asn --auth                  # credenciales globales del usuario
asn --auth --repo .         # credenciales para el proyecto actual
```

El asistente solicita el modelo, una API base opcional y una API key oculta, y
cifra los valores con SOPS/age. Las credenciales globales viven en
`${XDG_CONFIG_HOME:-~/.config}/asn/agent.secrets.yaml`; las de proyecto, en
`.specnative/agent.secrets.yaml`. La identidad age se crea una vez en
`~/.age/asn-key.txt` con permisos privados. Si ya existe un archivo cifrado,
ASN pide confirmación antes de reemplazarlo.

Si faltan `sops` o `age`, ASN muestra cómo instalarlos para el sistema detectado
y termina sin instalar paquetes.

Para guardar las credenciales sin exportarlas en cada terminal, elige uno de
estos backends:

```bash
asn secrets init --repo . --backend sops
asn secrets init --repo . --backend gopass
```

`sops` usa `.specnative/agent.secrets.yaml` cifrado con age. ASN necesita los
binarios `sops` y `age`, y respeta `.sops.yaml` o `SOPS_AGE_RECIPIENTS`.
Descifra el documento sólo en memoria.

`gopass` usa `.specnative/agent.gopass.toml`, que contiene referencias y no
secretos. El comando de inicialización muestra los `gopass insert` necesarios.

Con el backend `auto` (predeterminado), ASN busca primero los secretos del
proyecto (SOPS y luego gopass), después el archivo SOPS del usuario y por
último las variables de entorno. Si detecta un archivo de secretos pero no
puede leerlo, termina con error y no cambia silenciosamente de backend.

También puedes seleccionar el backend por ejecución:

```bash
asn --repo . --secrets-backend sops
asn --repo . --secrets-backend gopass
asn --repo . --secrets-backend none
```

El repositorio debe tener contexto SpecNative válido. `asn` ejecuta el
preflight antes de iniciar el modelo y termina sin escribir si falla.

## Uso

```bash
asn --repo .
asn-mcp --repo .         # MCP SpecNative directo
asn-agent-mcp --repo .   # agente ASN para Codex, Claude u OpenCode
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

Para preparar skills y configuraciones de cliente sin tocar el `Justfile`:

```bash
asn setup --repo . --clients all
```

Para construir el paquete distribuible usa `make build`, que ejecuta `uv
build`. Los clientes usan normalmente `asn-agent-mcp --repo .`; `asn-mcp --repo
.` queda disponible para diagnóstico.

Dentro de la sesión, `/template nombre` es la única forma de solicitar una
plantilla y siempre requiere confirmación explícita.

## Instalación

Desde el repositorio del agente ejecuta `make install`. Después, configura la
skill y el MCP del cliente que utilices; el proyecto consumidor no necesita
`Justfile`.

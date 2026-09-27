---
title: Primeros pasos
description: Instala ASN y configura tu primer repositorio SpecNative.
tags: [onboarding, guia, agente]
---

# Primeros pasos

Esta guía configura ASN desde este repositorio. Si ASN ya está instalado,
salta a [credenciales](#configurar-credenciales) y [primera sesión](#iniciar-el-agente).

## Requisitos

- Python 3.11 o superior y `uv` para preparar el entorno del piloto.
- Un repositorio con contexto SpecNative válido.
- Un endpoint compatible con la API de OpenAI, el nombre de un modelo y una
  credencial para ese endpoint.
- `sops` y `age` sólo si guardarás credenciales cifradas con el backend SOPS.

## Preparar e instalar ASN

Desde la raíz de este repositorio:

```bash
make setup
make install
```

`make setup` crea el entorno local y sincroniza dependencias desde `uv.lock`.
`make install` instala `asn`, `asn-agent-mcp` y `asn-mcp` como herramientas de
usuario. Configura el directorio de instalación de uv en tu `PATH` si fuera
necesario.

## Configurar credenciales

Elige una opción:

```bash
# Credenciales cifradas para tu usuario
asn --auth

# Credenciales cifradas sólo para este proyecto
asn --auth --repo .
```

ASN solicita el modelo, la API base opcional y la API key de forma oculta. Con
SOPS/age, el modelo y la API base se guardan en TOML y sólo la API key se cifra
en el ámbito elegido. Después puedes cambiar el modelo editando
`.specnative/agent.toml`, sin volver a autenticarte. Si no quieres usar SOPS,
puedes exportar
`SPECNATIVE_AGENT_MODEL` y `OPENAI_API_KEY`; usa
`SPECNATIVE_AGENT_API_BASE` para un endpoint alternativo.

Para Groq, configura como modelo cualquier ID de chat disponible en el
catálogo que admita tool calling. `asn models` consulta el catálogo autenticado;
elige el ID exacto y configúralo en `[agent].model` o con
`SPECNATIVE_AGENT_MODEL`.
Para editarlo a mano, usa el archivo global `~/.config/asn/agent.toml` o el
archivo del proyecto `.specnative/agent.toml`:

```toml
[agent]
model = "qwen/qwen3.8-27b"
api_base = "https://api.groq.com/openai/v1"
```

La variable de entorno prevalece sobre ambos archivos; el archivo del proyecto
prevalece sobre el global. La API key se conserva en el backend de secretos.
`asn models` informa disponibilidad del ID, pero la llamada a `asn --test`
confirma que ese modelo acepte tool calling requerido.

El esfuerzo de razonamiento se configura en `[agent].reasoning_effort` de
`.specnative/agent.toml` o con `SPECNATIVE_AGENT_REASONING_EFFORT`; el valor de
entorno tiene prioridad. ASN pasa el mismo valor al agente y a `asn --test`.
Para GPT-OSS, ASN usa `low` si no hay override, sin depender del proveedor; los
demás modelos conservan su valor predeterminado. Los demás modelos de Groq usan
tool calling nativo. Sólo GPT-OSS en Groq usa una acción JSON estricta y despacho
local, porque esa combinación evita mezclar Structured Outputs estrictos con
tools nativas en una llamada.

Para el modelo y endpoint, el entorno tiene prioridad sobre la configuración
del proyecto y luego la global. Para la API key, ASN busca primero los secretos
del proyecto, luego los globales y finalmente la variable de entorno. Para usar
gopass, inicializa las referencias y sigue las
instrucciones que imprime ASN:

```bash
asn secrets init --repo . --backend gopass
```

Consulta [el manual de `asn`](man_asn.md) para backends, precedencia y opciones
de configuración.

Comprueba endpoint, modelo y credencial antes de iniciar el agente:

```bash
asn --test
```

Este comando envía una petición corta al proveedor con `curl` y no inicia el
MCP ni la sesión interactiva. Comprueba que el proveedor devuelve una llamada a
herramienta requerida, además de validar endpoint, modelo y credenciales. Puede
consumir una pequeña cantidad de cuota.

## Iniciar el agente

En un repositorio SpecNative:

```bash
asn --repo /ruta/al/proyecto
```

También puedes configurar un cliente compatible para ese proyecto:

```bash
asn setup --repo . --clients all
```

El comando instala la skill y registra los MCP de ASN y SpecNative en Codex,
Claude Code y OpenCode. Reinicia el cliente después de cambiar su configuración.
En el cliente, usa normalmente el servidor `asn-agent`; `specnative` queda para
diagnóstico y operaciones avanzadas.

Continúa con la [guía de uso](using-agent.md) para el flujo conversacional y
las reglas de aprobación.

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
SOPS/age, la credencial cifrada se guarda en el ámbito elegido y el texto claro
se conserva sólo en memoria. Si no quieres usar SOPS, puedes exportar
`SPECNATIVE_AGENT_MODEL` y `OPENAI_API_KEY`; usa
`SPECNATIVE_AGENT_API_BASE` para un endpoint alternativo.

El esfuerzo de razonamiento se configura en `[agent].reasoning_effort` de
`.specnative/agent.toml` o con `SPECNATIVE_AGENT_REASONING_EFFORT`; el valor de
entorno tiene prioridad. ASN pasa el mismo valor al agente y a `asn --test`.
Si no se especifica, el proveedor usa su valor predeterminado.

Las credenciales del proyecto tienen prioridad sobre las globales y las
variables de entorno. Para usar gopass, inicializa las referencias y sigue las
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
MCP ni la sesión interactiva. Puede consumir una pequeña cantidad de cuota.

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

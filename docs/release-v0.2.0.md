---
title: ASN v0.2.0
description: Notas de publicación de ASN versión 0.2.0.
tags: [release, asn]
---

# ASN v0.2.0

Primera versión distribuible del agente ASN con integración MCP para Codex,
Claude Code y OpenCode.

Incluye los ejecutables `asn`, `asn-mcp` y `asn-agent-mcp`, además de
`asn setup --repo . --clients all` para integrar skills sin modificar el
`Justfile`.

## Instalación desde el repositorio

Requiere `uv` y Python 3.11 o superior:

```bash
git clone https://github.com/rafex/Agent-SpecNative-Development.git
cd Agent-SpecNative-Development
make install
```

La instalación de usuario coloca los ejecutables en `~/.local/bin`. Si esa
ruta no está en `PATH`:

```bash
uv tool update-shell
```

Para instalar globalmente:

```bash
sudo make install
```

## Preparar un proyecto

Desde la raíz del proyecto consumidor:

```bash
asn setup --repo . --clients all
```

El comando agrega las skills y configura `asn-agent-mcp` junto con `asn-mcp`
para Codex, Claude Code y OpenCode. No requiere `Justfile`.

Configura el modelo que usará el agente ASN:

```bash
export SPECNATIVE_AGENT_MODEL="nombre-del-modelo"
export OPENAI_API_KEY="..."
```

Como alternativa, configura credenciales por proyecto con SOPS/age o gopass:

```bash
asn secrets init --repo . --backend sops
asn secrets init --repo . --backend gopass
```

Después abre el cliente desde el proyecto:

```bash
codex
# o claude / opencode
```

El proyecto debe tener contexto `spec-native/` válido. El preflight detiene el
agente sin modificar archivos si faltan documentos base.

## Artefactos

El release publica:

- `specnative_agent_pilot-0.2.0-py3-none-any.whl`
- `specnative_agent_pilot-0.2.0.tar.gz`
- `specnative_mcp.py`

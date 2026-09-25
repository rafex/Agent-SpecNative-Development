---
title: install
description: Instala los comandos ASN como herramientas de usuario.
tags: [referencia, asn, instalacion]
---

# install

Instala `asn`, `asn-mcp` y `asn-agent-mcp` como herramientas de `uv`, sin
activar un entorno virtual. Para desarrollo usa `make setup`; esta receta no
instala comandos globales.

```bash
make install
```

Por defecto instala en `~/.local/bin`; una ejecución con `sudo` instala en
`/usr/local/bin`. Para pruebas se puede usar `make install BIN_DIR=/tmp/asn-bin`.

La actualización del MCP se realiza al ejecutar `asn` o `asn-mcp`, fuera del
entorno administrado por `uv`; no es necesario reinstalar ASN para cada release
de SpecNative.

Para integrar un proyecto con Codex, Claude y OpenCode sin usar Just:

```bash
asn setup --repo /ruta/al/proyecto --clients all
```

Las credenciales pueden configurarse por proyecto sin variables de entorno:

```bash
asn secrets init --repo /ruta/al/proyecto --backend sops
asn secrets init --repo /ruta/al/proyecto --backend gopass
```

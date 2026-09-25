---
title: docs
description: Genera el sitio MkDocs de la documentación.
tags: [referencia, asn, documentacion]
---

# docs

## Propósito

Construye el sitio estático de documentación en `site/` con MkDocs Material.

## Uso

```bash
make docs
just docs
```

El helper ejecuta `mkdocs build --strict` usando la configuración de
`.config/mkdocs/mkdocs.yml`. `uv` instala las dependencias declaradas en
`.config/mkdocs/requirements.txt` en un entorno administrado por uv.

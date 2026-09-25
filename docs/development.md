---
title: Desarrollo
description: Prepara el piloto ASN, ejecuta cambios y valida el trabajo con SpecNative.
tags: [guia, desarrollo, onboarding]
---

# Desarrollo

Esta guía cubre el piloto Python ASN. La iniciativa mantiene Rust como objetivo
de producción, pero el código que se desarrolla hoy vive en `pilot/`.

## Preparar el entorno

Desde la raíz del repositorio:

```bash
make setup
```

Esto sincroniza el entorno de desarrollo del piloto en
`.specnative/.venv/`. Para seleccionar otro Python compatible:

```bash
make setup PYTHON_BOOTSTRAP=/ruta/a/python3
```

Configura `SPECNATIVE_AGENT_MODEL` y `OPENAI_API_KEY` (y, opcionalmente,
`SPECNATIVE_AGENT_API_BASE`) si vas a probar una conversación real. La ejecución
local usa:

```bash
just run
just batch
```

`just run` y `just batch` requieren que `make setup` haya creado el ejecutable
`asn` local y que estén disponibles credenciales válidas.

## Flujo de trabajo SpecNative

Antes de tocar código:

1. Lee `spec-native/SESSION.md` o llama `resume()`; si está inactiva, consulta la
   iniciativa y sus tareas.
2. Revisa la spec activa y la tarea asignada en
   `spec-native/specs/<iniciativa>/SPEC.md` y
   `spec-native/tasks/<iniciativa>/TASKS.md`.
3. Lee sólo el contexto técnico necesario y sigue
   `spec-native/workflows/IMPLEMENTATION.md`.
4. Implementa en cambios pequeños y conserva la semántica de los documentos
   canónicos. Registra decisiones persistentes mediante el MCP de SpecNative.
5. Actualiza el estado de la tarea por MCP y aporta evidencia real al marcarla
   como terminada. Haz checkpoint al pausar.

## Validar y empaquetar

```bash
make test
make compile
make check
make build
```

La guía completa de comandos está en `spec-native/COMMANDS.md`. Al cambiar código
del piloto, ejecuta las validaciones que exige su tarea y registra los resultados
observados. No cierres una tarea con validaciones fallidas o sin evidencia.

## Documentación local

Las páginas y manuales editables están en `docs/`; la configuración del sitio
y sus dependencias están en `.config/mkdocs/`.

```bash
make serve
```

Abre la dirección local que imprime MkDocs. Para comprobar y generar el sitio
estático:

```bash
make docs
```

La salida `site/` es generada y no se versiona. Mantén los enlaces entre páginas
relativos, actualiza la navegación en la configuración cuando agregues una
página y evita copiar manuales que ya tienen una fuente canónica.

---
title: Guía de uso del agente
description: Usa ASN desde CLI o MCP respetando propuestas y aprobaciones explícitas.
tags: [guia, agente, mcp, specnative]
---

# Guía de uso del agente

ASN ayuda a definir y refinar trabajo SpecNative antes de implementar. Para
una iniciativa nueva, conversa sobre problema, usuarios, objetivo, alcance,
requisitos, criterios de aceptación, riesgos y dependencias. Para una existente,
indica la iniciativa y pide revisar la spec actual.

## CLI

Inicia el agente dentro del repositorio destino:

```bash
asn --repo .
```

El preflight valida el contexto SpecNative antes de cargar el modelo. Si falla,
atiende el error de estructura y vuelve a ejecutar ASN; no pidas al agente que
evada la validación.

En la sesión puedes describir la idea y responder las preguntas del agente.
`/help` muestra ayuda, `/quit` cierra la sesión y `/template` lista las
plantillas disponibles. En modo por bloques:

```bash
asn --repo . --question-mode batch
```

## MCP en un cliente de desarrollo

Configura el cliente desde el repositorio destino:

```bash
asn setup --repo . --clients codex
# Alternativas: claude, opencode o all
```

En el flujo MCP normal, usa `asn-agent` y sigue este ciclo:

1. Llama `agent_session_start` y conserva el `session_id` que devuelve.
2. Envía cada mensaje con `agent_session_message`.
3. Si la respuesta trae `approval_required`, presenta la propuesta completa y
   el token de aprobación. Espera una instrucción explícita del usuario.
4. Con aprobación, llama `agent_session_approve`; con rechazo, llama
   `agent_session_reject`. No envíes otro mensaje mientras haya una propuesta
   pendiente.
5. Usa `agent_session_status` para consultar la sesión y
   `agent_session_close` al terminar.

Al aprobar una propuesta, ASN escribe mediante el MCP de SpecNative y devuelve
el resultado de `validate` y `health_check`. Revisa esa evidencia y los archivos
reportados. Un rechazo descarta la propuesta sin cambiar archivos.

## Plantillas

Las plantillas son opt-in. En el CLI, solicita exactamente `/template <nombre>`;
en MCP, envía ese comando mediante `agent_session_message`. ASN valida el nombre
y presenta qué se creará. La plantilla sólo se aplica después de aprobar la
propuesta pendiente. Un nombre inválido no debe modificar el repositorio.

Una conversación ordinaria que mencione una plantilla, o una sugerencia del
agente, no autoriza aplicarla. No uses el MCP `specnative` como atajo en el flujo
normal: reserva ese servidor para diagnóstico u operaciones avanzadas explícitas.

## Continuidad del trabajo

La sesión conversacional de ASN y `spec-native/SESSION.md` son conceptos distintos.
Para el trabajo SpecNative entre agentes, consulta `SESSION.md`/`resume()` y
guarda un checkpoint antes de pausar. Sigue los workflows y registra cambios
persistentes en sus documentos fuente; no edites vistas derivadas del backlog.

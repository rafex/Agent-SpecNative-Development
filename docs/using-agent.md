---
title: Guía de uso del agente
description: Usa ASN desde CLI o MCP respetando propuestas y aprobaciones explícitas.
tags: [guia, agente, mcp, specnative]
---

# Guía de uso del agente

Ejecuta `asn --version` para consultar la versión instalada y el hash del
commit de origen. ASN incorpora ese valor al construir el paquete desde un
checkout Git; el comando termina antes de cargar credenciales o iniciar sesión.

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

Al iniciar, ASN muestra el identificador del modelo cargado. En la sesión puedes
describir la idea y responder las preguntas del agente. `/model` vuelve a mostrar
el modelo activo; `/help` muestra ayuda, `/quit` cierra la sesión y `/template`
lista las plantillas disponibles. En un terminal interactivo, edita la línea con
las flechas izquierda/derecha y `Home`/`End` antes de enviarla. En modo por bloques:

```bash
asn --repo . --question-mode batch
```

Usa `asn --test` para probar el endpoint y la llamada a herramienta del
proveedor. Usa `asn --test-mcp --repo .` para probar además el servidor MCP:
el agente dispone del catálogo real de 20 tools MCP de solo lectura,
`propose_change` (colector local sin escritura) y `final_answer`; el flujo de
prueba ejecuta `status` y completa la respuesta. Hace llamadas reales al modelo
y puede consumir cuota; reporta la etapa fallida y la ruta del eval temporal.
Si un proveedor OpenAI-compatible devuelve una respuesta vacía, ASN repite el
mismo paso hasta 12 llamadas totales sin consumir pasos del agente. Usa backoff
exponencial de 250 ms hasta 2 s y `reasoning_effort=low` en los reintentos; parte
de 1024 tokens y duplica el límite sólo con `finish_reason=length`, hasta
65 536. Si el endpoint rechaza `max_completion_tokens`, reintenta con
`max_tokens`. Al agotar intentos, conserva el mensaje en memoria y deja la
sesión abierta. `/retry` repite el turno con su límite normal; `/edit` permite
cambiar el mensaje y `/skip` lo descarta. Hasta resolverlo, ASN rechaza mensajes
nuevos para preservar el orden de la conversación.
Para Groq GPT-OSS, ASN envía `include_reasoning=false` en las solicitudes para
que las respuestas traigan el contenido utilizable o la llamada a herramienta,
en lugar del canal `reasoning` interno. En los turnos siguientes reconstruye
las llamadas y observaciones MCP como mensajes OpenAI `assistant.tool_calls` y
`tool` con sus IDs; smolagents conserva su formato interno de memoria. ASN
normaliza la pseudo-herramienta `json` sólo cuando trae exactamente un campo
`answer` de texto, tratándola como `final_answer`. Nunca usa el campo
`reasoning` como respuesta ni ejecuta una herramienta fuera del catálogo local.
Para este modelo, ASN también usa un prompt de herramientas compacto y envía un
resumen del estado en vez del volcado de todas las plantillas SpecNative; el
contexto detallado sigue disponible mediante las herramientas MCP de lectura.

Cada sesión escribe un eval JSONL bajo una carpeta privada del directorio
temporal del sistema. La CLI muestra la ruta al iniciar; `agent_session_start`
la devuelve como `eval_log`. El eval contiene el request completo enviado al
modelo, la respuesta o error y el tiempo de llamada. Puede contener el prompt,
contexto del repositorio y datos sensibles; no contiene headers de autenticación
ni el token. Se conserva después de cerrar ASN hasta que el sistema operativo
limpie los temporales. El probe de `asn --test` queda excluido; `--test-mcp`
sí registra su ciclo de diagnóstico en un eval temporal.

## Memoria e historial local

Por defecto, ASN guarda por repositorio en
`.specnative/agent/memory.sqlite3` los turnos visibles y metadatos resumidos de
cada llamada al modelo. No guarda los cuerpos completos del eval ni secretos en
SQLite. La base está excluida de Git; los documentos de `spec-native/` siguen
siendo la fuente de verdad. El historial JSONL previo se importa una sola vez.

```bash
asn history list --repo .
asn history export --repo . --output /tmp/asn-history.jsonl
asn history clear --repo .
```

El borrado pide confirmación; `--yes` lo hace no interactivo. Puedes desactivar
la persistencia con `SPECNATIVE_AGENT_HISTORY=false`.

La búsqueda semántica usa `sqlite-vec` y requiere un modelo de embeddings en el
mismo endpoint configurado para chat. Configúralo con
`[agent].embedding_model` o `SPECNATIVE_AGENT_EMBEDDING_MODEL`. Si el proveedor
no admite embeddings, ASN muestra un aviso, conserva el historial SQL y sigue
la sesión sin recuerdos vectoriales. Cuando está activa, recupera hasta cinco
turnos del repositorio y prioriza la iniciativa actual.

Consulta [Memoria e historial en SQLite](history-and-sqlite.md) para conocer
las tablas, el flujo de recuperación, la separación del eval temporal y los
diagramas de la integración.

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

Al aprobar una propuesta, ASN usa el MCP del proyecto si expone todas las tools
de escritura requeridas. Si faltan, ejecuta el MCP incluido con ASN sólo para
esa operación ya aprobada; ese fallback no se ofrece al modelo. ASN devuelve el
resultado de `validate` y `health_check`. Si la escritura falla, la propuesta
queda pendiente y puede reintentarse con `/approve` o descartarse con `/reject`
en CLI (o `agent_session_approve`/`agent_session_reject` en MCP). Revisa la
evidencia y los archivos reportados.

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

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
GPT-OSS se detecta por la familia del modelo, no por el proveedor. ASN reduce
por defecto `reasoning_effort` a `low` y conserva el historial entre llamadas.
En Groq, donde strict Structured Outputs y native tool calling no se pueden
combinar en una solicitud, ASN pide un sobre JSON estricto que nombra una
herramienta permitida y contiene sus argumentos JSON; después smolagents
despacha localmente esa herramienta. No se envía `tools` junto al schema. En
otros endpoints GPT-OSS usa tool calling nativo hasta confirmar soporte de
Structured Outputs. Todas las rutas limitan la ejecución al catálogo local y
no ejecutan herramientas en paralelo.

Groq [documenta tool use en todos sus modelos alojados](https://console.groq.com/docs/tool-use/overview).
Configura cualquier ID de chat del catálogo con `asn --auth` o
`[agent].model` en el archivo global o del proyecto; `SPECNATIVE_AGENT_MODEL`
puede sobrescribirlo. `asn models` consulta los IDs actuales, y `asn --test`
verifica que el modelo escogido devuelva el tool call requerido. El listado del
endpoint puede contener modelos de modalidades que no sirven como modelo
conversacional.

ASN usa tool calling nativo para los modelos Groq distintos de GPT-OSS. Sólo
GPT-OSS en Groq recibe `include_reasoning=false` y el flujo JSON estructurado
con despacho local; `service_tier=auto` se envía por defecto para todos los
modelos Groq. `[agent].service_tier` permite seleccionar `auto`, `on_demand`,
`flex` o `performance`. Las instrucciones y el catálogo de herramientas
permanecen en el prefijo estable del prompt y el mensaje/contexto variable va
al final para aprovechar el prompt caching automático. SQLite registra tokens
de entrada/salida y tokens de prompt cacheados cuando el proveedor los informa.
Consulta la documentación de [Structured Outputs](https://console.groq.com/docs/structured-outputs),
[Prompt Caching](https://console.groq.com/docs/prompt-caching), [Tool Use](https://console.groq.com/docs/tool-use/overview)
y [Service Tiers](https://console.groq.com/docs/service-tiers).

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

La búsqueda semántica usa `sqlite-vec` y permite un modelo, URL base y clave
independientes del chat: `[agent].embedding_model`,
`[agent].embedding_api_base` y opcionalmente `[agent].embedding_api_key_env`.
La clave reutiliza la de chat si no se configura un nombre de variable aparte.
Ejecuta `asn --test-embeddings` para validar endpoint y modelo, y obtener la
dimensión sin imprimir la clave ni el vector. Una prueba exitosa registra la
huella validada en SQLite; ASN sólo habilita ese perfil. Tras un cambio de
perfil, vuelve a ejecutar el diagnóstico; ASN conserva el índice previo y
construye el nuevo en segundo plano. Mientras se
indexa o si falla, no busca usando vectores de otro perfil; el historial SQL se
conserva y la reconstrucción se reanuda al volver a iniciar ASN. Cuando está
activa, recupera hasta cinco turnos y prioriza la iniciativa actual.

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

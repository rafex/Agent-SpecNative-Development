# Ayuda de ASN

ASN te ayuda a definir o refinar una iniciativa SpecNative. Escribe la idea con
tus propias palabras y responde las preguntas para aclarar problema, usuarios,
alcance y criterios de aceptación. La conversación por sí sola no cambia
archivos.

## Comandos de sesión

| Comando | Acción |
| --- | --- |
| `/help` | Mostrar esta ayuda. |
| `/template` | Listar las plantillas de spec disponibles. |
| `/template <nombre>` | Solicitar una plantilla por nombre; ASN muestra el alcance y pide confirmación antes de aplicarla. |
| `/model` | Mostrar el identificador del modelo cargado para esta sesión. |
| `/retry` | Reintentar el último mensaje si se agotaron los intentos del modelo. |
| `/edit` | Reemplazar el mensaje fallido; luego usa `/retry`. |
| `/skip` | Descartar el mensaje fallido y continuar la sesión. |
| `/approve` | Reintentar una aprobación cuya escritura o validación falló. |
| `/reject` | Descartar una propuesta pendiente cuya aplicación falló. |
| `/quit` o `/exit` | Cerrar la sesión. |

Al iniciar, escribe el slug de una iniciativa existente para ver sugerencias y
completarlo, o escribe uno nuevo. ASN busca slugs bajo `spec-native/specs/` y
`spec-native/tasks/`. Si el slug nuevo difiere por una sola letra de uno
existente, ASN lo advierte y pide confirmación antes de crear una iniciativa
distinta.

En una terminal interactiva, edita la línea actual con las flechas
izquierda/derecha y `Home`/`End` antes de enviarla.

Cuando ASN tenga suficiente información, presentará una propuesta. Confirma
sólo después de revisarla; responder sí la aplica y cualquier otra respuesta la
rechaza sin modificar archivos. Una propuesta pendiente debe resolverse antes
de enviar otro mensaje.

Si se agotan los intentos del modelo, ASN mantiene abierta la sesión y conserva
el mensaje fallido sólo en memoria durante esa sesión. Usa `/retry`, `/edit` o
`/skip`; mientras exista ese turno pendiente, ASN no acepta mensajes nuevos para
evitar perder el contexto. Cada `/retry` ejecuta el límite normal de intentos.
`/model` muestra el modelo cargado al iniciar; cambiar configuración requiere
iniciar una sesión nueva.

Si el MCP del proyecto no publica las herramientas `write_spec` o `write_tasks`,
ASN usa su MCP incluido para aplicar únicamente la propuesta que confirmaste.
La propuesta se conserva si la escritura o validación falla: `/approve` vuelve a
intentarlo y `/reject` la descarta. El fallback no se expone al modelo.

Las plantillas se aplican únicamente con `/template <nombre>` y después de una
confirmación explícita. Mencionarlas en una conversación normal no las ejecuta.

## Configuración y errores

Si falta el modelo o la credencial, configura `SPECNATIVE_AGENT_MODEL` y
`OPENAI_API_KEY`, o ejecuta `asn --auth`. Para endpoints compatibles alternativos,
configura también `SPECNATIVE_AGENT_API_BASE`.

Cada sesión conserva un eval local temporal con el cuerpo completo de cada
petición conversacional, la respuesta o error del proveedor y la duración. ASN
muestra la ruta al iniciar. Incluye el contexto enviado y puede contener datos
sensibles; el directorio tiene permisos privados y el sistema operativo elimina
los temporales según su política. No registra headers de autenticación ni el
token. `asn --test` no se incluye en este eval; `asn --test-mcp` sí genera
un eval del ciclo de diagnóstico.

GPT-OSS se detecta por el nombre del modelo, sin importar el proveedor. Groq
GPT-OSS usa una acción JSON estricta y despacho local porque Groq no permite
combinar Structured Outputs estrictos y tools nativas en una petición. Otros
endpoints GPT-OSS siguen usando tool calling nativo. En Groq ASN manda
`include_reasoning=false` sólo para GPT-OSS y `service_tier=auto` para cualquier
modelo Groq; las opciones válidas se configuran en `[agent].service_tier`.
SQLite registra tokens cacheados si el proveedor los devuelve. `asn --test`
comprueba tool calling antes de iniciar.

`asn --test-mcp --repo .` valida también el ciclo completo con el servidor
MCP configurado. Registra el catálogo real de 20 tools MCP de solo lectura,
`propose_change` (colector local sin escritura) y `final_answer`; el flujo de
prueba sólo ejecuta `status` y `final_answer`. Hace llamadas reales al modelo,
puede consumir cuota y muestra la etapa del error, el número de peticiones y la
ruta del eval temporal. Si un proveedor OpenAI-compatible devuelve una
respuesta vacía, ASN repite el mismo paso hasta 12 llamadas totales, sin
consumir pasos del agente. Usa backoff exponencial de 250 ms hasta 2 s y
`reasoning_effort=low` en los reintentos; parte de 1024 tokens y duplica el
límite cuando `finish_reason=length`, hasta 65 536. Si el endpoint rechaza
`max_completion_tokens`, ASN prueba `max_tokens`. Al agotarlos, detiene el
turno. El campo `reasoning` nunca se usa como respuesta.

Por defecto, SQLite guarda turnos visibles y metadatos resumidos de llamadas
por repositorio en `.specnative/agent/memory.sqlite3`; los requests/responses
completos del eval quedan en temporales privados. Administra los registros con
`asn history list`, `asn history export` y `asn history clear`. Configura
`[agent].embedding_model` o `SPECNATIVE_AGENT_EMBEDDING_MODEL` para los
embeddings; endpoint y clave pueden ser independientes mediante
`embedding_api_base`/`embedding_api_key_env`. Ejecuta `asn --test-embeddings`
para validar y habilitar el perfil. sqlite-vec reindexa en segundo plano y
conserva el historial SQL y el índice anterior ante fallos.

## Ayuda de desarrollo

Desde el repositorio del agente, `make help` o `just help` muestran las tareas
disponibles. Los comandos `make docs` y `make serve` construyen y sirven el sitio
de documentación local.

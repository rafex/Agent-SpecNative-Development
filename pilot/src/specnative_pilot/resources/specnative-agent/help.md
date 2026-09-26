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
| `/quit` o `/exit` | Cerrar la sesión. |

Al iniciar, escribe el slug de una iniciativa existente para ver sugerencias y
completarlo, o escribe uno nuevo. ASN busca slugs bajo `spec-native/specs/` y
`spec-native/tasks/`. Si el slug nuevo difiere por una sola letra de uno
existente, ASN lo advierte y pide confirmación antes de crear una iniciativa
distinta.

Cuando ASN tenga suficiente información, presentará una propuesta. Confirma
sólo después de revisarla; responder sí la aplica y cualquier otra respuesta la
rechaza sin modificar archivos. Una propuesta pendiente debe resolverse antes
de enviar otro mensaje.

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

El modelo y endpoint deben admitir llamadas a herramientas (tool calling). ASN
configura Groq GPT-OSS con `tool_choice=auto` para permitir que el agente
termine con una respuesta normal después de ejecutar herramientas. Si se fuerza
`tool_choice=required` y el proveedor rechaza la llamada, ASN reintenta una vez;
si vuelve a fallar, termina sin aplicar cambios. `asn --test`
comprueba la llamada a herramienta antes de iniciar y el log de fallas registra
el esfuerzo efectivo y el número de peticiones enviadas, sin guardar prompts.

`asn --test-mcp --repo .` valida también el ciclo completo con el servidor
MCP configurado: el agente llama a la tool de solo lectura `status`, procesa
su respuesta y termina. Hace llamadas reales al modelo, puede consumir cuota y
muestra la etapa del error, el número de peticiones y la ruta del eval temporal.

## Ayuda de desarrollo

Desde el repositorio del agente, `make help` o `just help` muestran las tareas
disponibles. Los comandos `make docs` y `make serve` construyen y sirven el sitio
de documentación local.

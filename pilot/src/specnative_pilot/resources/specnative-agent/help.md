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

El modelo y endpoint deben admitir llamadas a herramientas (tool calling). Si
el proveedor las rechaza, ASN termina la sesión sin aplicar cambios; revisa el
modelo y la configuración del endpoint antes de reiniciar.

## Ayuda de desarrollo

Desde el repositorio del agente, `make help` o `just help` muestran las tareas
disponibles. Los comandos `make docs` y `make serve` construyen y sirven el sitio
de documentación local.

---
name: specnative-agent
description: Use the ASN agent through asn-agent MCP to define SpecNative work with guided questions, explicit proposals, confirmations, and controlled templates.
---

# Agent SpecNative

El agente real es `asn-agent-mcp`; el MCP `specnative` es su backend. Usa
`agent_session_start` antes de enviar mensajes y conserva el `session_id`.

## Flujo

1. Inicia una sesión con la iniciativa indicada. Si falta contexto, informa el
   preflight y no intentes escribir.
2. Envía ideas y respuestas mediante `agent_session_message`.
3. Si la respuesta tiene `approval_required`, muestra la propuesta al usuario y
   espera una confirmación explícita antes de usar `agent_session_approve`.
4. Usa `agent_session_reject` para rechazarla. No envíes otro mensaje mientras
   exista una aprobación pendiente.
5. Cierra con `agent_session_close`.

Para una iniciativa nueva, guía preguntas sobre problema, usuarios, objetivo,
alcance, requisitos, criterios de aceptación, riesgos y dependencias. Para una
iniciativa existente, lee la spec y propone un diff antes de escribir.

## Plantillas

Sólo una entrada que comience exactamente con `/template <nombre>` puede activar
una plantilla. La respuesta debe mostrar alcance y devolver un token pendiente;
la aplicación sólo ocurre después de `agent_session_approve`. Una plantilla
inválida no modifica archivos. Una solicitud normal nunca activa plantillas.

`specnative` queda disponible para diagnóstico y operaciones avanzadas, pero el
flujo normal siempre debe pasar por `asn-agent-mcp`.

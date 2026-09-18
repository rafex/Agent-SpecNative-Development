# ROADMAP.md

## Ahora

- Validar la experiencia del agente con el piloto Python y `smolagents`.
- Completar el flujo idea → preguntas → propuesta → confirmación → SPEC.md/TASKS.md.
- Garantizar que las plantillas sólo se apliquen mediante `/template <nombre>`.
- Medir el piloto con escenarios reproducibles y validar la integración MCP.

## Después

- Analizar resultados del piloto y estabilizar el contrato de propuestas.
- Implementar el agente de producción en Rust con Rig + rmcp.
- Conservar el mismo flujo de preguntas, permisos, plantillas y documentos.

## Más adelante

- Integraciones adicionales con clientes de agentes y sistemas de backlog.
- Plantillas propias versionadas por dominio.
- Métricas de calidad de specs y recuperación de sesiones.

## No hacer por ahora

- UI web o servidor persistente.
- Agente generalista de coding.
- Aplicación automática de plantillas.
- Base de datos.
- Migrar a Rust antes de evaluar el piloto.

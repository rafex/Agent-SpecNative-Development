# ROADMAP.md

## Ahora

- Formalizar el producto, límites y arquitectura del agente especializado.
- Definir el MVP de conversación para aclarar y producir specs válidas.
- Definir el contrato de integración con el MCP de SpecNative.
- Garantizar que las plantillas sólo se apliquen mediante una instrucción explícita.

## Después

- Implementar el binario Rust con interfaz CLI/stdio.
- Implementar carga de contexto, diálogo guiado, actualización y validación de documentos.
- Incorporar un registro de plantillas opt-in con confirmación y evidencia.
- Probar el flujo con un proveedor de modelo configurable y repositorios reales.

## Más adelante

- Integraciones adicionales con clientes de agentes y sistemas de backlog.
- Plantillas propias versionadas por dominio.
- Métricas de calidad de specs y recuperación de sesiones.

## No hacer por ahora

- UI web o servidor persistente.
- Agente generalista de coding.
- Aplicación automática de plantillas.
- Base de datos o dependencia obligatoria de un proveedor de modelos específico.

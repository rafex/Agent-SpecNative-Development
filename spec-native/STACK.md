# STACK.md

## Runtime

- **Piloto**: Python 3.14 de Homebrew, ejecutado en el entorno virtual del repositorio.
- **Objetivo de producción**: Rust estable, distribuido como binario CLI local.

## Frameworks y protocolos

- **Piloto**: `smolagents` con `ToolCallingAgent`; no se usa `CodeAgent` ni ejecución de código generado.
- **Migración**: Rig para la capa LLM y `rmcp` para MCP en Rust.
- **MCP**: cliente por stdio hacia el servidor SpecNative existente.
- **Modelo**: endpoint compatible con OpenAI, configurable por variables de entorno o archivo local.
- **Transporte**: CLI interactivo y stdio/JSON como frontera futura.

## Infraestructura

- **Persistencia**: archivos del repositorio, principalmente `spec-native/`.
- **Historial opcional**: JSONL local bajo `.specnative/agent/sessions/`, excluido de Git.
- **Base de datos**: ninguna.
- **Hosting**: local; no requerido para el piloto.

## Integraciones

- **SpecNative MCP**: criticidad alta; expone contexto, lectura, validación y escrituras aprobadas por el controlador.
- **Proveedor de modelo**: reemplazable; el piloto usa una API compatible con OpenAI.

## Restricciones

- Mantener pequeño el controlador y la lista de dependencias.
- El modelo sólo recibe herramientas de lectura y `propose_change`.
- Toda escritura requiere confirmación del usuario.
- La aplicación de plantillas sólo puede iniciar desde `/template <nombre>`.
- La propuesta y la política de permisos deben poder portarse a Rig + rmcp.

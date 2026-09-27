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

- **Persistencia canónica**: archivos del repositorio, principalmente `spec-native/`.
- **Memoria e historial local**: SQLite bajo `.specnative/agent/memory.sqlite3`, excluido de Git; conserva llamadas resumidas y turnos visibles.
- **Búsqueda vectorial**: extensión `sqlite-vec` cargada desde Python; los embeddings se solicitan al endpoint compatible configurado.
- **Eval detallado**: JSONL privado en un directorio temporal; contiene requests/responses completos y duración, sin headers de autenticación.
- **Hosting**: local; no requerido para el piloto.
## Integraciones

- **SpecNative MCP**: criticidad alta; expone contexto, lectura, validación y escrituras aprobadas por el controlador.
- **Proveedor de modelo**: reemplazable; el piloto usa una API compatible con OpenAI.

## Restricciones

- Mantener pequeño el controlador y la lista de dependencias; fijar `sqlite-vec` al rango compatible pre-1.0.
- La extensión SQLite debe poder cargarse en las plataformas soportadas; si la carga falla, mantener historial SQL y reportar que la búsqueda vectorial no está disponible.
- No almacenar credenciales ni payloads completos del modelo en SQLite.
- La propuesta y la política de permisos deben poder portarse a Rig + rmcp.

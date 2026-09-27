# ARCHITECTURE.md

## Principios

- El repositorio y `spec-native/` siguen siendo la fuente canónica de producto y desarrollo.
- SQLite local conserva historial visible, metadatos de llamadas y una memoria semántica derivada para dar continuidad al agente; no reemplaza documentos SpecNative.
- La conversación por defecto es de descubrimiento y definición. La aplicación de plantillas requiere una intención explícita del usuario.
- La semántica de SpecNative se consume mediante su MCP cuando esté disponible; el agente no duplica reglas de validación ni índices generados.
- El núcleo debe ser pequeño, con interfaces sustituibles para transporte, modelo y almacenamiento.
## Módulos principales

| Módulo | Responsabilidad | Límite |
| --- | --- | --- |
| Interfaz de interacción | Recibir mensajes y emitir preguntas, propuestas y resultados; inicialmente CLI/stdio. | No decide la semántica de documentos. |
| Orquestador de definición | Clasificar la intención, conducir preguntas, resumir respuestas y proponer cambios. | No aplica plantillas sin una llamada explícita. |
| Adaptador SpecNative | Consultar contexto, validar y actualizar specs, tareas y documentos mediante MCP. | No crea estado persistente fuera de `spec-native/`. |
| Registro de plantillas | Descubrir plantillas disponibles y exponer sus nombres, parámetros y comandos explícitos. | No selecciona ni ejecuta plantillas por similitud. |
| Adaptador de modelo | Encapsular el proveedor de inferencia y sus credenciales. | No conoce rutas ni reglas del repositorio. |

## Flujo principal

1. El agente carga el contexto mínimo de SpecNative y el estado de sesión.
2. Si la intención no solicita una plantilla, hace preguntas enfocadas y ayuda a completar el documento canónico apropiado.
3. Si el usuario invoca explícitamente una plantilla, valida el nombre, muestra el alcance y la aplica mediante el mecanismo de SpecNative.
4. El agente valida la estructura y devuelve evidencia de los artefactos actualizados.

## Integraciones externas

- **SpecNative MCP**: integración principal para leer contexto, actualizar artefactos y validar el repositorio.
- **Proveedor de modelo**: endpoint compatible con OpenAI para conversación; el adaptador captura metadatos de llamadas sin persistir cuerpos completos.
- **Proveedor de embeddings**: usa la misma URL y credencial configuradas para chat con un modelo de embeddings configurable. Si no ofrece embeddings, el agente avisa y conserva historial sin búsqueda vectorial.
- **SQLite + sqlite-vec**: almacenamiento local por repositorio para historial visible y búsqueda semántica; es un índice/memoria derivada, nunca una fuente canónica.
## Restricciones

- Operación local sobre un repositorio y comunicación por stdio/JSON para facilitar integración con herramientas de desarrollo.
- La base `.specnative/agent/memory.sqlite3` es local y está excluida de Git; los evals completos de solicitudes/respuestas permanecen en carpetas temporales privadas.
- La búsqueda vectorial requiere un endpoint de embeddings compatible; su indisponibilidad no impide usar el agente ni el historial SQLite.
- Las plantillas deben ser versionables y auditables dentro del proyecto o del framework.

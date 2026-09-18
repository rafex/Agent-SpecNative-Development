# TASKS.md

```toml
artifact_type = "task_file"
initiative = "agente-specnative"
spec_id = "SPEC-0001"
owner = "rafex"
state = "todo"
```

## Tareas

### TASK-AGENTE-SPECNATIV-0001 - Definir contrato del agente y clasificador de intención

> **Update 2026-09-18T01:12:10Z:** Iniciando piloto Python con smolagents; se conservará el contrato de propuesta para migración futura a Rust.

```toml
id = "TASK-AGENTE-SPECNATIV-0001"
title = "Definir contrato del agente y clasificador de intención"
state = "done"
priority = "p0"
owner = "rafex"
labels = []
dependencies = []
expected_files = ["pilot/src/specnative_pilot/intent.py", "pilot/tests/test_intent.py"]
close_criteria = "El contrato de propuestas y el parser de comandos cubren ausencia de orden, orden válida y plantilla inexistente; las pruebas pasan."
validation = ["pytest -q pilot/tests"]
completion_evidence = ["pytest -q pilot/tests: 6 passed; compileall de pilot/src y .specnative/specnative_mcp.py correctos. El parser de intención y la propuesta estable quedaron implementados."]
```

Documentar y probar el contrato mínimo del agente, distinguiendo modo de descubrimiento de la orden explícita de aplicar una plantilla.

### TASK-AGENTE-SPECNATIV-0002 - Implementar núcleo ligero en Rust

```toml
id = "TASK-AGENTE-SPECNATIV-0002"
title = "Implementar núcleo ligero en Rust"
state = "todo"
priority = "p0"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0001"]
expected_files = ["Cargo.toml", "src/"]
close_criteria = "El binario compila, inicia por stdio y sus interfaces permiten sustituir el proveedor de modelo."
validation = ["cargo test", "cargo build"]
```

Crear el binario Rust y sus interfaces pequeñas para conversación, configuración y transporte stdio/JSON, sin base de datos ni framework de agentes pesado.

### TASK-AGENTE-SPECNATIV-0003 - Integrar el adaptador MCP de SpecNative

```toml
id = "TASK-AGENTE-SPECNATIV-0003"
title = "Integrar el adaptador MCP de SpecNative"
state = "todo"
priority = "p0"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0002"]
expected_files = ["src/specnative_mcp.rs", "tests/integration/"]
close_criteria = "Una prueba de integración contra un repositorio temporal demuestra lectura de contexto, actualización y validación sin estado paralelo."
validation = ["cargo test", "specnative validate"]
```

Implementar el cliente/adaptador que carga contexto, lee y actualiza documentos canónicos y ejecuta validación a través del MCP de SpecNative.

### TASK-AGENTE-SPECNATIV-0004 - Implementar registro de plantillas opt-in

```toml
id = "TASK-AGENTE-SPECNATIV-0004"
title = "Implementar registro de plantillas opt-in"
state = "todo"
priority = "p1"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0003"]
expected_files = ["src/templates.rs", "tests/templates.rs"]
close_criteria = "Las plantillas se listan sin aplicarse; sólo una confirmación explícita genera cambios; nombres inválidos no modifican archivos."
validation = ["cargo test", "walkthrough de escenarios"]
```

Exponer las plantillas disponibles y una operación explícita `usar plantilla <nombre>` con validación, alcance visible, confirmación y evidencia.

### TASK-AGENTE-SPECNATIV-0005 - Validar flujo completo de definición de specs

```toml
id = "TASK-AGENTE-SPECNATIV-0005"
title = "Validar flujo completo de definición de specs"
state = "todo"
priority = "p1"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0004"]
expected_files = ["tests/acceptance/", "README.md"]
close_criteria = "Los escenarios de aceptación de SPEC-0001 pasan y health_check/validate no reportan errores."
validation = ["cargo test", "specnative validate", "health_check"]
```

Ejecutar pruebas y walkthrough de idea incompleta a spec, incluyendo sesión, criterios de aceptación, errores y reporte de evidencia.

### TASK-AGENTE-SPECNATIV-0006 - Implementar piloto interactivo con smolagents

> **Update 2026-09-18T01:18:01Z:** Implementando el piloto Python con smolagents y la barrera de escritura controlada por el controlador.

```toml
id = "TASK-AGENTE-SPECNATIV-0006"
title = "Implementar piloto interactivo con smolagents"
state = "done"
priority = "p0"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0001"]
expected_files = ["pilot/pyproject.toml", "pilot/src/", "pilot/tests/"]
close_criteria = "El CLI instala y arranca; el flujo idea → spec → tareas queda cubierto por pruebas y la política impide que el modelo escriba o aplique plantillas directamente."
validation = ["pytest -q pilot/tests", "compileall pilot/src", "smoke test MCP en repositorio temporal"]
completion_evidence = ["pytest -q pilot/tests: 6 passed; compileall de pilot/src y .specnative/specnative_mcp.py correcto; smoke test del adaptador MCP en repositorio temporal: passed; CLI --help correcto; el agente no expone write_spec, write_tasks ni apply_spec_template al modelo."]
```

Construir el CLI Python del piloto con ToolCallingAgent, MCP por stdio, propuesta estructurada, confirmación de escrituras, historial opcional y comando /template explícito.

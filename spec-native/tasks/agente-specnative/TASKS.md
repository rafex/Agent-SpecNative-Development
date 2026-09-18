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

```toml
id = "TASK-AGENTE-SPECNATIV-0001"
title = "Definir contrato del agente y clasificador de intención"
state = "todo"
priority = "p0"
owner = "rafex"
labels = []
dependencies = []
expected_files = ["docs/agent-contract.md", "tests/intent_classifier.rs"]
close_criteria = "El contrato define eventos, entradas, salidas y casos ambiguos; las pruebas cubren ausencia de orden, orden válida y plantilla inexistente."
validation = ["cargo test"]
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

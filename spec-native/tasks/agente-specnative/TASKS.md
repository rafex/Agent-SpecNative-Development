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

> **Update 2026-09-18T16:59:51Z:** Añadir actualización automática del MCP incluido: release, fallback Git, caché y fallback interno.

```toml
id = "TASK-AGENTE-SPECNATIV-0003"
title = "Integrar el adaptador MCP de SpecNative"
state = "done"
priority = "p0"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0002"]
expected_files = ["src/specnative_mcp.rs", "tests/integration/"]
close_criteria = "Una prueba de integración contra un repositorio temporal demuestra lectura de contexto, actualización y validación sin estado paralelo."
validation = ["cargo test", "specnative validate"]
completion_evidence = ["Implementado el proveedor remoto MCP con caché XDG de 24 h, modos auto/never/force, verificación SHA-256 del release, fallback a git clone main/tools/specnative_mcp.py, fallback a caché anterior y finalmente MCP interno. Validado con 22 pruebas, uv lock --check, make check, make build, validación SpecNative y handshake MCP real contra release v0.9.0."]
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

> **Update 2026-09-18T19:24:53Z:** El piloto Python ahora expone asn-agent-mcp y asn setup; el CLI y el servidor MCP reutilizan AgentSession con propuestas, confirmaciones y plantillas explícitas.

> **Update 2026-09-18T23:41:00Z:** ASN admite credenciales por SOPS/age y gopass mediante `asn secrets init`, con autodetección segura, fallback compatible a variables de entorno y resolución compartida entre `asn` y `asn-agent-mcp`.

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
completion_evidence = ["pytest -q pilot/tests: 37 passed; uv lock --check --project pilot; make check; make build; smoke real con sops + age resolvió modelo, endpoint y API key sin archivo descifrado; `asn secrets init --backend gopass` generó referencias sin secretos; `asn-agent-mcp --help` expone los flags de backend; make install mantiene los ejecutables asn, asn-mcp y asn-agent-mcp; handshake MCP del agente expone agent_session_start, agent_session_message, agent_session_status, agent_session_approve, agent_session_reject y agent_session_close; preflight fallido en Portal no inicializa el modelo ni modifica archivos; asn setup --repo Portal --clients all es idempotente; Codex, Claude y OpenCode detectan asn-agent y specnative."]
```

Construir el CLI Python del piloto con ToolCallingAgent, MCP por stdio, propuesta estructurada, confirmación de escrituras, historial opcional y comando /template explícito.

### TASK-AGENTE-SPECNATIV-0007 - Guiar la configuración y autenticación de credenciales

> **Update 2026-09-25T14:46:46Z:** Autenticación verificada además contra los binarios reales SOPS/age en un directorio temporal. Paquete reinstalado desde el checkout en ~/.local/bin.

> **Update 2026-09-25T14:44:55Z:** Implementados validación de credenciales al iniciar, autenticación SOPS/age global y por proyecto, resolución proyecto → global → entorno y mensajes no interactivos para MCP.

```toml
id = "TASK-AGENTE-SPECNATIV-0007"
title = "Guiar la configuración y autenticación de credenciales"
state = "done"
priority = "p0"
owner = "rafex"
labels = []
dependencies = ["TASK-AGENTE-SPECNATIV-0006"]
expected_files = ["pilot/src/specnative_pilot/cli.py", "pilot/src/specnative_pilot/secrets.py", "pilot/src/specnative_pilot/secret_setup.py", "pilot/src/specnative_pilot/session.py", "pilot/tests/test_cli.py", "pilot/tests/test_secrets.py", "pilot/tests/test_session.py", "pilot/README.md", "docs/man_asn.md"]
close_criteria = "asn valida credenciales antes de iniciar y explica cómo configurarlas; asn --auth cifra credenciales globales o por proyecto con SOPS/age, crea y protege la identidad ~/.age/asn-key.txt si falta, y MCP informa fallos sin solicitar entrada interactiva."
validation = ["pytest -q pilot/tests", "compileall pilot/src"]
completion_evidence = ["PYTHONPATH=pilot/src .specnative/.venv/bin/python -m pytest -q pilot/tests: 49 passed; compileall -q pilot/src .specnative/specnative_mcp.py: correcto; git diff --check: correcto; smoke real SOPS/age cifró y descifró credenciales globales desde un XDG_CONFIG_HOME temporal y generó una identidad con permisos 0600; `asn --help` instalado expone `--auth`."]
```

El archivo SOPS del proyecto tiene prioridad sobre el global y las variables de entorno quedan como fallback. `asn --auth` configura globalmente por defecto; `--repo` limita la autenticación al proyecto indicado.

### TASK-AGENTE-SPECNATIV-0008 - Cancelar asn --auth limpiamente con Ctrl+C

> **Update 2026-09-25T18:11:38Z:** `asn --auth` captura KeyboardInterrupt, muestra una cancelación normal y devuelve código 0. authenticate solicita modelo, endpoint y API key antes de crear/cifrar y escribir el archivo de credenciales. El ejecutable de usuario fue reinstalado.

> **Update 2026-09-25T18:09:53Z:** Implementando salida limpia al recibir KeyboardInterrupt durante la autenticación.

```toml
id = "TASK-AGENTE-SPECNATIV-0008"
title = "Cancelar asn --auth limpiamente con Ctrl+C"
state = "done"
priority = "p0"
owner = "rafex"
labels = []
dependencies = []
expected_files = ["pilot/src/specnative_pilot/cli.py", "spec-native/specs/agente-specnative/SPEC.md"]
close_criteria = "Si el usuario pulsa Ctrl+C en cualquier prompt de asn --auth, el CLI termina sin traceback, informa que la autenticación se canceló y no deja credenciales parciales."
validation = ["Revisión del manejo de KeyboardInterrupt y del orden de escritura de credenciales", "make install BIN_DIR=/home/rafex/.local/bin"]
completion_evidence = ["make install BIN_DIR=/home/rafex/.local/bin: instalación del paquete specnative-agent-pilot 0.2.0 desde este checkout y actualización de los ejecutables asn, asn-agent-mcp, asn-mcp y specnative-agent; revisión del flujo authenticate confirma que las escrituras SOPS ocurren después de completar los prompts."]
```

Manejar KeyboardInterrupt durante la autenticación interactiva para salir sin traceback ni presentar la interrupción del usuario como fallo; verificar que interrumpir la captura no escriba credenciales.

### TASK-AGENTE-SPECNATIV-0009 - Documentar uso y desarrollo del agente ASN con MkDocs

> **Update 2026-09-25T19:57:35Z:** Implementando el sitio MkDocs Material y las guías en español de uso del agente y desarrollo del piloto.

```toml
id = "TASK-AGENTE-SPECNATIV-0009"
title = "Documentar uso y desarrollo del agente ASN con MkDocs"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "El sitio MkDocs Material contiene portada, inicio rápido, guía de uso y guía de desarrollo que cubren instalación, credenciales, integración MCP, propuesta/aprobación/rechazo, plantillas explícitas, workflow SpecNative, comandos y validación. Los manuales existentes quedan enlazados sin duplicar su contenido; el sitio compila con la navegación configurada y site/ está ignorado por Git."
validation = ["mkdocs build --strict -f .config/mkdocs/mkdocs.yml", "Verificar manualmente la navegación y los enlaces internos de las guías"]
completion_evidence = ["`make docs` ejecutó `mkdocs build --strict --config-file .config/mkdocs/mkdocs.yml` sin errores; `just --list` muestra docs y serve; se comprobó frontmatter en todos los docs/*.md, `git check-ignore site/index.html` excluye la salida, y `git diff --check` pasa."]
```

Crear guías en español para instalar/configurar ASN, usar correctamente el flujo del agente y contribuir/desarrollar el piloto; añadir un sitio MkDocs Material con comandos locales docs y serve.

### TASK-AGENTE-SPECNATIV-0010 - Mostrar ayuda Markdown y manejar fallos de tool calling

> **Update 2026-09-25T20:34:37Z:** Implementando /help con Markdown empaquetado y mdcat, y manejo controlado del error de generación de herramientas.

```toml
id = "TASK-AGENTE-SPECNATIV-0010"
title = "Mostrar ayuda Markdown y manejar fallos de tool calling"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "/help muestra docs/man_help.md completo desde una instalación distribuida, renderizado con mdcat cuando está disponible y con fallback legible cuando falta. AgentGenerationError se informa sin traceback, cierra MCP/sesión con código no cero, no reintenta automáticamente y no escribe archivos."
validation = ["Verificar /help desde un paquete instalado con mdcat disponible y ausente", "Simular AgentGenerationError al enviar un mensaje y confirmar salida limpia sin escrituras"]
completion_evidence = ["`uv run --project pilot --extra dev --locked -- python -m pytest -q pilot/tests/test_policy.py`: 6 passed; `make docs`: build estricto correcto con el snippet de ayuda; `uv build --project pilot --out-dir /tmp/asn-help-dist`: wheel y sdist creados, comprobado que el wheel incluye `specnative_pilot/resources/specnative-agent/help.md`; `git diff --check` correcto."]
```

Ampliar /help para renderizar el manual Markdown empaquetado con mdcat y manejar AgentGenerationError de proveedores tool-calling con salida clara, cierre seguro y sin reintentos automáticos.

### TASK-AGENTE-SPECNATIV-0011 - Agregar asn --test para validar endpoint, modelo y token

```toml
id = "TASK-AGENTE-SPECNATIV-0011"
title = "Agregar asn --test para validar endpoint, modelo y token"
state = "done"
priority = "p2"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "`asn --test` reutiliza el mismo modelo, URL base y token que el agente; realiza una sola petición corta sin herramientas usando curl; informa éxito o error útil sin exponer credenciales; sale antes del preflight/MCP/agente; manual y guía de inicio documentan el modo."
validation = ["Pruebas unitarias simuladas cubren curl exitoso, respuestas HTTP inválidas, fallo de curl y ausencia de credenciales sin hacer llamadas reales al proveedor.", "Pruebas CLI confirman que --test no inicia Controller y que propaga el resultado del diagnóstico.", "Ejecutar pytest dirigido del paquete pilot."]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config uv run --project pilot pytest -q` terminó con 59 passed; `make docs` generó el sitio MkDocs correctamente; `git diff --check` pasó. Las pruebas usan curl simulado y no realizaron llamadas reales al proveedor."]
```

Añadir un modo de diagnóstico `asn --test` que resuelva la configuración y secretos actuales y envíe una petición Chat Completions mínima con curl, evitando arrancar MCP o agente interactivo; documentar uso y errores seguros.

### TASK-AGENTE-SPECNATIV-0012 - Mostrar petición sanitizada en asn --test

```toml
id = "TASK-AGENTE-SPECNATIV-0012"
title = "Mostrar petición sanitizada en asn --test"
state = "done"
priority = "p2"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "Antes o durante el reporte del resultado, asn --test muestra método, URL sanitizada, modelo, JSON del request y token enmascarado con prefijo/sufijo (tokens cortos completamente ocultos). Nunca revela userinfo ni valores de query URL; respuesta sin texto incluye status HTTP y metadatos disponibles sin volcar respuesta completa."
validation = ["Pruebas unitarias de requests exitoso, HTTP error y HTTP 200 con contenido vacío comprueban que se imprime el resumen solicitado y no se filtran secretos.", "Pruebas de redacción verifican prefijo/sufijo y tokens cortos, además de credenciales embebidas y query params en URL.", "Correr suite pilot y build de MkDocs; no hacer request real a proveedor."]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config uv run --project pilot pytest -q` terminó con 62 passed; `make docs` construyó el sitio correctamente. Las pruebas simulan curl y validan el resumen sanitizado en éxitos, HTTP 401 y HTTP 200 sin texto; no hubo llamadas reales al proveedor."]
```

Ampliar el diagnóstico de asn --test para mostrar URL endpoint, modelo, body de la petición y Authorization parcialmente enmascarado incluso en errores; reportar metadatos de HTTP 200 sin contenido, ocultando credenciales URL.

### TASK-AGENTE-SPECNATIV-0013 - Aplicar esfuerzo de razonamiento y registrar fallas de ASN

```toml
id = "TASK-AGENTE-SPECNATIV-0013"
title = "Aplicar esfuerzo de razonamiento y registrar fallas de ASN"
state = "done"
priority = "p2"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "[agent].reasoning_effort y SPECNATIVE_AGENT_REASONING_EFFORT configuran el mismo argumento del proveedor para agente y prueba, con env prevaleciendo y default del proveedor cuando falta; asn --test usa límite 1024. Fallas de CLI y asn-agent-mcp registran JSONL saneado con traceback para excepciones inesperadas, en /var/log/asn con fallback de usuario específico de plataforma y /tmp final, rotado a 10 MiB x 5 copias y permisos 0700/0600. No se registran prompts, respuestas, bodies ni credenciales, y el transporte MCP stdio no mezcla logs en stdout."
validation = ["Pruebas cubren precedencia de razonamiento y propagación a constructor del modelo y request curl, default omitido y cap 1024.", "Pruebas simulan errores CLI/MCP, destinos no escribibles, redacción de secretos, permisos/rotación y preservación del stdout MCP.", "Ejecutar suite pilot y compilación MkDocs sin petición real al proveedor."]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config XDG_STATE_HOME=/tmp/asn-test-state uv run --project pilot pytest -q` terminó con 75 passed; `make docs` compiló MkDocs correctamente y `git diff --check` pasó. Las llamadas curl se simularon; no se consultó al proveedor real."]
```

Configurar reasoning_effort compartido por el agente y asn --test, elevar el presupuesto del smoke test para modelos de razonamiento e implementar logs JSONL de fallas del CLI y agente MCP con rutas persistentes/fallback, rotación y redacción de secretos.

### TASK-AGENTE-SPECNATIV-0014 - Recuperar y diagnosticar fallos de tool calling en Groq GPT-OSS

> **Update 2026-09-26T17:25:30Z:** Cambios implementados globalmente en ASN; el probe HTTP ahora exige un tool call real y el retry queda restringido al 400 exacto de Groq GPT-OSS.

> **Update 2026-09-26T17:16:19Z:** Implementando defaults Groq GPT-OSS, retry acotado y validación de tool calling en asn --test.

```toml
id = "TASK-AGENTE-SPECNATIV-0014"
title = "Recuperar y diagnosticar fallos de tool calling en Groq GPT-OSS"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "Groq GPT-OSS sin override usa reasoning_effort low; solo el 400 por no emitir herramienta se reintenta una vez con instrucción explícita; el segundo fallo no modifica artefactos y se registra sanitizado. asn --test confirma llamada a herramienta y reporta errores útiles."
validation = ["Pruebas simuladas cubren effort default/overrides, reintento único exacto, éxito de segundo intento, segundo fallo y ausencia de reintentos para errores distintos.", "Pruebas simuladas de asn --test validan tool_calls esperadas, HTTP error, respuesta sin tool call, sanitización y uso del effort efectivo.", "Ejecutar pytest del paquete pilot, make docs y git diff --check; probar asn --test contra el endpoint configurado."]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config XDG_STATE_HOME=/tmp/asn-test-state uv run --project pilot pytest -q`: 84 passed; `make docs`: compilación correcta; `git diff --check`: correcto; MCP `validate()`: las 15 referencias obligatorias válidas; `health_check()`: 8/8 documentos saludables. Tras `make install`, `/home/rafex/.local/bin/asn --test --repo /home/rafex/repository/rafex/portal-captive` respondió HTTP 200 y validó `asn_tool_call_probe` con `tool_choice=required` y `reasoning_effort=low`."]
```

Definir effort low por defecto para Groq GPT-OSS, reintentar una sola vez el error HTTP 400 exacto de tool choice requerido, y hacer que asn --test compruebe una llamada real a una herramienta.

### TASK-AGENTE-SPECNATIV-0015 - Autocompletar iniciativas existentes y prevenir duplicados por typo

```toml
id = "TASK-AGENTE-SPECNATIV-0015"
title = "Autocompletar iniciativas existentes y prevenir duplicados por typo"
state = "done"
priority = "p1"
owner = "rafex"
labels = ["cli", "usability"]
dependencies = ["TASK-AGENTE-SPECNATIV-0006"]
expected_files = ["pilot/src/specnative_pilot/controller.py", "pilot/pyproject.toml", "pilot/tests/test_policy.py", "pilot/src/specnative_pilot/resources/specnative-agent/help.md"]
close_criteria = "En una terminal interactiva ASN muestra sugerencias de slugs existentes mientras se escribe; en modo no interactivo conserva el prompt; un slug a una edición de distancia requiere confirmación antes de crear una iniciativa distinta."
validation = ["uv run --project pilot pytest -q", "uv lock --check --project pilot", "git diff --check"]
completion_evidence = ["XDG_CONFIG_HOME=/tmp/asn-test-config XDG_STATE_HOME=/tmp/asn-test-state uv run --project pilot pytest -q: 91 passed; uv lock --check --project pilot: correcto; make docs: compilación correcta; git diff --check: correcto; MCP validate: 15 archivos y referencias válidos; MCP health_check: 8/8 documentos saludables."]
```

Completar slugs desde `spec-native/specs/` y `spec-native/tasks/`, reutilizar una coincidencia cercana al rechazar la creación y permitirla sólo tras confirmación explícita.

### TASK-AGENTE-SPECNATIV-0016 - Registrar eval de modelos y corregir el formato del reintento

> **Update 2026-09-26T19:08:14Z:** Implementando eval JSONL temporal y protegido en llamadas del modelo, salida de ruta en CLI/MCP y retry serializable con contador de requests efectivamente enviados.

```toml
id = "TASK-AGENTE-SPECNATIV-0016"
title = "Registrar eval de modelos y corregir el formato del reintento"
state = "done"
priority = "p1"
owner = "rafex"
labels = ["agent", "diagnostics", "provider"]
dependencies = ["TASK-AGENTE-SPECNATIV-0014"]
expected_files = ["pilot/src/specnative_pilot/model_eval.py", "pilot/src/specnative_pilot/model.py", "pilot/src/specnative_pilot/session.py", "pilot/tests/test_model_eval.py", "pilot/tests/test_model.py"]
close_criteria = "Cada llamada conversacional al proveedor deja un registro JSONL en una carpeta temporal privada con payload, respuesta/error y duración, y la ruta se expone en CLI/MCP. El retry de Groq usa contenido compatible con smolagents y cuenta sólo llamadas enviadas."
validation = ["uv run --project pilot pytest -q", "uv lock --check --project pilot", "make docs", "git diff --check", "specnative validate"]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config XDG_STATE_HOME=/tmp/asn-test-state uv run --project pilot pytest -q`: 97 passed; `uv lock --check --project pilot`: correcto; `make docs`: compilación correcta; `git diff --check`: correcto; MCP `validate`: 15 archivos y referencias válidos; MCP `health_check`: 8/8 documentos saludables. Pruebas simuladas; sin peticiones reales al proveedor."]
```

Guardar trazas exactas del cuerpo de cada llamada conversacional del agente en temporales privados (sin headers de autenticación), exponer su ubicación e impedir que un error local al serializar el retry se cuente como petición enviada.

### TASK-AGENTE-SPECNATIV-0017 - Mostrar version ASN asociada al commit

> **Update 2026-09-26T19:23:50Z:** Agregada como requisito: versión de distribución asociada al hash Git; inicio implementación de build metadata y flag CLI.

```toml
id = "TASK-AGENTE-SPECNATIV-0017"
title = "Mostrar version ASN asociada al commit"
state = "done"
priority = "p1"
owner = "rafex"
labels = ["cli", "release"]
dependencies = []
expected_files = ["pilot/pyproject.toml", "pilot/src/specnative_pilot/cli.py", "pilot/tests/test_cli.py"]
close_criteria = "El paquete ASN obtiene en build una versión reproducible desde Git, `asn --version` la muestra incluyendo el hash del commit y sale sin leer configuración, credenciales ni conectar al proveedor."
validation = ["pytest de pilot incluyendo el comando --version", "uv lock --check --project pilot", "build del paquete que demuestre versión con hash", "instalación local y verificación de asn --version", "make docs", "git diff --check", "specnative validate"]
completion_evidence = ["Suite pilot: 98 passed; `uv lock --check --project pilot`: correcto; `make docs`: correcto; `git diff --check`: correcto; `uv build --project pilot --no-sources`: wheel/sdist contienen versión con hash Git; MCP `validate`: 15 referencias válidas; `health_check`: 8/8. Publicado `3721a7311787210ede986ecbf0b41508c7a16330`, `make install BIN_DIR=/home/rafex/.local/bin` instaló `asn 0.2.1.dev9+g3721a7311`; `asn setup --repo /home/rafex/repository/rafex/portal-captive --clients all` verificó configuración existente de Codex, Claude y OpenCode como actualizada."]
```

Generar metadatos de versión desde el commit Git al construir ASN e incluirlos en la salida inmediata `asn --version` para identificar la versión instalada.

### TASK-AGENTE-SPECNATIV-0018 - Probar el ciclo completo de tools MCP en ASN

> **Update 2026-09-26T20:02:21Z:** La eval del fallo de 2026-09-26 confirma que status/read_spec se invocan; el error está en serialización de la instrucción retry tras role-conversion tool-response a user. Implementando regresión y diagnóstico end-to-end.

```toml
id = "TASK-AGENTE-SPECNATIV-0018"
title = "Probar el ciclo completo de tools MCP en ASN"
state = "done"
priority = "p1"
owner = "rafex"
labels = ["agent", "diagnostics", "mcp"]
dependencies = ["TASK-AGENTE-SPECNATIV-0016"]
expected_files = ["pilot/src/specnative_pilot/mcp_check.py", "pilot/src/specnative_pilot/model.py", "pilot/src/specnative_pilot/cli.py", "pilot/tests/test_mcp_check.py"]
close_criteria = "`asn --test-mcp` ejecuta una llamada real del agente a la tool MCP de solo lectura `status`, valida que el agente continúe después del resultado, muestra etapa, requests, duración y ubicación del eval; el retry Groq puede serializar el historial con tool-response sin error local."
validation = ["uv run --project pilot pytest -q", "uv lock --check --project pilot", "make docs", "git diff --check", "specnative validate"]
completion_evidence = ["`XDG_CONFIG_HOME=/tmp/asn-test-config XDG_STATE_HOME=/tmp/asn-test-state uv run --project pilot pytest -q`: 109 passed; cubre retry tras `tool-response`, ciclo real de ToolCallingAgent simulado, MCP status, fallos por etapa, límite de tools y CLI; `uv lock --check --project pilot`: correcto; `make docs`: correcto; `git diff --check`: correcto; MCP `validate`: 15 referencias válidas; `health_check`: 8/8 documentos saludables. Sin llamadas reales al proveedor."]
```

Agregar una prueba end-to-end del agente y MCP para diagnosticar fallas de tool calling y corregir el retry cuando smolagents normaliza resultados MCP al rol user.

### TASK-AGENTE-SPECNATIV-0019 - Robustecer respuestas vacías y ampliar el diagnóstico agente-MCP

> **Update 2026-09-27T02:20:30Z:** Implementado reintento único para respuestas exitosas vacías de Groq GPT-OSS, fallo explícito y catálogo de diagnóstico alineado con las tools seguras de producción.

> **Update 2026-09-27T02:16:37Z:** Implementación autorizada tras el diagnóstico del caso Groq GPT-OSS; mantengo el proveedor y limito la recuperación a un reintento.

```toml
id = "TASK-AGENTE-SPECNATIV-0019"
title = "Robustecer respuestas vacías y ampliar el diagnóstico agente-MCP"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "Groq GPT-OSS recibe un único reintento cuando una respuesta exitosa llega vacía; si vuelve vacía, ASN termina con un error diagnóstico sin exponer razonamiento ni entrar en un bucle de parsing. asn --test-mcp registra todo el catálogo MCP de solo lectura más propose_change local y valida status seguido de final_answer sin escritura. La documentación describe el comportamiento."
validation = ["uv run --project pilot pytest -q", "make docs", "git diff --check", "SpecNative validate"]
completion_evidence = ["`uv run --project pilot pytest -q` pasó: 117 tests. `make docs` construyó el sitio correctamente (emitió sólo la advertencia del proyecto MkDocs Material sobre MkDocs 2.0). `git diff --check` pasó tras normalizar el EOF de TASKS.md. SpecNative validate pasó: 15 archivos y referencias válidos."]
```

Evitar bucles de parsing cuando Groq GPT-OSS devuelve HTTP 200 sin contenido ni tool call, y hacer que asn --test-mcp reproduzca el catálogo seguro real del agente.

### TASK-AGENTE-SPECNATIV-0020 - Reintentar respuestas vacías de GPT-OSS dentro del paso

> **Update 2026-09-27T02:58:57Z:** Implementado límite de 12 llamadas totales dentro del mismo paso, backoff 250 ms→2 s, max_completion_tokens creciente sólo con finish_reason=length y reasoning_effort=low en reintentos.

> **Update 2026-09-27T02:53:33Z:** Implementar la política aprobada para Groq GPT-OSS, manteniendo los reintentos dentro de generate() para no consumir pasos smolagents.

```toml
id = "TASK-AGENTE-SPECNATIV-0020"
title = "Reintentar respuestas vacías de GPT-OSS dentro del paso"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "Una respuesta vacía sin tool calls reintenta el mismo paso hasta 12 llamadas totales, con backoff exponencial de 250 ms con tope de 2 s. Cuando finish_reason=length, max_completion_tokens se duplica hasta 65 536; en otros motivos no aumenta. reasoning_effort queda en low. Al agotar intentos el turno falla con diagnóstico. Pruebas y documentación cubren la política."
validation = ["uv run --project pilot pytest -q", "make docs", "git diff --check", "SpecNative validate"]
completion_evidence = ["`uv run --project pilot pytest -q`: 119 passed. `make docs`: sitio construido correctamente; MkDocs Material mostró su advertencia upstream sobre MkDocs 2.0. `git diff --check`: passed. SpecNative validate: 15 archivos y referencias válidos."]
```

Evitar que respuestas exitosas vacías de Groq GPT-OSS consuman pasos smolagents; limitar llamadas por paso y recuperar presupuesto cuando finish_reason indique length.

### TASK-AGENTE-SPECNATIV-0021 - Generalizar recuperación del modelo y agregar memoria SQLite

> **Update 2026-09-27T03:36:53Z:** Implementación iniciada desde el plan aprobado; eval detallado temporal se mantiene separado del historial persistente.

```toml
id = "TASK-AGENTE-SPECNATIV-0021"
title = "Generalizar recuperación del modelo y agregar memoria SQLite"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "ASN reintenta respuestas vacías hasta 12 intentos dentro del paso en proveedores OpenAI compatibles usando reasoning_effort=low y fallback max_completion_tokens→max_tokens; mantiene el historial textual serializable. El piloto persiste llamadas (metadatos) y turnos visibles en SQLite por repositorio, importa JSONL idempotentemente, ofrece recuperación vectorial con sqlite-vec priorizando iniciativa y degradación con aviso si embeddings no están disponibles, y permite listar/exportar/borrar historial mediante CLI. Eval completo permanece temporal; docs/spec reflejan que spec-native es la fuente canónica."
validation = ["Casos simulados de respuesta vacía, finish_reason=length, tool call válida, fallback de tokens y agotamiento de 12 intentos en proveedores compatibles.", "Verificar serialización textual del historial sin reasoning oculto ni tool_call_ids estructurados.", "Pruebas de integración SQLite para persistencia, migración idempotente, recuperación con prioridad de iniciativa, exportación y borrado.", "Simular proveedor sin embeddings y verificar aviso con continuidad de la sesión.", "Ejecutar suite del piloto y build estricto MkDocs."]
completion_evidence = ["`uv run --project pilot pytest -q`: 130 passed; `make docs`: sitio MkDocs construido; `uv lock --project pilot --check`, compileall y `git diff --check`: correctos; `uv build --project pilot --out-dir /tmp/asn-sqlite-dist`: sdist y wheel creados; SpecNative validate: 15 archivos y referencias válidos. La prueba vectorial ejecutó sqlite-vec real; embeddings/provider externo se simularon."]
```

Generalizar los reintentos de respuestas vacías a proveedores OpenAI compatibles y agregar memoria e historial local por repositorio con SQLite/sqlite-vec, controles CLI, migración del JSONL existente y documentación.

### TASK-AGENTE-SPECNATIV-0022 - Endurecer GPT-OSS en Groq y documentar persistencia SQLite

> **Update 2026-09-27T04:47:17Z:** Completando compatibilidad del agente Groq GPT-OSS y actualización de guía operativa/SQLite antes de instalar y publicar.

```toml
id = "TASK-AGENTE-SPECNATIV-0022"
title = "Endurecer GPT-OSS en Groq y documentar persistencia SQLite"
state = "done"
priority = "p1"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "La petición real de inicio del portal devuelve una respuesta utilizable o una pregunta segura sin agotar reintentos; asn --test y asn --test-mcp completan con la instalación local; la documentación MkDocs explica qué persiste en SQLite y qué queda en eval temporal, incluye diagramas Mermaid y D2; el cambio está publicado en Git."
validation = ["Ejecutar asn --version, asn --test y asn --test-mcp contra la configuración local sin mostrar la credencial.", "Reproducir el prompt adjunto a través de AgentSession y comprobar respuesta utilizable sin modificar archivos del repositorio portal-captive.", "Construir el sitio MkDocs y revisar git diff --check."]
completion_evidence = ["Publicación `b74ef023f` en main e instalación local `asn 0.2.1.dev17+gb74ef023f`. Tras instalar: `asn --test --repo /home/rafex/repository/rafex/portal-captive` validó HTTP 200 y la tool call `asn_tool_call_probe`; `asn --test-mcp` ejecutó `status` y continuó tras el resultado MCP (4 requests). Un turno AgentSession con la petición del portal devolvió una pregunta breve sobre usar identidad ficticia, en una llamada, sin proponer ni escribir specs. `asn setup --clients all` confirmó Codex/Claude/OpenCode actualizados. `make docs`, compileall, `git diff --check` y compilación D2 pasaron; el SVG existente coincide con regeneración. SpecNative validate pasó con los 15 archivos requeridos."]
```

Completar la integración estructurada de tool calling y continuación para Groq GPT-OSS, instalar esta revisión en la máquina local, configurar ASN para uso y ampliar la documentación MkDocs sobre memoria e historial SQLite/sqlite-vec con diagramas Mermaid y D2.

### TASK-AGENTE-SPECNATIV-0023 - Consultar modelos disponibles del proveedor con ASN

> **Update 2026-09-27T04:58:14Z:** Implementando consulta autenticada GET /models para el endpoint compatible configurado y documentación de uso para Groq.

```toml
id = "TASK-AGENTE-SPECNATIV-0023"
title = "Consultar modelos disponibles del proveedor con ASN"
state = "done"
priority = "p2"
owner = "rafex"
labels = []
dependencies = []
expected_files = []
close_criteria = "`asn models --repo <ruta>` consulta el endpoint compatible `/models` con la credencial resuelta por ASN, lista IDs del catálogo y marca el modelo efectivo configurado; respuestas inválidas, HTTP errors y falta de credenciales producen mensajes seguros; los diagnósticos nunca muestran el token. La documentación incluye uso y ejemplo para Groq."
validation = ["Prueba unitaria simulando GET /models, catálogo vacío y errores HTTP sin imprimir credenciales.", "Verificar URL base con y sin `/v1`, conservando el modelo/end-point esperado.", "Construir documentación MkDocs, compilar Python y revisar git diff --check."]
completion_evidence = ["`asn models --repo /home/rafex/repository/rafex/portal-captive` ejecutó el GET real a https://api.groq.com/openai/v1/models, recibió HTTP 200, listó 12 IDs y marcó `qwen/qwen3.8-27b` como disponible; el token no apareció en salida. Con ese modelo, `asn --test` validó tool calling, `asn --test-mcp` pasó con 2 requests y el prompt real de portal-captive terminó en pregunta clara con 2 pasos, sin escribir specs. `make docs`, compileall y `git diff --check` correctos."]
```

Agregar `asn models` para enviar GET /models al endpoint configurado con la misma autenticación segura que ASN. Listar IDs disponibles, marcar el modelo configurado y manejar errores sin imprimir el token. Documentar el comando como validación del catálogo del proveedor.

### TASK-AGENTE-SPECNATIV-0024 - Recuperar turnos fallidos y aprobar propuestas con MCP compatible

> **Update 2026-09-27T05:18:38Z:** Implementación autorizada; preservar el MCP local de portal-captive y no escribir allí propuestas automáticamente.

```toml
id = "TASK-AGENTE-SPECNATIV-0024"
title = "Recuperar turnos fallidos y aprobar propuestas con MCP compatible"
state = "done"
priority = "p1"
owner = "dev"
labels = []
dependencies = []
expected_files = []
close_criteria = "La sesión no termina por un fallo de generación ni por un fallo de aprobación. /retry, /edit, /skip, /approve, /reject y /model mantienen el estado correcto; el modelo activo se muestra al iniciar y al consultar. Las aprobaciones usan MCP del proyecto si soporta escrituras o el MCP incluido con ASN en caso contrario, sólo tras aprobación explícita."
validation = ["Pruebas unitarias de recuperación, persistencia de estado en RAM y fallback MCP; suite del paquete pasa.", "Verificar documentación de comandos y que ASN instalado reporte el hash publicado."]
completion_evidence = ["Implementado en 9e9c522971ff0e1eee6c3ec481bd525da42e49c5 y publicado. ASN conserva el mensaje fallido, permite /retry /edit /skip, conserva aprobaciones para /approve /reject y presenta el modelo cargado; el fallback de escritura sólo se ejecuta tras aprobación explícita y no se expone al modelo. 115 pruebas fuera de tests/test_model.py pasaron; MkDocs --strict y compileall pasaron. La suite completa conserva 8 fallos preexistentes en tests/test_model.py: los fixtures manuales no inicializan custom_role_conversions; model.py no fue modificado."]
```

Mantener ASN interactivo tras agotar reintentos del modelo, permitir reintentar/editar/omitir el mensaje en RAM, mostrar modelo activo y completar escrituras aprobadas usando el MCP incluido cuando el MCP del proyecto no ofrezca write_spec/write_tasks.

### TASK-AGENTE-SPECNATIV-0025 - Habilitar edición interactiva de texto en la terminal

> **Update 2026-09-27T05:33:34Z:** Cambio aplicado para que las entradas TTY usen prompt_toolkit; se conserva input_fn para entradas inyectadas/no TTY. Pendiente verificación manual de teclas en terminal.

```toml
id = "TASK-AGENTE-SPECNATIV-0025"
title = "Habilitar edición interactiva de texto en la terminal"
state = "in_progress"
priority = "p2"
owner = "dev"
labels = []
dependencies = []
expected_files = []
close_criteria = "En una terminal interactiva, el prompt principal permite mover el cursor con flechas izquierda/derecha y con Home/End; las inserciones y borrados ocurren en la posición del cursor. Entrada no interactiva y tests que inyectan input_fn conservan el comportamiento actual."
validation = ["Verificación manual en terminal usando izquierda, derecha, Home y End en un texto de entrada.", "Verificar que el fallback input_fn sigue funcionando fuera de una TTY."]
```

Usar un prompt de terminal con edición en línea para todas las entradas interactivas de ASN, incluidas entradas largas y confirmaciones, de modo que izquierda/derecha y Home/End editen el texto correctamente.

### TASK-AGENTE-SPECNATIV-0026 - Implementar protocolo GPT-OSS por modelo y memoria vectorial reindexable

```toml
id = "TASK-AGENTE-SPECNATIV-0026"
title = "Implementar protocolo GPT-OSS por modelo y memoria vectorial reindexable"
state = "done"
priority = "p1"
owner = "dev"
labels = []
dependencies = []
expected_files = []
close_criteria = "GPT-OSS usa la estrategia adecuada sin combinar response_format estricto con tools; los parámetros Groq son aplicados solo en Groq; embeddings admiten endpoint y credencial separados con asn --test-embeddings; los cambios de modelo/endpoint reindexan de forma diferida y recuperable, sin mezclar vectores ni perder turnos o índice anterior; documentación y pruebas cubren las rutas."
validation = ["Ejecutar pruebas de modelo, configuración, embeddings e historial SQLite.", "Construir documentación MkDocs."]
completion_evidence = ["`make check VENV=pilot/.venv PYTHON=pilot/.venv/bin/python` terminó correctamente con 145 tests aprobados, compileall y git diff --check. `make docs` construyó MkDocs y `make build` generó wheel y sdist. Se añadieron pruebas específicas de JSON Schema sin tools nativas, migración SQLite, reindexado en segundo plano, cambio atómico de perfil y diagnóstico de embeddings."]
```

Implementar estrategia GPT-OSS independiente del proveedor, usando JSON Schema estricto y despacho local en endpoints con soporte confirmado (sin combinar schema y tools en Groq) y tools nativas en otros endpoints; configurar opciones Groq reasoning/service tier/cache métricas; separar configuración y diagnóstico de embeddings y añadir reindexado vectorial en segundo plano con SQLite que preserve historial y el índice anterior ante fallos.

### TASK-AGENTE-SPECNATIV-0027 - Aplicar soporte general de Groq al catálogo de modelos de ASN

> **Update 2026-09-27T15:30:23Z:** Implementando compatibilidad general con modelos Groq del catálogo; los protocolos especiales siguen acotados a GPT-OSS.

```toml
id = "TASK-AGENTE-SPECNATIV-0027"
title = "Aplicar soporte general de Groq al catálogo de modelos de ASN"
state = "done"
priority = "p1"
owner = "dev"
labels = []
dependencies = []
expected_files = []
close_criteria = "Cualquier ID de modelo de chat Groq compatible con tool calling puede configurarse y usarse por la ruta OpenAI-compatible de ASN; las opciones generales de service tier aplican a Groq y las adaptaciones de razonamiento/JSON de GPT-OSS no se filtran a otros modelos. La guía explica que `asn models` muestra catálogo y el modelo se elige configurando el ID."
validation = ["Pruebas unitarias demuestran que un modelo Groq no GPT-OSS conserva tool calling nativo, recibe service_tier configurado/default y no recibe include_reasoning ni reasoning_effort por defecto.", "Prueba/documentación cubren la selección de un ID arbitrario del catálogo sin allowlist de GPT-OSS.", "Ejecutar suite de pruebas, build docs y git diff --check."]
completion_evidence = ["`pilot/.venv/bin/python -m compileall -q pilot/src`, `make docs` y `git diff --check` correctos. La ruta de construcción transmite service_tier a todo modelo del endpoint api.groq.com; include_reasoning=false y el protocolo JSON estructurado continúan limitados a GPT-OSS. Se documentó consultar IDs con asn models, configurarlos con asn --auth/SPECNATIVE_AGENT_MODEL y validarlos con asn --test. No se hizo una llamada real a Groq."]
```

Permitir usar cualquier modelo de chat de Groq compatible con tool calling, aplicar opciones del proveedor a todos los modelos Groq cuando correspondan y mantener únicamente las adaptaciones de protocolo/reasoning limitadas a GPT-OSS. Aclarar la selección de IDs mediante `asn models` y configuración.

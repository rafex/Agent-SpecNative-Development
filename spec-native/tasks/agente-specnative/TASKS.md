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

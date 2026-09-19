# SPEC.md

```toml
artifact_type = "spec"
id            = "SPEC-0001"
state         = "active"
owner         = "rafex"
created_at    = "2026-09-17"
updated_at    = "2026-09-18"
replaces      = "none"
related_tasks = ["TASK-AGENTE-SPECNATIV-0001", "TASK-AGENTE-SPECNATIV-0002", "TASK-AGENTE-SPECNATIV-0003", "TASK-AGENTE-SPECNATIV-0004", "TASK-AGENTE-SPECNATIV-0005", "TASK-AGENTE-SPECNATIV-0006"]
related_decisions = []
artifacts     = ["pilot/", ".specnative/specnative_mcp.py"]
validation    = ["cargo test", "specnative validate", "walkthrough de conversación"]
```

## Resumen

Construir un agente local muy ligero, preferentemente como binario Rust, que
ayude a un programador a convertir una idea ambigua en artefactos válidos de
SpecNative mediante una conversación guiada.

## Problema

El programador necesita conocer la estructura y el flujo de SpecNative para
pasar de una intención a una spec clara, con alcance, criterios de aceptación,
riesgos y tareas. Un asistente generalista puede comenzar a implementar antes
de aclarar el problema o aplicar una plantilla que el usuario no pidió.

## Objetivo

Al finalizar el MVP, un programador podrá iniciar el agente en un repositorio
SpecNative, recibir preguntas enfocadas, revisar propuestas y producir o
refinar los documentos canónicos del framework. Las plantillas estarán
disponibles para consulta, pero sólo se ejecutarán después de una instrucción
explícita como `usar plantilla <nombre>`.

## Alcance

Incluye:

- Un núcleo de orquestación conversacional enfocado en definición de specs.
- Interfaz inicial CLI/stdio y un adaptador para el MCP de SpecNative.
- Lectura del contexto y sesión del repositorio antes de preguntar.
- Flujo normal de descubrimiento que no selecciona ni aplica plantillas.
- Registro de plantillas con comandos explícitos, validación del nombre y
  evidencia del artefacto generado.
- Validación final de estructura y estados de SpecNative.

Excluye:

- Implementación autónoma de código, revisión de pull requests o despliegue.
- UI web, servidor persistente y base de datos.
- Dependencia obligatoria de un proveedor específico de modelos.
- Selección o aplicación automática de plantillas por similitud.

## Requisitos funcionales

- RF-1: El agente debe cargar el contexto mínimo de `spec-native/` y la sesión
  activa antes de conducir una definición.
- RF-2: En ausencia de una orden explícita de plantilla, el agente debe actuar
  en modo de descubrimiento: preguntar, resumir y proponer contenido para el
  documento canónico apropiado.
- RF-3: El agente debe reconocer una llamada explícita a una plantilla, validar
  que existe, mostrar qué producirá y solicitar confirmación antes de escribir.
- RF-4: El agente debe invocar el MCP de SpecNative para leer, actualizar y
  validar artefactos, evitando duplicar sus reglas e índices.
- RF-5: El agente debe devolver los archivos modificados y la evidencia de
  validación al finalizar cada operación.
- RF-6: El proveedor de modelo debe poder sustituirse sin cambiar el núcleo de
  conversación ni el adaptador SpecNative.
- RF-7: El agente debe poder resolver modelo, endpoint y API key desde un
  archivo SOPS/age o referencias gopass, manteniendo variables de entorno como
  compatibilidad y sin escribir secretos descifrados al repositorio.

## Requisitos no funcionales

- RNF-1: El MVP debe distribuirse como un binario local Rust con pocas
  dependencias y sin base de datos.
- RNF-2: El transporte inicial debe funcionar por stdio/JSON para integrarse
  con herramientas de desarrollo.
- RNF-3: Ninguna operación de plantilla debe ejecutarse como efecto lateral de
  una sugerencia, inferencia o coincidencia semántica.
- RNF-4: Las operaciones deben ser auditables mediante archivos versionados y
  resultados de validación reproducibles.

## Criterios de aceptación

- Dado un repositorio SpecNative y una idea incompleta, cuando el programador
  inicia el agente, entonces el agente lee el contexto y formula preguntas
  enfocadas antes de proponer una spec.
- Dado un flujo de definición sin mención de plantilla, cuando el agente
  completa una iteración, entonces sólo propone o actualiza el documento
  canónico acordado y no aplica ninguna plantilla.
- Dado el comando explícito `usar plantilla <nombre>`, cuando el nombre existe,
  entonces el agente muestra el alcance, solicita confirmación y aplica la
  plantilla mediante el MCP después de confirmarla.
- Dado un nombre de plantilla inexistente, cuando el usuario intenta usarlo,
  entonces el agente no modifica archivos y muestra las plantillas disponibles.
- Dado un cambio de documento, cuando termina la operación, entonces el agente
  ejecuta validación y reporta archivos y evidencia.
- Dado un proveedor de modelo alternativo que cumple el adaptador definido,
  cuando se configura, entonces el flujo de definición conserva el mismo
  comportamiento SpecNative.

## Dependencias y riesgos

- El contrato y la disponibilidad del MCP de SpecNative condicionan la
  actualización canónica de documentos.
- Rust se adopta como dirección preferida, pero la versión exacta y las
  dependencias se fijarán al implementar el MVP.
- La elección del proveedor de modelo queda abierta; debe probarse con un
  adaptador mínimo antes de convertirla en decisión persistente.
- La detección de intención debe distinguir con precisión una petición de
  ayuda de una orden explícita de plantilla.
- Los binarios externos `sops`, `age` y `gopass` son opcionales; sólo se
  requieren cuando el backend correspondiente se configura o autodetecta.

## Plan de validación

- Pruebas unitarias del clasificador de intención y del registro de plantillas.
- Pruebas de integración contra un repositorio SpecNative temporal y su MCP.
- `cargo test` y compilación del binario.
- `specnative validate` y `health_check` sobre los artefactos.
- Walkthrough manual de los escenarios de aceptación, incluyendo el caso en
  que una plantilla no debe aplicarse.

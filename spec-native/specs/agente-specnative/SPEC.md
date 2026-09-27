# SPEC.md

```toml
artifact_type = "spec"
id            = "SPEC-0001"
state         = "active"
owner         = "rafex"
created_at    = "2026-09-17"
updated_at    = "2026-09-26"
replaces      = "none"
related_tasks = ["TASK-AGENTE-SPECNATIV-0001", "TASK-AGENTE-SPECNATIV-0002", "TASK-AGENTE-SPECNATIV-0003", "TASK-AGENTE-SPECNATIV-0004", "TASK-AGENTE-SPECNATIV-0005", "TASK-AGENTE-SPECNATIV-0006", "TASK-AGENTE-SPECNATIV-0007", "TASK-AGENTE-SPECNATIV-0008", "TASK-AGENTE-SPECNATIV-0014", "TASK-AGENTE-SPECNATIV-0015", "TASK-AGENTE-SPECNATIV-0016", "TASK-AGENTE-SPECNATIV-0017", "TASK-AGENTE-SPECNATIV-0018", "TASK-AGENTE-SPECNATIV-0019", "TASK-AGENTE-SPECNATIV-0020", "TASK-AGENTE-SPECNATIV-0021"]
related_decisions = ["DEC-0001"]
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
- UI web, servidor persistente o base de datos centralizada.
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
- RF-8: El CLI debe validar modelo y API key antes de iniciar; si faltan, debe
  explicar las variables de entorno aceptadas y ofrecer `asn --auth`. La
  autenticación debe cifrar credenciales SOPS/age globales o por proyecto,
  creando una identidad age de usuario si no existe.
  creando una identidad age de usuario si no existe.
- RF-9: Para Groq GPT-OSS, el esfuerzo de razonamiento será `low` cuando no
  exista override. Si Groq devuelve el HTTP 400 específico de
  `tool_choice=required` sin llamada a herramienta, ASN reintentará una sola
  vez con una instrucción reforzada; un fallo persistente no escribirá archivos
  y quedará registrado. `asn --test` debe comprobar una llamada requerida a
  herramienta.
- RF-10: Al elegir una iniciativa, el CLI debe sugerir slugs existentes durante
  la escritura y advertir antes de continuar con un slug nuevo que difiera por
  una sola edición de uno existente.
- RF-11: Cada llamada conversacional efectuada al proveedor debe quedar en un
  eval JSONL privado temporal con el payload enviado, la respuesta o error y la
  duración; el reintento de Groq debe usar un formato de mensajes serializable.
- RF-12: `asn --version` debe mostrar la versión instalada e incluir el hash del
  commit Git del que se construyó el paquete, sin leer configuración ni iniciar
  conexiones externas.
- RF-13: `asn --test-mcp` debe ejecutar un ciclo real de agente con una
  herramienta MCP de solo lectura, comprobar que el agente continúa después de
  recibir el resultado, y reportar la etapa y eval temporal si falla.
- RF-14: Ante una respuesta sin contenido utilizable ni llamada a herramienta,
  el adaptador debe reintentar dentro del mismo paso hasta 12 solicitudes
  totales. Los reintentos usan `reasoning_effort=low`; si el endpoint rechaza
  `max_completion_tokens`, ASN reintenta con `max_tokens`. Ninguna respuesta
  vacía cuenta como paso completado.
- RF-15: ASN debe conservar por defecto en SQLite local, por repositorio, los
  metadatos de llamadas y los turnos visibles de usuario/agente. La base no
  contiene prompts/respuestas crudos del eval ni credenciales, y no reemplaza
  los documentos canónicos de `spec-native/`.
- RF-16: Cuando se configure un modelo de embeddings compatible con la URL y
  credencial del proveedor, ASN indexa turnos visibles con `sqlite-vec` y
  recupera hasta cinco recuerdos del repositorio, priorizando la iniciativa
  activa. Si embeddings no están disponibles, conserva historial e informa la
  degradación sin detener la sesión.
- RF-17: `asn history list`, `asn history export` y `asn history clear` permiten
  consultar, exportar a JSONL y borrar los datos locales. La importación del
  historial JSONL previo debe ser idempotente.

## Requisitos no funcionales

- RNF-1: El agente debe operar localmente; la memoria e historial usan SQLite
  como datos derivados por repositorio, sin un servicio de base centralizado.
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
- Dado que faltan el modelo o la API key, cuando se inicia `asn` o una sesión
  MCP, entonces se informa qué configuración falta y se sugiere `asn --auth`
  sin imprimir valores secretos ni iniciar el modelo.
- Dado que el usuario ejecuta `asn --auth`, cuando proporciona modelo, API
  base opcional y API key, entonces ASN cifra las credenciales a nivel global;
  con `--repo <ruta>` las cifra para ese proyecto. Una identidad nueva se crea
  en `~/.age/asn-key.txt`, y los archivos existentes sólo se reemplazan tras
  confirmación explícita.
- Dado que no están instalados SOPS o age, cuando se ejecuta `asn --auth`,
  entonces ASN presenta instrucciones de instalación y no instala paquetes ni
  escribe credenciales.
- Dado que el usuario interrumpe `asn --auth` con Ctrl+C durante la captura,
  entonces ASN informa que la autenticación se canceló sin traceback ni crear
  el archivo de credenciales.
- Dado que existe `portal-captive`, cuando el usuario escribe `portal-captives`
  como slug nuevo, entonces ASN advierte de la coincidencia cercana y requiere
  confirmación para continuar con un segundo slug.
- Dada una sesión del agente, cuando se efectúa una llamada al modelo, entonces
  el eval conserva el request JSON, la respuesta/error y la latencia sin headers
  de autenticación, y su ruta queda disponible en CLI y en `agent_session_start`.
- Dada una respuesta HTTP 400 de Groq por no llamar una herramienta, cuando ASN
  reintenta, entonces smolagents serializa correctamente el mensaje y el
  contador refleja sólo las llamadas que llegaron al cliente del proveedor.
- Dado un paquete ASN construido desde un commit Git, cuando el usuario ejecuta
  `asn --version`, entonces se muestra una versión que incluye el hash de ese
  commit antes de cargar credenciales o configuración.
- Dado un proveedor y un servidor MCP configurados, cuando el usuario ejecuta
  `asn --test-mcp`, entonces el agente invoca la herramienta de lectura
  `status`, procesa su resultado y finaliza el ciclo sin disponer de tools de
  escritura; si falla, se identifica la etapa sin imprimir prompts ni secretos.
- Dado un proveedor OpenAI-compatible que devuelve completions vacías,
  cuando ASN reintenta el paso, entonces realiza como máximo 12 solicitudes,
  fuerza `reasoning_effort=low` en los reintentos, usa el fallback de límite de
  tokens si el endpoint lo exige y sólo retorna cuando hay contenido o tool call.
- Dada una sesión con historial habilitado, cuando se envían turnos o llamadas
  al modelo, entonces SQLite guarda sólo turnos visibles y metadatos resumidos,
  mientras el eval completo continúa en el directorio temporal.
- Dado un proveedor compatible con embeddings, cuando existe memoria relevante,
  entonces ASN incluye hasta cinco turnos históricos como referencia y prioriza
  los de la iniciativa actual. Si el proveedor no ofrece embeddings, la sesión
  continúa con un aviso y conserva el historial SQL.
- Dado un JSONL de historial anterior, cuando ASN inicializa la base, entonces
  importa sus pares de turnos una sola vez. `asn history export` emite JSONL y
  `asn history clear` borra llamadas, turnos, vectores y el JSONL migrado.

## Dependencias y riesgos

- El contrato y la disponibilidad del MCP de SpecNative condicionan la
  actualización canónica de documentos.
- Rust se adopta como dirección preferida, pero la versión exacta y las
  dependencias se fijarán al implementar el MVP.
- La elección del proveedor de modelo queda abierta; debe probarse con un
  adaptador mínimo antes de convertirla en decisión persistente. El piloto usa
  `sqlite-vec` como extensión precargable; la búsqueda semántica requiere que el
  endpoint de chat admita embeddings y su falla sólo desactiva esa búsqueda.
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

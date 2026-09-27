+++
[session]
state = "in_progress"
agent = "unknown"
initiative = "agente-specnative"
task = "TASK-AGENTE-SPECNATIV-0029"
intent = "Emitir el aviso de embeddings no disponibles una sola vez por ejecución de ASN, incluso entre varias sesiones del proceso."
last_updated = "2026-09-27T17:35:41Z"
+++

# Active Session

## Current state

Emitir el aviso de embeddings no disponibles una sola vez por ejecución de ASN, incluso entre varias sesiones del proceso.

## Next steps

1. Ejecutar la prueba de sesión con dos AgentSession en el mismo proceso.
2. Ejecutar el conjunto de pruebas de historial y sesión.
3. Marcar TASK-AGENTE-SPECNATIV-0029 como done con evidencia si pasan.

## Context for next agent

Implementación en pilot/src/specnative_pilot/session.py usa Lock y un flag de módulo para arbitrar un solo aviso por proceso. docs/history-and-sqlite.md documenta que la memoria vectorial es opcional y SQLite continúa persistiendo turnos. No se ejecutaron pruebas en esta sesión.

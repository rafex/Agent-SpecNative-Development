# STACK.md

## Runtime

- **Lenguaje**: Rust.
- **Versión**: toolchain estable soportada por el proyecto; fijar la versión exacta al iniciar la implementación.
- **Distribución**: binario CLI pequeño, ejecutable localmente.

## Frameworks y protocolos

- **Cargo**: compilación, dependencias y pruebas.
- **stdio/JSON**: transporte inicial para integrar el agente con clientes y procesos de desarrollo.
- **MCP**: cliente/adaptador hacia el servidor SpecNative existente.
- **Modelo de lenguaje**: proveedor intercambiable detrás de un trait/interfaz; no se fija uno en esta etapa.

## Infraestructura

- **Persistencia**: archivos del repositorio, principalmente `spec-native/`.
- **Base de datos**: ninguna en el MVP.
- **Hosting**: local; no requerido para la primera versión.
- **CI/CD**: compilación, pruebas y validación de artefactos SpecNative.

## Integraciones

- **SpecNative MCP**: criticidad alta; proporciona la semántica y operaciones canónicas del framework.
- **Proveedor de modelo**: criticidad alta para la conversación, pero reemplazable y configurable.

## Restricciones

- Mantener bajo el número de dependencias y el tiempo de arranque.
- No incorporar un runtime de agentes generalista si una capa pequeña de orquestación es suficiente.
- La aplicación de plantillas debe ser una operación explícita y comprobable.

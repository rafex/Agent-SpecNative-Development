# PRODUCT.md

## Problema

Definir software con Spec-Driven Development requiere convertir una idea ambigua en contexto de producto, decisiones, especificaciones y criterios verificables. Hoy el programador debe conocer la estructura de SpecNative y recordar qué documento actualizar; los asistentes genéricos tienden a saltar a la implementación o a aplicar plantillas sin que se les pida.

## Usuarios

- **Programadores y equipos pequeños**: necesitan acompañamiento conversacional para aclarar el problema, alcance, usuarios, restricciones y criterios de aceptación antes de escribir código.
- **Agentes de desarrollo**: necesitan leer y actualizar el contexto canónico de SpecNative sin duplicar estado en una base externa.

## Objetivos

- Construir un agente especializado y muy ligero para definir trabajo con SpecNative.
- Guiar al programador mediante preguntas y propuestas hasta producir especificaciones claras, trazables y accionables.
- Cargar plantillas disponibles, pero aplicar una plantilla únicamente cuando el usuario haga una llamada explícita para usarla.
- Mantener el repositorio `spec-native/` como fuente de verdad y respetar sus estados, relaciones y workflows.
- Medir el éxito por la capacidad de producir una spec válida desde una conversación, reducir ambigüedad antes de implementar y evitar cambios automáticos no solicitados.

## No objetivos

- Ser un agente generalista de implementación, revisión de código, despliegue o administración de infraestructura.
- Elegir o aplicar una plantilla automáticamente por inferencia.
- Reemplazar el framework SpecNative o crear una segunda fuente de verdad fuera del repositorio.
- Fijar desde el inicio un proveedor específico de modelos o una interfaz de usuario pesada.

## Valor diferencial

El agente conoce el modelo documental y operativo de SpecNative, trabaja sobre el contexto real del repositorio y separa dos intenciones: ayudar a definir una spec y aplicar una plantilla. La segunda sólo ocurre tras una instrucción explícita del programador, haciendo el flujo predecible y controlable.

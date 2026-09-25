+++
doctype = "decision"
id = "DEC-0001"
title = "Credenciales ASN globales y por proyecto con SOPS/age"
status = "accepted"
created_at = "2026-09-25"
owners = []
related_specs = ["SPEC-0001"]
related_tasks = ["TASK-AGENTE-SPECNATIV-0007"]
related_architecture = []
supersedes = []
tags = ["asn", "credentials", "sops", "age"]
+++

# DEC-0001 - Credenciales ASN globales y por proyecto con SOPS/age

## Contexto

El CLI y los clientes MCP necesitan una forma guiada de configurar credenciales sin depender de exportarlas manualmente en cada proceso ni escribirlas en texto plano.

## Decisión

`asn --auth` configura credenciales globales por defecto en XDG_CONFIG_HOME/asn/agent.secrets.yaml, y `asn --auth --repo <ruta>` configura el proyecto. Los secretos de proyecto tienen prioridad, luego las credenciales SOPS globales y finalmente las variables de entorno. ASN genera y reutiliza la identidad local ~/.age/asn-key.txt si falta. Si faltan SOPS/age, muestra instrucciones de instalación y no instala paquetes automáticamente.

## Consecuencias

La configuración global funciona para distintos repositorios y los valores de proyecto pueden sobrescribirla. El archivo SOPS se comparte sólo donde se copie; la identidad age privada queda local a la máquina y debe conservarse para descifrar los secretos. Las variables siguen funcionando como fallback y MCP informa faltantes sin abrir prompts.

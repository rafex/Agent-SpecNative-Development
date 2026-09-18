#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Uso: $0 /ruta/al/proyecto" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

target="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
agent_root="$(cd "${script_dir}/../.." && pwd)"
source_adapter="${agent_root}/agent_spec_native.just"
source_manual="${agent_root}/docs/man_asn.md"

if [[ ! -d "${target}" ]]; then
  echo "SpecNative: el proyecto no existe: ${target}" >&2
  exit 2
fi
target="$(cd "${target}" && pwd)"
target_justfile="${target}/Justfile"
target_adapter="${target}/agent_spec_native.just"

if [[ ! -f "${source_adapter}" ]]; then
  echo "SpecNative: falta el adaptador canónico: ${source_adapter}" >&2
  exit 2
fi

has_import=0
if [[ -f "${target_justfile}" ]] && grep -Fqx "import 'agent_spec_native.just'" "${target_justfile}"; then
  has_import=1
fi

if [[ "${has_import}" -eq 0 && -f "${target_justfile}" ]] && just --summary --justfile "${target_justfile}" 2>/dev/null | grep -Eq '(^|[[:space:]])asn([[:space:]]|$)'; then
  echo "SpecNative: colisión detectada; el Justfile ya define asn." >&2
  exit 3
fi

if [[ -e "${target_adapter}" ]] && ! cmp -s "${source_adapter}" "${target_adapter}"; then
  echo "SpecNative: ${target_adapter} ya existe y no coincide con el adaptador canónico." >&2
  exit 3
fi
if [[ ! -e "${target_adapter}" ]]; then
  cp "${source_adapter}" "${target_adapter}"
fi

if [[ -f "${target_justfile}" ]]; then
  if [[ "${has_import}" -eq 0 ]]; then
    printf '\nimport '\''agent_spec_native.just'\''\n' >> "${target_justfile}"
  fi
else
  printf "import 'agent_spec_native.just'\n" > "${target_justfile}"
fi

if [[ -f "${source_manual}" && ! -e "${target}/docs/man_asn.md" ]]; then
  mkdir -p "${target}/docs"
  cp "${source_manual}" "${target}/docs/man_asn.md"
fi

if ! just --fmt --check --justfile "${target_justfile}"; then
  echo "SpecNative: el Justfile no supera la comprobación de formato tras la integración." >&2
  exit 4
fi

echo "SpecNative integrado en ${target}. Instala ASN con make install y ejecuta: just asn"

# Adaptador reutilizable para proyectos que ya instalaron `asn`.

asn:
    @if ! command -v asn >/dev/null 2>&1; then echo "SpecNative: no existe asn en PATH. Ejecuta make install en el repositorio del agente." >&2; exit 2; fi
    asn --repo "{{ justfile_directory() }}"

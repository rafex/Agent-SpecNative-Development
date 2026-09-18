# Adaptador reutilizable para integrar el piloto SpecNative en otro proyecto.
# Requiere SPECNATIVE_AGENT_ROOT apuntando a este repositorio del agente.

agent_root := env_var_or_default("SPECNATIVE_AGENT_ROOT", "")
agent_python := agent_root + "/.specnative/.venv/bin/python"
agent_mcp := agent_root + "/.specnative/specnative_mcp.py"

asn:
    @if [ -z "{{ agent_root }}" ]; then echo "SpecNative: configura SPECNATIVE_AGENT_ROOT antes de ejecutar just asn." >&2; exit 2; fi
    @if [ ! -x "{{ agent_python }}" ]; then echo "SpecNative: no existe el Python del agente en {{ agent_python }}. Ejecuta make setup en el repositorio del agente." >&2; exit 2; fi
    @if [ ! -f "{{ agent_mcp }}" ]; then echo "SpecNative: no existe el MCP en {{ agent_mcp }}." >&2; exit 2; fi
    PYTHONPATH="{{ agent_root }}/pilot/src" "{{ agent_python }}" -m specnative_pilot.cli --repo "{{ justfile_directory() }}" --mcp-python "{{ agent_python }}" --mcp-script "{{ agent_mcp }}" --preflight

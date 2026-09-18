# setup

Crea únicamente `.specnative/.venv` usando `PYTHON_BOOTSTRAP` y sincroniza las
dependencias de desarrollo con `uv.lock`. No modifica `PATH` ni instala
comandos globales.

```bash
make setup
just setup
```

# install

Instala `asn` y `asn-mcp` como herramientas de `uv`, sin activar un entorno
virtual. Para desarrollo usa `make setup`; esta receta no instala comandos
globales.

```bash
make install
```

Por defecto instala en `~/.local/bin`; una ejecución con `sudo` instala en
`/usr/local/bin`. Para pruebas se puede usar `make install BIN_DIR=/tmp/asn-bin`.

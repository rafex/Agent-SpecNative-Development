# install

Instala `asn` y `asn-mcp` como herramientas de `uv`, sin activar un entorno
virtual. Para desarrollo usa `make setup`; esta receta no instala comandos
globales.

```bash
make install
```

Por defecto instala en `~/.local/bin`; una ejecución con `sudo` instala en
`/usr/local/bin`. Para pruebas se puede usar `make install BIN_DIR=/tmp/asn-bin`.

La actualización del MCP se realiza al ejecutar `asn` o `asn-mcp`, fuera del
entorno administrado por `uv`; no es necesario reinstalar ASN para cada release
de SpecNative.

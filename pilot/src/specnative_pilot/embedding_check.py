from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlsplit


class EmbeddingTestError(RuntimeError):
    """Safe diagnostic error for an embeddings endpoint check."""


@dataclass(frozen=True)
class EmbeddingTestResult:
    model: str
    endpoint: str
    dimension: int
    elapsed_ms: float


def check_embeddings(*, api_key: str | None, model: str | None, base_url: str | None) -> EmbeddingTestResult:
    if not api_key:
        raise EmbeddingTestError("Falta la credencial del endpoint de embeddings.")
    if not model:
        raise EmbeddingTestError("Configura [agent].embedding_model antes de ejecutar `asn --test-embeddings`.")
    endpoint = (base_url or "https://api.openai.com/v1").rstrip("/")
    try:
        parts = urlsplit(endpoint)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError
        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = f":{parts.port}" if parts.port is not None else ""
        safe_endpoint = f"{parts.scheme}://{host}{port}{parts.path}"
    except ValueError as error:
        raise EmbeddingTestError("La URL de embeddings debe ser una dirección HTTP o HTTPS válida.") from error
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=endpoint)
        started = time.perf_counter()
        result = client.embeddings.create(model=model, input="ASN embedding connectivity check")
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not result.data or not result.data[0].embedding:
            raise EmbeddingTestError("El endpoint respondió sin un vector de embedding.")
        return EmbeddingTestResult(model=model, endpoint=safe_endpoint, dimension=len(result.data[0].embedding), elapsed_ms=elapsed_ms)
    except EmbeddingTestError:
        raise
    except Exception as error:
        status = getattr(error, "status_code", None)
        detail = f" HTTP {status}" if status else ""
        raise EmbeddingTestError(f"Falló la validación del endpoint de embeddings:{detail} {type(error).__name__}.") from error

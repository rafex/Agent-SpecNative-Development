from types import SimpleNamespace

import pytest

from specnative_pilot.embedding_check import EmbeddingTestError, check_embeddings


def test_embedding_check_reports_endpoint_model_dimension_and_time(monkeypatch):
    class Embeddings:
        def create(self, **kwargs):
            assert kwargs == {"model": "nomic-embed-text-v1.5", "input": "ASN embedding connectivity check"}
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: SimpleNamespace(embeddings=Embeddings()))
    result = check_embeddings(api_key="secret", model="nomic-embed-text-v1.5", base_url="https://embed.test/v1")
    assert result.endpoint == "https://embed.test/v1"
    assert result.dimension == 3
    assert result.elapsed_ms >= 0


def test_embedding_check_does_not_leak_credentials_in_errors(monkeypatch):
    class Embeddings:
        def create(self, **kwargs):
            raise RuntimeError("provider error secret")

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: SimpleNamespace(embeddings=Embeddings()))
    with pytest.raises(EmbeddingTestError) as error:
        check_embeddings(api_key="secret", model="embed", base_url="https://embed.test/v1")
    assert "secret" not in str(error.value)


def test_embedding_check_requires_model_and_key():
    with pytest.raises(EmbeddingTestError, match="Falta la credencial"):
        check_embeddings(api_key=None, model="embed", base_url=None)
    with pytest.raises(EmbeddingTestError, match="embedding_model"):
        check_embeddings(api_key="secret", model=None, base_url=None)

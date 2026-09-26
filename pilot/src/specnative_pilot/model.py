from __future__ import annotations

from smolagents import OpenAIServerModel

from .config import Config
from .secrets import SecretResolutionError, resolve_credentials


def build_model(config: Config) -> OpenAIServerModel:
    try:
        credentials = resolve_credentials(config)
    except SecretResolutionError as error:
        raise RuntimeError(str(error)) from error
    if not credentials.model:
        raise RuntimeError(
            "Falta el modelo ASN. Configura SPECNATIVE_AGENT_MODEL, [agent].model o ejecuta `asn --auth`."
        )
    if not credentials.api_key:
        raise RuntimeError(
            f"No existe una API key en el backend configurado ni en la variable {config.api_key_env}; "
            "configúrala en el entorno o ejecuta `asn --auth`."
        )
    model_options = {"reasoning_effort": config.reasoning_effort} if config.reasoning_effort else {}
    return OpenAIServerModel(
        model_id=credentials.model,
        api_base=credentials.api_base,
        api_key=credentials.api_key,
        **model_options,
    )

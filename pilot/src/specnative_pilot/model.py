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
        raise RuntimeError("Configura el modelo en el backend de secretos, SPECNATIVE_AGENT_MODEL o [agent].model.")
    if not credentials.api_key:
        raise RuntimeError(
            f"No existe una API key en el backend configurado ni en la variable {config.api_key_env}."
        )
    return OpenAIServerModel(
        model_id=credentials.model,
        api_base=credentials.api_base,
        api_key=credentials.api_key,
    )

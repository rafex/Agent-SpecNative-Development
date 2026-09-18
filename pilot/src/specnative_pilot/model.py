from __future__ import annotations

import os

from smolagents import OpenAIServerModel

from .config import Config


def build_model(config: Config) -> OpenAIServerModel:
    if not config.model:
        raise RuntimeError("Configura SPECNATIVE_AGENT_MODEL o [agent].model antes de iniciar el piloto.")
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise RuntimeError(f"No existe la variable de entorno {config.api_key_env}.")
    return OpenAIServerModel(
        model_id=config.model,
        api_base=config.api_base,
        api_key=api_key,
    )

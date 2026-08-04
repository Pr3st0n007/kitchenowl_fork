"""LLM-backed recipe agent.

This package provides:

* :class:`LLMProvider` and :class:`OpenAICompatibleProvider` -- thin wrappers
  around ``litellm`` for chat completions with tool calling.
* :class:`RecipeAgent` -- runs the agent loop, executes tools using
  :mod:`app.service.agent_tools`, persists messages and reports the final
  assistant reply.

The provider is intentionally tiny: by going through litellm, we get OpenAI,
Google Gemini (`gemini/...` model prefix or the OpenAI-compatibility
endpoint) and any other OpenAI-compatible HTTP API for free.
"""

from .agent import RecipeAgent
from .provider import LLMError, LLMProvider, OpenAICompatibleProvider, get_provider

__all__ = [
    "LLMError",
    "LLMProvider",
    "OpenAICompatibleProvider",
    "RecipeAgent",
    "get_provider",
]

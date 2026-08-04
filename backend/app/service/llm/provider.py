"""LLM provider abstraction backed by ``litellm``."""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import urlparse

from app.models.llm_config import LLMConfig, LLMProviderType

_logger = logging.getLogger(__name__)
_BUILTIN_PROVIDER_HOSTS = {
    LLMProviderType.OPENAI: {"api.openai.com"},
    LLMProviderType.GEMINI: {"generativelanguage.googleapis.com"},
}


class LLMError(Exception):
    """Raised when the configured LLM endpoint cannot be reached or refuses the request."""


def _empty_tool_calls() -> list[dict[str, Any]]:
    return []


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=_empty_tool_calls)
    raw: dict[str, Any] | None = None


def _mapping_to_dict(value: Mapping[Any, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in value.items()}


def _obj_get(
    obj: object | None, key: str, default: object | None = None
) -> object | None:
    if obj is None:
        return default
    if isinstance(obj, dict):
        data = cast(dict[str, Any], obj)
        return data.get(key, default)
    return getattr(obj, key, default)


def _as_str(value: object | None, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _parse_allowed_hosts(env_value: str | None) -> set[str]:
    if not env_value:
        return set()
    return {h.strip().lower() for h in env_value.split(",") if h.strip()}


def validate_endpoint_url(url: str) -> str:
    """Validate an outbound HTTP endpoint and return its normalized hostname."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise LLMError("LLM endpoint URL is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise LLMError("LLM endpoint URL must use http or https and include a host")
    if parsed.username or parsed.password:
        raise LLMError("LLM endpoint URL must not contain credentials")
    return hostname.lower()


def _is_non_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return not address.is_global


def _model_id_for(config: LLMConfig) -> str:
    """Return the model string passed to litellm.

    For Gemini we prefer the native ``gemini/<model>`` provider so litellm
    can use the official Generative Language API; otherwise we use the
    user-supplied model verbatim, which makes litellm fall back to the
    custom ``api_base`` (OpenAI-compatible).
    """
    model = (config.model or "").strip()
    if not model:
        raise LLMError("LLM config does not have a model name")

    if config.provider == LLMProviderType.GEMINI and "/" not in model:
        return f"gemini/{model}"
    return model


class LLMProvider:
    """Base class. Subclasses implement :meth:`chat`."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    def generate_image(self, prompt: str) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """Provider that delegates to ``litellm.completion``.

    Supports OpenAI, Gemini (via either the native ``gemini/`` route or the
    OpenAI-compatible REST endpoint) and arbitrary OpenAI-compatible servers
    (Ollama, vLLM, OpenRouter, LM Studio, ...).
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._enforce_outbound_allowlist()

    # ------------------------------------------------------------------ helpers

    def _enforce_outbound_allowlist(self) -> None:
        allowed = _parse_allowed_hosts(os.getenv("LLM_ALLOWED_HOSTS"))
        base_url = self.config.effective_base_url()
        hostname = validate_endpoint_url(base_url) if base_url else None
        # Native Gemini route doesn't need a base URL but always hits Google.
        if hostname is None and self.config.provider == LLMProviderType.GEMINI:
            hostname = "generativelanguage.googleapis.com"
        if hostname is None:
            raise LLMError("The configured LLM provider has no endpoint URL")
        if allowed:
            if hostname not in allowed:
                raise LLMError(
                    f"LLM endpoint host '{hostname}' is not in LLM_ALLOWED_HOSTS"
                )
            return
        if hostname not in _BUILTIN_PROVIDER_HOSTS.get(self.config.provider, set()):
            raise LLMError(
                f"LLM endpoint host '{hostname}' is not in LLM_ALLOWED_HOSTS"
            )

        try:
            addresses: set[str] = set()
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM):
                sockaddr = item[4]
                if not sockaddr:
                    continue
                host = sockaddr[0]
                if isinstance(host, str):
                    addresses.add(host)
        except socket.gaierror as exc:
            raise LLMError(
                f"LLM endpoint host '{hostname}' cannot be resolved"
            ) from exc
        if any(_is_non_public_address(address) for address in addresses):
            raise LLMError(
                f"LLM endpoint host '{hostname}' resolves to a non-public address; "
                "add it to LLM_ALLOWED_HOSTS to allow it explicitly"
            )

    # ------------------------------------------------------------------ chat

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        try:
            # Imported lazily so test code can patch the module-level name and
            # so importing this module never triggers litellm's network probes.
            import litellm
        except Exception as exc:  # pragma: no cover - import-time failure
            raise LLMError(f"litellm is not available: {exc}") from exc
        litellm_any: Any = litellm
        completion: Callable[..., object] = cast(
            Callable[..., object], litellm_any.completion
        )

        kwargs: dict[str, Any] = {
            "model": _model_id_for(self.config),
            "messages": messages,
            "api_key": self.config.get_api_key(),
            "timeout": 60,
            "num_retries": 0,
        }

        base_url = self.config.effective_base_url()
        # litellm's native ``gemini/`` route talks to Google's Generative
        # Language API directly and ignores ``api_base``. Worse, if the
        # OpenAI-compatible URL is forwarded as ``api_base`` Google's REST
        # endpoint returns 404. Only forward ``api_base`` when the user
        # explicitly configured one.
        model_id = kwargs["model"]
        if base_url and not model_id.startswith("gemini/"):
            kwargs["api_base"] = base_url

        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens
        # Per-call temperature (e.g. from a persona) overrides the
        # household-level default. Falls back to ``config.temperature``.
        effective_temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        if effective_temperature is not None:
            kwargs["temperature"] = effective_temperature

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = completion(**kwargs)
        except Exception as exc:
            detail = str(exc)
            for attr in ("response", "llm_provider", "message"):
                val = getattr(exc, attr, None)
                if val is not None:
                    body = getattr(val, "text", None) or getattr(val, "content", None)
                    if body:
                        detail += f" | {attr}.body={body!r}"
                    else:
                        detail += f" | {attr}={val!r}"
            _logger.warning("LLM call failed: %s\nrepr=%r", detail, exc, exc_info=True)
            raise LLMError(detail) from exc

        return _normalize_response(response)

    def generate_image(self, prompt: str) -> str:
        try:
            import litellm
        except Exception as exc:
            raise LLMError(f"litellm is not available: {exc}") from exc
        litellm_any: Any = litellm
        image_generation: Callable[..., object] = cast(
            Callable[..., object], litellm_any.image_generation
        )

        model = self.config.icon_generation_model or "dall-e-3"

        if self.config.provider == LLMProviderType.GEMINI and "/" not in model:
            model = f"gemini/{model}"

        kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "api_key": self.config.get_api_key(),
        }

        base_url = self.config.effective_base_url()
        # Mirror chat behavior: native ``gemini/...`` image routes must not
        # receive OpenAI-compatible ``api_base`` URLs (Google returns 404).
        if base_url and not model.startswith("gemini/"):
            kwargs["api_base"] = base_url

        try:
            response_obj: object = image_generation(**kwargs)
            data_obj = _obj_get(response_obj, "data")
            data: list[object]
            if isinstance(data_obj, Sequence) and not isinstance(
                data_obj, (str, bytes, bytearray)
            ):
                data = list(cast(Sequence[object], data_obj))
            else:
                data = []
            if not data:
                raise LLMError("Image generation did not return any images")

            first = data[0]
            image_url = _as_str(_obj_get(first, "url"), "")
            if not image_url:
                raise LLMError("Image generation response did not include an image URL")
            return image_url
        except Exception as exc:
            _logger.warning("LLM image generation failed: %s", exc, exc_info=True)
            raise LLMError(_friendly_image_error_message(exc)) from exc


def _friendly_image_error_message(exc: Exception) -> str:
    detail = str(exc)
    lower = detail.lower()
    is_rate_limited = (
        "ratelimiterror" in lower
        or "resource_exhausted" in lower
        or "quota exceeded" in lower
        or "429" in lower
    )
    if not is_rate_limited:
        return detail

    retry_hint = None
    retry_in_match = re.search(r"please retry in\s+([0-9.]+)s", detail, re.IGNORECASE)
    if retry_in_match:
        retry_hint = retry_in_match.group(1)
    else:
        retry_delay_match = re.search(
            r'"retryDelay"\s*:\s*"([^"]+)"', detail, re.IGNORECASE
        )
        if retry_delay_match:
            retry_hint = retry_delay_match.group(1)

    message = "Image generation is rate limited by the provider quota."
    if retry_hint:
        message += f" Retry after about {retry_hint}s."
    message += " Check Gemini API quota and billing settings."
    return message


def _normalize_response(response: object) -> LLMResponse:
    """Normalise a litellm ``ModelResponse`` into our :class:`LLMResponse`.

    litellm exposes either an OpenAI-shaped object with attribute access or
    a plain dict, depending on the provider, so handle both.
    """

    choices_obj = _obj_get(response, "choices", [])
    choices: list[object]
    if isinstance(choices_obj, Sequence) and not isinstance(
        choices_obj, (str, bytes, bytearray)
    ):
        choices = list(cast(Sequence[object], choices_obj))
    else:
        choices = []
    if not choices:
        return LLMResponse(content=None, raw=_safe_dict(response))
    message_obj = _obj_get(choices[0], "message", {})
    content_obj = _obj_get(message_obj, "content")
    raw_tool_calls_obj = _obj_get(message_obj, "tool_calls", [])
    raw_tool_calls: list[object]
    if isinstance(raw_tool_calls_obj, Sequence) and not isinstance(
        raw_tool_calls_obj, (str, bytes, bytearray)
    ):
        raw_tool_calls = list(cast(Sequence[object], raw_tool_calls_obj))
    else:
        raw_tool_calls = []

    tool_calls: list[dict[str, Any]] = []
    for tc_obj in raw_tool_calls:
        function_obj = _obj_get(tc_obj, "function", {})
        tool_calls.append(
            {
                "id": _as_str(_obj_get(tc_obj, "id")),
                "type": _as_str(_obj_get(tc_obj, "type"), "function"),
                "function": {
                    "name": _as_str(_obj_get(function_obj, "name")),
                    "arguments": _as_str(_obj_get(function_obj, "arguments")),
                },
            }
        )

    return LLMResponse(
        content=content_obj if isinstance(content_obj, str) else None,
        tool_calls=tool_calls,
        raw=_safe_dict(response),
    )


def _safe_dict(obj: object | None) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return _mapping_to_dict(cast(Mapping[Any, Any], obj))
    for attr in ("model_dump", "dict", "to_dict"):
        method = getattr(obj, attr, None)
        if callable(method):
            try:
                result = method()
                if isinstance(result, Mapping):
                    return _mapping_to_dict(cast(Mapping[Any, Any], result))
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                _logger.debug("Failed serializing LLM response via %s: %s", attr, exc)
                continue
    return None


def get_provider(config: LLMConfig) -> LLMProvider:
    """Return the provider implementation for ``config``."""
    return OpenAICompatibleProvider(config)

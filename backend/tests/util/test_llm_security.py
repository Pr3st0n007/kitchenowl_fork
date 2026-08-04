# pyright: reportPrivateUsage=false
# ruff: noqa: I001

import sys
from types import SimpleNamespace
from typing import Any, cast
from app.config import _validate_jwt_secret
from app.helpers.safe_error import safe_error_message
from app.models.llm_config import LLMConfig, LLMProviderType
from app.service.llm.provider import (
    LLMError,
    OpenAICompatibleProvider,
    validate_endpoint_url,
)
import pytest


class _FakeRateLimitError(Exception):
    pass


def test_production_jwt_secret_must_be_strong():
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        _validate_jwt_secret("PLEASE_CHANGE_ME", allow_insecure=False)
    assert _validate_jwt_secret("x" * 32, allow_insecure=False) == "x" * 32


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "not-a-url", "https://user:secret@example.com/v1"],
)
def test_llm_endpoint_rejects_unsafe_url_shapes(url: str):
    with pytest.raises(LLMError):
        validate_endpoint_url(url)


def test_private_llm_endpoint_requires_explicit_allowlist(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("LLM_ALLOWED_HOSTS", raising=False)
    config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.CUSTOM,
            effective_base_url=lambda: "http://llm.internal:11434/v1",
        ),
    )
    with pytest.raises(LLMError, match="not in LLM_ALLOWED_HOSTS"):
        OpenAICompatibleProvider(config)


def test_allowlist_explicitly_permits_private_llm_endpoint(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LLM_ALLOWED_HOSTS", "llm.internal")
    config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.CUSTOM,
            effective_base_url=lambda: "http://llm.internal:11434/v1",
        ),
    )
    OpenAICompatibleProvider(config)


def test_configured_allowlist_also_restricts_builtin_provider(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LLM_ALLOWED_HOSTS", "llm.internal")
    config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.OPENAI,
            effective_base_url=lambda: "https://api.openai.com/v1",
        ),
    )
    with pytest.raises(LLMError, match="not in LLM_ALLOWED_HOSTS"):
        OpenAICompatibleProvider(config)


def test_safe_error_message_is_single_line_and_capped():
    message = safe_error_message(ValueError("visible\n" + "secret" * 100))
    assert message == "visible"
    assert len(safe_error_message(ValueError("x" * 300))) == 200


def test_generate_image_prefixes_gemini_models(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_image_generation(**kwargs: Any):
        captured.update(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(url="https://example.test/icon.png")]
        )

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(image_generation=fake_image_generation),
    )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.GEMINI,
            icon_generation_model="gemini-flash-latest",
            get_api_key=lambda: "test-key",
            effective_base_url=lambda: None,
        ),
    )

    assert provider.generate_image("draw an icon") == "https://example.test/icon.png"
    assert captured["model"] == "gemini/gemini-flash-latest"
    assert captured["prompt"] == "draw an icon"


def test_generate_image_ignores_api_base_for_native_gemini(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    def fake_image_generation(**kwargs: Any):
        captured.update(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(url="https://example.test/icon.png")]
        )

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(image_generation=fake_image_generation),
    )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.GEMINI,
            icon_generation_model="imagen-3.0-fast-generate-001",
            get_api_key=lambda: "test-key",
            effective_base_url=lambda: (
                "https://generativelanguage.googleapis.com/v1beta/openai/"
            ),
        ),
    )

    assert provider.generate_image("draw an icon") == "https://example.test/icon.png"
    assert captured["model"] == "gemini/imagen-3.0-fast-generate-001"
    assert "api_base" not in captured


def test_generate_image_rate_limit_error_is_user_friendly(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_image_generation(**kwargs: Any):
        raise _FakeRateLimitError(
            """{
  \"error\": {
    \"code\": 429,
    \"message\": \"Quota exceeded. Please retry in 54.096s.\",
    \"status\": \"RESOURCE_EXHAUSTED\"
  }
}"""
        )

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(image_generation=fake_image_generation),
    )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.GEMINI,
            icon_generation_model="gemini-2.5-flash-image",
            get_api_key=lambda: "test-key",
            effective_base_url=lambda: None,
        ),
    )

    with pytest.raises(LLMError) as exc_info:
        provider.generate_image("draw an icon")

    assert "rate limited" in str(exc_info.value).lower()
    assert "retry after about 54.096s" in str(exc_info.value).lower()


def test_generate_image_raises_clear_error_on_empty_data(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_image_generation(**kwargs: Any):
        return SimpleNamespace(data=[])

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(image_generation=fake_image_generation),
    )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.config = cast(
        LLMConfig,
        SimpleNamespace(
            provider=LLMProviderType.GEMINI,
            icon_generation_model="gemini-2.5-flash-image",
            get_api_key=lambda: "test-key",
            effective_base_url=lambda: None,
        ),
    )

    with pytest.raises(LLMError, match="did not return any images"):
        provider.generate_image("draw an icon")

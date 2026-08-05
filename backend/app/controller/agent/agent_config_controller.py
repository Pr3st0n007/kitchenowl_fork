"""Per-household LLM configuration endpoints."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
import base64
from types import SimpleNamespace

import blurhash
import requests
from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from PIL import Image
from werkzeug.utils import secure_filename

from app.config import UPLOAD_FOLDER
from app.errors import InvalidUsage
from app.helpers import RequiredRights, authorize_household, validate_args
from app.helpers.safe_error import safe_error_message
from app.models import HouseholdMember, LLMConfig
from app.models.file import File
from app.models.llm_config import LLMProviderType
from app.service.llm.provider import LLMError, get_provider

from .schemas import UpdateLLMConfig

agentConfigHousehold = Blueprint("agentConfig", __name__)

_logger = logging.getLogger(__name__)
_DEFAULT_GEMINI_MODEL = "gemini-flash-latest"


# Fields a non-admin household member is allowed to see. The system prompt,
# base URL etc. may contain operator-specific notes and must stay admin-only.
_MEMBER_VISIBLE_FIELDS = (
    "household_id",
    "provider",
    "model",
    "enabled",
    "api_key_set",
)


def _is_household_admin(household_id: int) -> bool:
    if not current_user:
        return False
    if getattr(current_user, "admin", False):
        return True
    member = HouseholdMember.find_by_ids(household_id, current_user.id)
    return bool(member and member.admin)


def _redact_config(full: dict) -> dict:
    return {k: full[k] for k in _MEMBER_VISIBLE_FIELDS if k in full}


def _derive_icon_name(subject: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", subject.lower()).strip()
    if not cleaned:
        return "generated"
    return cleaned.split()[0]


def _render_icon_prompt(template: str, subject: str) -> str:
    prompt = template.replace("{name}", subject)
    prompt = prompt.replace("[SUBJECT]", subject)
    return prompt


def _image_bytes_from_provider_response(image_ref: str) -> bytes:
    if image_ref.startswith("data:image/"):
        _, _, payload = image_ref.partition(",")
        if not payload:
            raise InvalidUsage("Generated image data URL was empty")
        try:
            return base64.b64decode(payload, validate=True)
        except Exception as exc:  # pragma: no cover - defensive
            raise InvalidUsage(f"Generated image data URL was invalid: {exc}") from exc

    try:
        response = requests.get(image_ref, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as exc:
        raise InvalidUsage(f"Failed to download generated image: {exc}")


def _parse_json_object_request() -> dict:
    req = request.get_json(silent=True)
    if req is None:
        raw_body = request.get_data(cache=False, as_text=True).strip()
        if raw_body:
            try:
                req = json.loads(raw_body)
            except ValueError:
                req = {}
        else:
            req = {}
    if not isinstance(req, dict):
        return {}
    return req


def _normalize_nullable_str(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _build_test_config(cfg: LLMConfig, overrides: dict) -> SimpleNamespace:
    provider = cfg.provider
    if "provider" in overrides:
        raw_provider = _normalize_nullable_str(overrides.get("provider"))
        if raw_provider is None:
            raise InvalidUsage("Provider is required to run a test")
        try:
            provider = LLMProviderType(raw_provider)
        except ValueError as exc:
            raise InvalidUsage("Invalid provider") from exc

    model = cfg.model
    if "model" in overrides:
        model = _normalize_nullable_str(overrides.get("model"))
    if provider == LLMProviderType.GEMINI and not model:
        model = _DEFAULT_GEMINI_MODEL

    base_url = cfg.base_url
    if "base_url" in overrides:
        base_url = _normalize_nullable_str(overrides.get("base_url"))

    icon_generation_prompt = cfg.icon_generation_prompt
    if "icon_generation_prompt" in overrides:
        icon_generation_prompt = _normalize_nullable_str(
            overrides.get("icon_generation_prompt")
        )

    icon_generation_model = cfg.icon_generation_model
    if "icon_generation_model" in overrides:
        icon_generation_model = _normalize_nullable_str(
            overrides.get("icon_generation_model")
        )

    api_key = cfg.get_api_key()
    if "api_key" in overrides:
        api_key = _normalize_nullable_str(overrides.get("api_key"))

    return SimpleNamespace(
        provider=provider,
        model=model,
        base_url=base_url,
        icon_generation_prompt=icon_generation_prompt,
        icon_generation_model=icon_generation_model,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        default_base_url=lambda: cfg.default_base_url(),
        effective_base_url=lambda: base_url or cfg.default_base_url(),
        get_api_key=lambda: api_key,
        has_api_key=lambda: bool(api_key),
    )


@agentConfigHousehold.route("/config", methods=["GET"])
@jwt_required()
@authorize_household()
def get_config(household_id):
    cfg = LLMConfig.get_or_create(household_id)
    full = cfg.obj_to_dict()
    if _is_household_admin(household_id):
        return jsonify(full)
    # Members only see what they need to decide whether to show the chat
    # entry point: provider/model/enabled/api_key_set. Admin-only fields
    # (system prompt, base URL, tuning parameters) are stripped.
    return jsonify(_redact_config(full))


@agentConfigHousehold.route("/config", methods=["PUT"])
@jwt_required()
@authorize_household(required=RequiredRights.ADMIN)
@validate_args(UpdateLLMConfig)
def update_config(args, household_id):
    cfg = LLMConfig.get_or_create(household_id)

    if "provider" in args:
        cfg.provider = LLMProviderType(args["provider"])
    if "base_url" in args:
        cfg.base_url = (args["base_url"] or "").strip() or None
    if "model" in args:
        cfg.model = (args["model"] or "").strip() or None
    elif cfg.provider == LLMProviderType.GEMINI and not (cfg.model or "").strip():
        # When Gemini is selected without an explicit model, use the
        # lightweight multimodal default that works for image+text prompts.
        cfg.model = _DEFAULT_GEMINI_MODEL
    if "api_key" in args:
        cfg.set_api_key(args["api_key"])
    if "brave_search_api_key" in args:
        cfg.set_brave_search_api_key(args["brave_search_api_key"])
    if "system_prompt" in args:
        cfg.system_prompt = args["system_prompt"]
    if "initial_greeting" in args:
        raw = args["initial_greeting"]
        cfg.initial_greeting = (raw or "").strip() or None
    if "icon_generation_prompt" in args:
        cfg.icon_generation_prompt = args["icon_generation_prompt"]
    if "icon_generation_model" in args:
        cfg.icon_generation_model = (
            args["icon_generation_model"] or ""
        ).strip() or None
    if "enabled" in args:
        cfg.enabled = bool(args["enabled"])
    if "max_tokens" in args:
        cfg.max_tokens = args["max_tokens"]
    if "temperature" in args:
        cfg.temperature = args["temperature"]

    cfg.save()
    return jsonify(cfg.obj_to_dict())


@agentConfigHousehold.route("/config/generate-icon", methods=["POST"])
@jwt_required()
@authorize_household()
def generate_icon(household_id):
    cfg = LLMConfig.find_by_household(household_id)
    if not cfg or not cfg.has_api_key():
        raise InvalidUsage("LLM Provider is not configured")

    req = _parse_json_object_request()
    item_name = str(req.get("name") or "Unknown item").strip() or "Unknown item"

    try:
        provider = get_provider(cfg)
    except LLMError as exc:
        raise InvalidUsage(str(exc))
    prompt = (
        cfg.icon_generation_prompt
        or "An icon for the ingredient {name}, minimalist, flat vector style, solid colors."
    )
    prompt = _render_icon_prompt(prompt, item_name)

    try:
        image_url = provider.generate_image(prompt)
    except LLMError as exc:
        raise InvalidUsage(str(exc))

    image_bytes = _image_bytes_from_provider_response(image_url)

    filename = secure_filename(str(uuid.uuid4()) + ".png")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    blur = None
    try:
        with Image.open(filepath) as image:
            image.thumbnail((100, 100))
            blur = blurhash.encode(image, x_components=4, y_components=3)
    except Exception:
        pass

    f = File(filename=filename, blur_hash=blur, created_by=current_user.id).save()

    return jsonify(
        {
            "filename": filename,
            "subject": item_name,
            "icon_name": _derive_icon_name(item_name),
        }
    )


@agentConfigHousehold.route("/config/test", methods=["POST"])
@jwt_required()
@authorize_household(required=RequiredRights.ADMIN)
def test_config(household_id):
    cfg = LLMConfig.find_by_household(household_id)
    if not cfg:
        raise InvalidUsage("Provider, model and API key are required to run a test")

    req = _parse_json_object_request()
    test_cfg = _build_test_config(cfg, req)

    if not test_cfg.model or not test_cfg.has_api_key():
        raise InvalidUsage("Provider, model and API key are required to run a test")

    try:
        provider = get_provider(test_cfg)
    except LLMError as exc:
        _logger.info("LLM connection test setup failed: %s", exc)
        return jsonify(
            {"ok": False, "error": safe_error_message(exc, "LLM provider error")}
        ), 200
    try:
        chat_response = provider.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a connection test. Reply with the single word 'ok'.",
                },
                {"role": "user", "content": "ping"},
            ],
            tools=None,
        )
    except LLMError as exc:
        _logger.info("LLM connection test failed: %s", exc)
        return jsonify(
            {"ok": False, "error": safe_error_message(exc, "LLM provider error")}
        ), 200

    image_prompt = (
        test_cfg.icon_generation_prompt
        or "An icon for the ingredient {name}, minimalist, flat vector style, solid colors."
    )
    image_prompt = _render_icon_prompt(image_prompt, "test ingredient")
    try:
        provider.generate_image(image_prompt)
    except LLMError as exc:
        _logger.info("LLM image generation test failed: %s", exc)
        return jsonify(
            {
                "ok": False,
                "error": safe_error_message(
                    exc,
                    "Image generation check failed for the configured provider/model",
                ),
            }
        ), 200

    return jsonify(
        {
            "ok": True,
            "reply": (chat_response.content or "").strip()[:200],
        }
    )

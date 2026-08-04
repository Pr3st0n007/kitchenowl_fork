"""Per-household LLM configuration endpoints."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from flask_jwt_extended import current_user, jwt_required

from app.errors import InvalidUsage
from app.helpers import RequiredRights, authorize_household, validate_args
from app.helpers.safe_error import safe_error_message
from app.models import HouseholdMember, LLMConfig
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
        cfg.icon_generation_model = (args["icon_generation_model"] or "").strip() or None
    if "enabled" in args:
        cfg.enabled = bool(args["enabled"])
    if "max_tokens" in args:
        cfg.max_tokens = args["max_tokens"]
    if "temperature" in args:
        cfg.temperature = args["temperature"]

    cfg.save()
    return jsonify(cfg.obj_to_dict())


import os
import uuid
import blurhash
from PIL import Image
from flask import request
import requests
from werkzeug.utils import secure_filename
from app.config import UPLOAD_FOLDER
from app.models.file import File

@agentConfigHousehold.route("/config/generate-icon", methods=["POST"])
@jwt_required()
@authorize_household()
def generate_icon(household_id):
    cfg = LLMConfig.find_by_household(household_id)
    if not cfg or not cfg.has_api_key():
        raise InvalidUsage("LLM Provider is not configured")

    req = request.json or {}
    item_name = req.get("name", "Unknown item")

    provider = get_provider(cfg)
    prompt = cfg.icon_generation_prompt or "An icon for the ingredient {name}, minimalist, flat vector style, solid colors."
    prompt = prompt.replace("{name}", item_name)

    try:
        image_url = provider.generate_image(prompt)
    except LLMError as exc:
        raise InvalidUsage(str(exc))

    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        raise InvalidUsage(f"Failed to download generated image: {exc}")

    filename = secure_filename(str(uuid.uuid4()) + ".png")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(response.content)

    blur = None
    try:
        with Image.open(filepath) as image:
            image.thumbnail((100, 100))
            blur = blurhash.encode(image, x_components=4, y_components=3)
    except Exception:
        pass

    f = File(filename=filename, blur_hash=blur, created_by=current_user.id).save()

    return jsonify({"filename": filename})

@agentConfigHousehold.route("/config/test", methods=["POST"])
@jwt_required()
@authorize_household(required=RequiredRights.ADMIN)
def test_config(household_id):
    cfg = LLMConfig.find_by_household(household_id)
    if not cfg or not cfg.model or not cfg.has_api_key():
        raise InvalidUsage("Provider, model and API key are required to run a test")

    provider = get_provider(cfg)
    try:
        response = provider.chat(
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

    return jsonify(
        {
            "ok": True,
            "reply": (response.content or "").strip()[:200],
        }
    )

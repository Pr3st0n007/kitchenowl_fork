from flask import Blueprint, jsonify

from app.config import (
    BACKEND_VERSION,
    DISABLE_USERNAME_PASSWORD_LOGIN,
    EMAIL_MANDATORY,
    MIN_FRONTEND_VERSION,
    OPEN_REGISTRATION,
    PRIVACY_POLICY_URL,
    SUPPORTED_LANGUAGES,
    TERMS_URL,
    oidc_clients,
)

health = Blueprint("health", __name__)


@health.route("", methods=["GET"])
def get_health():
    info = {
        "msg": "OK",
        "version": BACKEND_VERSION,
        "min_frontend_version": MIN_FRONTEND_VERSION,
        "oidc_provider": list(oidc_clients.keys()),
    }
    if PRIVACY_POLICY_URL:
        info["privacy_policy"] = PRIVACY_POLICY_URL
    if TERMS_URL:
        info["terms"] = TERMS_URL
    if OPEN_REGISTRATION:
        info["open_registration"] = True
    if EMAIL_MANDATORY:
        info["email_mandatory"] = True
    if DISABLE_USERNAME_PASSWORD_LOGIN:
        info["disable_username_password_login"] = True
    info["feature_llm_agent"] = True
    return jsonify(info)


@health.route("/supported-languages", methods=["GET"])
def getSupportedLanguages():
    return jsonify(SUPPORTED_LANGUAGES)

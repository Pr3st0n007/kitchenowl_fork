import os
from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app import db
from app.config import (
    JWT_ACCESS_TOKEN_EXPIRES,
    JWT_REFRESH_TOKEN_EXPIRES,
    UPLOAD_FOLDER,
)
from app.helpers import server_admin_required
from app.models import Household, OIDCLink, Token, User

analytics = Blueprint("analytics", __name__)


@analytics.route("", methods=["GET"])
@jwt_required()
@server_admin_required()
def getBaseAnalytics():
    statvfs = os.statvfs(UPLOAD_FOLDER)
    return jsonify(
        {
            "users": {
                "total": User.count(),
                "verified": User.query.filter(User.email_verified.is_(True)).count(),
                "active": db.session.query(Token.user_id)
                .filter(Token.type == "refresh")
                .group_by(Token.user_id)
                .count(),
                "wau": db.session.query(Token.user_id)
                .filter(
                    Token.type == "refresh",
                    Token.created_at
                    >= datetime.now(UTC).date()
                    - timedelta(days=datetime.now(UTC).weekday()),
                )
                .group_by(Token.user_id)
                .count(),
                "dau": db.session.query(Token.user_id)
                .filter(
                    Token.type == "refresh",
                    Token.created_at >= datetime.now(UTC).date(),
                )
                .group_by(Token.user_id)
                .count(),
                "online": db.session.query(Token.user_id)
                .filter(
                    Token.type == "access",
                    Token.created_at >= datetime.now(UTC) - JWT_ACCESS_TOKEN_EXPIRES,
                )
                .group_by(Token.user_id)
                .count(),
                "old": User.query.filter(
                    User.created_at <= datetime.now(UTC) - JWT_REFRESH_TOKEN_EXPIRES
                ).count(),
                "old_active": User.query.filter(
                    User.created_at <= datetime.now(UTC) - JWT_REFRESH_TOKEN_EXPIRES
                )
                .filter(
                    User.id.in_(
                        db.session.query(Token.user_id)
                        .filter(Token.type == "refresh")
                        .group_by(Token.user_id)
                        .subquery()
                        .select()
                    )
                )
                .count(),
                "linked_account": db.session.query(OIDCLink.user_id)
                .group_by(OIDCLink.user_id)
                .count(),
            },
            "free_storage": statvfs.f_frsize * statvfs.f_bavail,
            "available_storage": statvfs.f_frsize * statvfs.f_blocks,
            "households": {
                "total": Household.count(),
                "expense_feature": Household.query.filter(
                    Household.expenses_feature.is_(True)
                ).count(),
                "planner_feature": Household.query.filter(
                    Household.planner_feature.is_(True)
                ).count(),
            },
        }
    )

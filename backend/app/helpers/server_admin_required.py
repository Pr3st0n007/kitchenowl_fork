from functools import wraps

from flask_jwt_extended import current_user

from app.errors import ForbiddenRequest, getClientIp


def server_admin_required():
    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            if not current_user or not current_user.admin:
                raise ForbiddenRequest(
                    message=f"Elevated rights required. IP {getClientIp()}"
                )
            return func(*args, **kwargs)

        return decorator

    return wrapper

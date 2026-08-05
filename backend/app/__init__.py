from app.config import (
    app as app,
    celery_app as celery_app,
    db as db,
    jwt as jwt,
    scheduler as scheduler,
    socketio as socketio,
)

# Import modules that register routes/jobs/sockets only after core
# extensions are exposed on `app` to avoid circular import issues.
from app.api import *  # noqa: F403
from app.controller import *  # noqa: F403
from app.jobs import *  # noqa: F403
from app.sockets import *  # noqa: F403

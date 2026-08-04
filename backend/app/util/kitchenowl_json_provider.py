import enum
from datetime import UTC, date, datetime

from flask.json.provider import DefaultJSONProvider


class KitchenOwlJSONProvider(DefaultJSONProvider):
    def default(self, o):  # type: ignore[assignment]
        if isinstance(o, (datetime, date)):
            return int(round(o.replace(tzinfo=UTC).timestamp() * 1000))
        if isinstance(o, enum.Enum):
            return int(o.value)

        return super().default(o)

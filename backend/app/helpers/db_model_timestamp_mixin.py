from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class DbModelTimestampMixin:
    """
    Provides the :attr:`created_at` and :attr:`updated_at` audit timestamps
    """

    #: Timestamp for when this instance was created in UTC
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    #: Timestamp for when this instance was last updated in UTC
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    created_at._creation_order = 9998
    updated_at._creation_order = 9999

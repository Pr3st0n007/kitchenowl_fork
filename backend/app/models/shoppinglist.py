from typing import TYPE_CHECKING, Any, Self, cast

from sqlalchemy.orm import Mapped

from app import db
from app.helpers import DbModelAuthorizeMixin

Model = db.Model
if TYPE_CHECKING:
    from app.helpers.db_model_base import DbModelBase
    from app.models import History, Household, Item, Shoppinglist, User

    Model = DbModelBase


class Shoppinglist(Model, DbModelAuthorizeMixin):
    __tablename__ = "shoppinglist"

    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    name: Mapped[str] = db.Column(db.String(128))

    household_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("household.id"), nullable=False, index=True
    )

    household: Mapped[Household] = cast(
        Mapped["Household"],
        db.relationship(
            "Household",
            uselist=False,
        ),
    )
    items: Mapped[list["ShoppinglistItems"]] = cast(
        Mapped[list["ShoppinglistItems"]],
        db.relationship(
            "ShoppinglistItems",
            cascade="all, delete-orphan",
        ),
    )

    history: Mapped[list[History]] = cast(
        Mapped[list["History"]],
        db.relationship(
            "History",
            back_populates="shoppinglist",
            cascade="all, delete-orphan",
        ),
    )

    @classmethod
    def getDefault(cls, household_id: int) -> Self:
        return cast(
            Self,
            cls.query.filter(cls.household_id == household_id).order_by(cls.id).first(),
        )

    def isDefault(self) -> bool:
        return self.id == self.getDefault(self.household_id).id


class ShoppinglistItems(Model):
    __tablename__ = "shoppinglist_items"

    shoppinglist_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("shoppinglist.id"), primary_key=True
    )
    item_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("item.id"), primary_key=True
    )
    description: Mapped[str] = db.Column(db.String)
    created_by: Mapped[int | None] = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )

    item: Mapped[Item] = cast(
        Mapped["Item"],
        db.relationship(
            "Item",
            back_populates="shoppinglists",
        ),
    )
    shoppinglist: Mapped[Shoppinglist] = cast(
        Mapped["Shoppinglist"],
        db.relationship(
            "Shoppinglist",
            back_populates="items",
        ),
    )
    created_by_user: Mapped[User] = cast(
        Mapped["User"],
        db.relationship(
            "User",
            foreign_keys=[created_by],
            uselist=False,
        ),
    )

    def obj_to_item_dict(self) -> dict[str, Any]:
        res = self.item.obj_to_dict()
        res["description"] = self.description
        res["created_at"] = self.created_at
        res["updated_at"] = self.updated_at
        res["created_by"] = self.created_by
        return res

    @classmethod
    def find_by_ids(cls, shoppinglist_id: int, item_id: int) -> Self | None:
        return cls.query.filter(
            cls.shoppinglist_id == shoppinglist_id, cls.item_id == item_id
        ).first()

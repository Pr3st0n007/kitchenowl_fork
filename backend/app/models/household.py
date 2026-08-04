from typing import TYPE_CHECKING, Any, Self, cast

from sqlalchemy.orm import Mapped

from app import db
from app.helpers.db_list_type import DbListType

Model = db.Model
if TYPE_CHECKING:
    from app.helpers.db_model_base import DbModelBase
    from app.models import (
        Category,
        Expense,
        ExpenseCategory,
        File,
        Item,
        Recipe,
        Shoppinglist,
        Tag,
        User,
    )

    Model = DbModelBase


class Household(Model):
    __tablename__ = "household"

    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    name: Mapped[str] = db.Column(db.String(128), nullable=False)
    photo: Mapped[str | None] = db.Column(db.String(), db.ForeignKey("file.filename"))
    language: Mapped[str] = db.Column(db.String())
    planner_feature: Mapped[bool] = db.Column(
        db.Boolean(), nullable=False, default=True
    )
    expenses_feature: Mapped[bool] = db.Column(
        db.Boolean(), nullable=False, default=True
    )
    agent_feature: Mapped[bool] = db.Column(db.Boolean(), nullable=False, default=False)
    description: Mapped[str | None] = db.Column(db.String())
    link: Mapped[str | None] = db.Column(db.String(255))
    # For households that have verified their authenticity
    verified: Mapped[bool | None] = db.Column(db.Boolean, default=False)

    view_ordering: Mapped[list[str]] = db.Column(DbListType(), default=list())

    items: Mapped[list[Item]] = cast(
        Mapped[list["Item"]],
        db.relationship(
            "Item",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    shoppinglists: Mapped[list[Shoppinglist]] = cast(
        Mapped[list["Shoppinglist"]],
        db.relationship(
            "Shoppinglist",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    categories: Mapped[list[Category]] = cast(
        Mapped[list["Category"]],
        db.relationship(
            "Category",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    recipes: Mapped[list[Recipe]] = cast(
        Mapped[list["Recipe"]],
        db.relationship(
            "Recipe",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    tags: Mapped[list[Tag]] = cast(
        Mapped[list["Tag"]],
        db.relationship(
            "Tag",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    expenses: Mapped[list[Expense]] = cast(
        Mapped[list["Expense"]],
        db.relationship(
            "Expense",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    expenseCategories: Mapped[list[ExpenseCategory]] = cast(
        Mapped[list["ExpenseCategory"]],
        db.relationship(
            "ExpenseCategory",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    member: Mapped[list["HouseholdMember"]] = cast(
        Mapped[list["HouseholdMember"]],
        db.relationship(
            "HouseholdMember",
            back_populates="household",
            cascade="all, delete-orphan",
        ),
    )
    photo_file: Mapped[File] = cast(
        Mapped["File"],
        db.relationship(
            "File",
            back_populates="household",
            uselist=False,
        ),
    )

    def obj_to_dict(
        self,
        skip_columns: list[str] | None = None,
        include_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        res = super().obj_to_dict(skip_columns, include_columns)
        res["member"] = [m.obj_to_user_dict() for m in self.member]
        res["default_shopping_list"] = self.shoppinglists[0].obj_to_dict()
        if self.photo_file:
            res["photo_hash"] = self.photo_file.blur_hash
        return res

    def obj_to_public_dict(self) -> dict[str, Any]:
        res = super().obj_to_dict(
            include_columns=[
                "id",
                "name",
                "photo",
                "language",
                "description",
                "link",
                "verified",
            ]
        )
        if self.photo_file:
            res["photo_hash"] = self.photo_file.blur_hash
        return res

    def obj_to_export_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "language": self.language,
            "view_ordering": self.view_ordering,
            "planner_feature": self.planner_feature,
            "expenses_feature": self.expenses_feature,
            "agent_feature": self.agent_feature,
            "member": [m.user.username for m in self.member],
            "shoppinglists": [s.name for s in self.shoppinglists],
            "recipes": [s.obj_to_export_dict() for s in self.recipes],
            "items": [s.obj_to_export_dict() for s in self.items],
            "expenses": [s.obj_to_export_dict() for s in self.expenses],
        }


class HouseholdMember(Model):
    __tablename__ = "household_member"

    household_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("household.id"), primary_key=True
    )
    user_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True
    )

    owner: Mapped[bool] = db.Column(db.Boolean(), default=False, nullable=False)
    admin: Mapped[bool] = db.Column(db.Boolean(), default=True, nullable=False)

    expense_balance: Mapped[float] = db.Column(db.Float(), default=0, nullable=False)

    # Per-member default agent persona used when the user creates a new chat
    # without picking one explicitly. NULL falls back to the household's
    # global default persona.
    default_persona_id: Mapped[int | None] = db.Column(
        db.Integer,
        db.ForeignKey("agent_persona.id", ondelete="SET NULL"),
        nullable=True,
    )

    household: Mapped[Household] = cast(
        Mapped["Household"],
        db.relationship(
            "Household",
            back_populates="member",
        ),
    )
    user: Mapped[User] = cast(
        Mapped["User"],
        db.relationship(
            "User",
            back_populates="households",
        ),
    )

    def obj_to_user_dict(self) -> dict[str, Any]:
        res = self.user.obj_to_dict()
        res["owner"] = self.owner
        res["admin"] = self.admin
        res["expense_balance"] = self.expense_balance
        return res

    def delete(self):
        if self.owner:
            newOwner = next(
                (m for m in self.household.member if m.admin and m != self),
                next((m for m in self.household.member if m != self), None),
            )
            if newOwner:
                newOwner.admin = True
                newOwner.owner = True
                newOwner.save()
            super().delete()
        else:
            super().delete()

    @classmethod
    def find_by_ids(cls, household_id: int, user_id: int) -> Self | None:
        return cls.query.filter(
            cls.household_id == household_id, cls.user_id == user_id
        ).first()

    @classmethod
    def find_by_household(cls, household_id: int) -> list[Self]:
        return cls.query.filter(cls.household_id == household_id).all()

    @classmethod
    def find_by_user(cls, user_id: int) -> list[Self]:
        return cls.query.filter(cls.user_id == user_id).all()

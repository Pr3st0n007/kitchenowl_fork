import time

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.config import app
from app.helpers import authorize_household, validate_args
from app.models import Household
from app.service.importServices import (
    importExpense,
    importItem,
    importRecipe,
    importShoppinglist,
)
from app.service.recalculate_balances import recalculateBalances

from .schemas import ImportSchema

importBP = Blueprint("import", __name__)


@importBP.route("", methods=["POST"])
@jwt_required()
@authorize_household()
@validate_args(ImportSchema)
def importData(args, household_id):
    household = Household.find_by_id(household_id)
    if not household:
        return

    app.logger.info("Starting import...")

    t0 = time.time()
    if "items" in args:
        for item in args["items"]:
            importItem(household, item)

    if "recipes" in args:
        for recipe in args["recipes"]:
            importRecipe(
                household_id,
                recipe,
                args["recipe_overwrite"] if "recipe_overwrite" in args else False,
            )

    if "expenses" in args:
        for expense in args["expenses"]:
            importExpense(household, expense)
        recalculateBalances(household.id)

    if "shoppinglists" in args:
        for shoppinglist in args["shoppinglists"]:
            importShoppinglist(household, shoppinglist)

    app.logger.info(f"Import took: {(time.time() - t0):.3f}s")
    return jsonify({"msg": "DONE"})

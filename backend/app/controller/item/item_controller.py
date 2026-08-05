import os
import uuid
import base64

import blurhash
import requests
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from PIL import Image
from werkzeug.utils import secure_filename

from app.config import UPLOAD_FOLDER
from app.errors import InvalidUsage, NotFoundRequest
from app.helpers import authorize_household, validate_args
from app.models import Category, Item, Recipe, RecipeItems
from app.models.file import File
from app.models.llm_config import LLMConfig
from app.service.llm.provider import LLMError, get_provider
from app.util import description_splitter

from .schemas import AddItem, SearchByNameRequest, UpdateItem

item = Blueprint("item", __name__)
itemHousehold = Blueprint("item", __name__)


def _render_icon_prompt(template: str, subject: str) -> str:
    prompt = template.replace("{name}", subject)
    prompt = prompt.replace("[SUBJECT]", subject)
    return prompt


def _image_bytes_from_provider_response(image_ref: str) -> bytes:
    if image_ref.startswith("data:image/"):
        _, _, payload = image_ref.partition(",")
        if not payload:
            raise InvalidUsage("Generated image data URL was empty")
        try:
            return base64.b64decode(payload, validate=True)
        except Exception as exc:  # pragma: no cover - defensive
            raise InvalidUsage(f"Generated image data URL was invalid: {exc}") from exc

    try:
        response = requests.get(image_ref, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as exc:
        raise InvalidUsage(f"Failed to download generated image: {exc}")


@itemHousehold.route("", methods=["GET"])
@jwt_required()
@authorize_household()
def getAllItems(household_id):
    return jsonify(
        [e.obj_to_dict() for e in Item.all_from_household_by_name(household_id)]
    )


@item.route("/<int:id>", methods=["GET"])
@jwt_required()
def getItem(id):
    item = Item.find_by_id(id)
    if not item:
        raise NotFoundRequest()
    item.checkAuthorized()
    return jsonify(item.obj_to_dict())


@item.route("/<int:id>/recipes", methods=["GET"])
@jwt_required()
def getItemRecipes(id):
    item = Item.find_by_id(id)
    if not item:
        raise NotFoundRequest()
    item.checkAuthorized()
    recipe = (
        RecipeItems.query.filter(RecipeItems.item_id == id)
        .join(RecipeItems.recipe)
        .order_by(Recipe.name)
        .all()
    )
    return jsonify([e.obj_to_recipe_dict() for e in recipe])


@item.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def deleteItemById(id):
    item = Item.find_by_id(id)
    if not item:
        raise NotFoundRequest()
    item.checkAuthorized()
    item.delete()
    return jsonify({"msg": "DONE"})


@itemHousehold.route("/<int:id>/generate-icon", methods=["POST"])
@jwt_required()
@authorize_household()
def generateItemIcon(household_id, id):
    item = Item.find_by_id(id)
    if not item or item.household_id != household_id:
        raise NotFoundRequest()

    cfg = LLMConfig.find_by_household(household_id)
    if not cfg or not cfg.has_api_key():
        raise InvalidUsage("LLM Provider is not configured")

    try:
        provider = get_provider(cfg)
    except LLMError as exc:
        raise InvalidUsage(str(exc))
    prompt = (
        cfg.icon_generation_prompt
        or "An icon for the ingredient {name}, minimalist, flat vector style, solid colors."
    )
    prompt = _render_icon_prompt(prompt, item.name)

    try:
        image_url = provider.generate_image(prompt)
    except LLMError as exc:
        raise InvalidUsage(str(exc))

    image_bytes = _image_bytes_from_provider_response(image_url)

    filename = secure_filename(str(uuid.uuid4()) + ".png")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    blur = None
    try:
        with Image.open(filepath) as image:
            image.thumbnail((100, 100))
            blur = blurhash.encode(image, x_components=4, y_components=3)
    except Exception:
        pass

    from flask_jwt_extended import current_user

    f = File(filename=filename, blur_hash=blur, created_by=current_user.id).save()

    item.icon = filename
    item.save()

    return jsonify(item.obj_to_dict())


@itemHousehold.route("/search", methods=["GET"])
@jwt_required()
@authorize_household()
@validate_args(SearchByNameRequest)
def searchItemByName(args, household_id):
    query, description = description_splitter.split(args["query"])
    return jsonify(
        [
            e.obj_to_dict() | {"description": description}
            for e in Item.search_name(query, household_id)
        ]
    )


@itemHousehold.route("", methods=["POST"])
@jwt_required()
@authorize_household()
@validate_args(AddItem)
def addItem(args, household_id):
    name: str = args["name"].strip()[:128]
    if Item.find_by_name(household_id, name):
        raise InvalidUsage()

    item = Item(household_id=household_id, name=name)
    if "category" in args:
        if not args["category"]:
            item.category = None
        elif "id" in args["category"]:
            item.category = Category.find_by_id(args["category"]["id"])
        else:
            raise InvalidUsage()
    if "icon" in args:
        item.icon = args["icon"]
    item.save()

    return jsonify(item.obj_to_dict())


@item.route("/<int:id>", methods=["POST"])
@jwt_required()
@validate_args(UpdateItem)
def updateItem(args, id):
    item = Item.find_by_id(id)
    if not item:
        raise NotFoundRequest()
    item.checkAuthorized()

    if "category" in args:
        if not args["category"]:
            item.category = None
        elif "id" in args["category"]:
            item.category = Category.find_by_id(args["category"]["id"])
        else:
            raise InvalidUsage()
    if "icon" in args:
        item.icon = args["icon"]
    if "name" in args and args["name"] != item.name:
        newName: str = args["name"].strip()[:128]
        if not Item.find_by_name(item.household_id, newName):
            item.name = newName
    item.save()

    if "merge_item_id" in args and args["merge_item_id"] != id:
        mergeItem = Item.find_by_id(args["merge_item_id"])
        if mergeItem:
            item.merge(mergeItem)

    return jsonify(item.obj_to_dict())

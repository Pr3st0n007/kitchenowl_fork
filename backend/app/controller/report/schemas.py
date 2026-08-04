from marshmallow import EXCLUDE, Schema, fields


class AddReport(Schema):
    class Meta:
        unknown = EXCLUDE

    description = fields.String(
        validate=lambda a: not a or not a.isspace(),
        allow_none=True,
    )
    recipe_id = fields.Integer(
        allow_none=True,
    )
    user_id = fields.Integer(
        allow_none=True,
    )

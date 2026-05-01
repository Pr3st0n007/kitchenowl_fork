from marshmallow import EXCLUDE, Schema, fields, validate

from app.models.llm_config import LLMProviderType


PROVIDER_VALUES = [p.value for p in LLMProviderType]


class UpdateLLMConfig(Schema):
    class Meta:
        unknown = EXCLUDE

    provider = fields.String(validate=validate.OneOf(PROVIDER_VALUES))
    base_url = fields.String(allow_none=True, validate=validate.Length(max=512))
    model = fields.String(allow_none=True, validate=validate.Length(max=128))
    # ``api_key`` is write-only. Pass an empty string to clear the stored key.
    api_key = fields.String(allow_none=True)
    system_prompt = fields.String(allow_none=True)
    initial_greeting = fields.String(allow_none=True)
    enabled = fields.Boolean()
    max_tokens = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    temperature = fields.Float(allow_none=True, validate=validate.Range(min=0, max=2))


class CreateAgentChat(Schema):
    class Meta:
        unknown = EXCLUDE

    title = fields.String(load_default=None, allow_none=True)
    persona_id = fields.Integer(load_default=None, allow_none=True)


class UpdateAgentChat(Schema):
    class Meta:
        unknown = EXCLUDE

    # Pass an empty/whitespace string (or ``null``) to clear the manual title
    # and re-enable auto-rename.
    title = fields.String(allow_none=True, validate=validate.Length(max=255))


class PostAgentMessage(Schema):
    class Meta:
        unknown = EXCLUDE

    content = fields.String(
        required=True,
        validate=validate.Length(min=1, max=4000),
    )
    # Optional context attachments the user picked from the composer chip
    # row. The agent surfaces these as additional context to the LLM.
    attached_recipe_ids = fields.List(fields.Integer(), load_default=list)
    attached_item_ids = fields.List(fields.Integer(), load_default=list)


_REWIND_ACTIONS = ("rewind", "edit")


class RewindAgentMessage(Schema):
    """PATCH /chats/<id>/messages/<id> -- rewind to or edit a message.

    Two-stage flow: clients first call without ``confirm`` to get the undo
    preview, then again with ``confirm=true`` and any message-ids the user
    chose to skip in ``skip_undo_message_ids`` to actually apply.
    """

    class Meta:
        unknown = EXCLUDE

    action = fields.String(required=True, validate=validate.OneOf(_REWIND_ACTIONS))
    new_content = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(min=1, max=4000),
    )
    confirm = fields.Boolean(load_default=False)
    # Tool-message IDs the user opted to skip on the confirm call. Other
    # reversible ops in those messages will not be undone.
    skip_undo_message_ids = fields.List(fields.Integer(), load_default=list)


class RegenerateAgentMessage(Schema):
    """POST /chats/<id>/messages/<id>/regenerate -- replay last user turn."""

    class Meta:
        unknown = EXCLUDE

    confirm = fields.Boolean(load_default=False)
    skip_undo_message_ids = fields.List(fields.Integer(), load_default=list)


_PERSONA_SCOPES = ("global", "private")


class CreateAgentPersona(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate.Length(min=1, max=128))
    icon = fields.String(allow_none=True, validate=validate.Length(max=64))
    system_prompt = fields.String(allow_none=True)
    initial_greeting = fields.String(allow_none=True)
    temperature = fields.Float(allow_none=True, validate=validate.Range(min=0, max=2))
    scope = fields.String(
        load_default="private", validate=validate.OneOf(_PERSONA_SCOPES)
    )


class UpdateAgentPersona(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate.Length(min=1, max=128))
    icon = fields.String(allow_none=True, validate=validate.Length(max=64))
    system_prompt = fields.String(allow_none=True)
    initial_greeting = fields.String(allow_none=True)
    temperature = fields.Float(allow_none=True, validate=validate.Range(min=0, max=2))
    is_default_global = fields.Boolean()


class SetDefaultPersona(Schema):
    class Meta:
        unknown = EXCLUDE

    persona_id = fields.Integer(allow_none=True, load_default=None)


class AttachRecipeCard(Schema):
    """POST /chats/<id>/cards -- attach an existing recipe to the chat."""

    class Meta:
        unknown = EXCLUDE

    recipe_id = fields.Integer(required=True)
    group_label = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=64),
    )


class UpdateRecipeCard(Schema):
    """PATCH /chats/<id>/cards/<card_id> -- update group/position."""

    class Meta:
        unknown = EXCLUDE

    group_label = fields.String(
        allow_none=True,
        validate=validate.Length(max=64),
    )
    position = fields.Integer(allow_none=True, validate=validate.Range(min=0))

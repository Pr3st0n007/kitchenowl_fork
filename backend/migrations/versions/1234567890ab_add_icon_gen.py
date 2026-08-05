"""Add icon generation fields to llm_config

Revision ID: 1234567890ab
Revises: c8d2f3a14c01
Create Date: 2026-08-04 17:08:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "1234567890ab"
down_revision = "c8d2f3a14c01"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("llm_config") as batch_op:
        batch_op.add_column(sa.Column("icon_generation_model", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("icon_generation_prompt", sa.Text(), nullable=True))

def downgrade():
    with op.batch_alter_table("llm_config") as batch_op:
        batch_op.drop_column("icon_generation_prompt")
        batch_op.drop_column("icon_generation_model")

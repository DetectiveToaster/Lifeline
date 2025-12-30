"""init tables

Revision ID: 001_init
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bans",
        sa.Column("token_hash", sa.String(length=128), primary_key=True),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strikes",
        sa.Column("token_hash", sa.String(length=128), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "self_harm",
        sa.Column("token_hash", sa.String(length=128), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.String(length=512), nullable=True),
    )


def downgrade():
    op.drop_table("incidents")
    op.drop_table("self_harm")
    op.drop_table("strikes")
    op.drop_table("bans")

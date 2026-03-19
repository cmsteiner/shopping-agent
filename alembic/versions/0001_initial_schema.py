"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-19

Creates all tables for the shopping-agent MVP:
  users, shopping_lists, items, brand_preferences, messages, pending_confirmations
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )

    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SENT", "ARCHIVED", name="liststatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("brand_pref", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PENDING", name="itemstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "brand_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=200), nullable=False),
        sa.Column("set_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["set_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("INBOUND", "OUTBOUND", name="messagedirection"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("twilio_sid", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("twilio_sid"),
    )

    op.create_table(
        "pending_confirmations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("existing_item_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["existing_item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pending_confirmations")
    op.drop_table("messages")
    op.drop_table("brand_preferences")
    op.drop_table("items")
    op.drop_table("shopping_lists")
    op.drop_table("users")

"""Web schema foundation

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22

Adds categories, shopping trips, event log, and web-facing item/list metadata.
Backfills canonical categories and maps existing item.category strings to category_id.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CANONICAL_CATEGORIES: list[str] = [
    "PRODUCE",
    "DAIRY",
    "MEAT",
    "SEAFOOD",
    "BAKERY",
    "FROZEN",
    "PANTRY",
    "BEVERAGES",
    "SNACKS",
    "CLEANING",
    "PERSONAL CARE",
    "HOUSEHOLD",
    "OTHER",
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index("ix_categories_sort_order", "categories", ["sort_order"], unique=False)

    op.create_table(
        "shopping_trips",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", name="tripstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_trips_list_id", "shopping_trips", ["list_id"], unique=False)
    op.create_index("ix_shopping_trips_status", "shopping_trips", ["status"], unique=False)

    op.create_table(
        "list_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_list_events_created_at", "list_events", ["created_at"], unique=False)
    op.create_index("ix_list_events_list_id_id", "list_events", ["list_id", "id"], unique=False)

    with op.batch_alter_table("shopping_lists") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("is_purchased", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("new_during_trip", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_index("ix_items_category_id", ["category_id"], unique=False)
        batch_op.create_index("ix_items_list_id_status", ["list_id", "status"], unique=False)
        batch_op.create_index("ix_items_list_id_is_purchased", ["list_id", "is_purchased"], unique=False)
        batch_op.create_index("ix_items_updated_at", ["updated_at"], unique=False)
        batch_op.create_foreign_key("fk_items_category_id_categories", "categories", ["category_id"], ["id"])

    _backfill_categories_and_items()
    _backfill_list_versions()
    _drop_server_defaults()


def downgrade() -> None:
    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_constraint("fk_items_category_id_categories", type_="foreignkey")
        batch_op.drop_index("ix_items_updated_at")
        batch_op.drop_index("ix_items_list_id_is_purchased")
        batch_op.drop_index("ix_items_list_id_status")
        batch_op.drop_index("ix_items_category_id")
        batch_op.drop_column("version")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("new_during_trip")
        batch_op.drop_column("purchased_at")
        batch_op.drop_column("is_purchased")
        batch_op.drop_column("notes")
        batch_op.drop_column("category_id")

    with op.batch_alter_table("shopping_lists") as batch_op:
        batch_op.drop_column("version")

    op.drop_index("ix_list_events_list_id_id", table_name="list_events")
    op.drop_index("ix_list_events_created_at", table_name="list_events")
    op.drop_table("list_events")

    op.drop_index("ix_shopping_trips_status", table_name="shopping_trips")
    op.drop_index("ix_shopping_trips_list_id", table_name="shopping_trips")
    op.drop_table("shopping_trips")

    op.drop_index("ix_categories_sort_order", table_name="categories")
    op.drop_table("categories")


def _backfill_categories_and_items() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    category_table = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("version", sa.Integer()),
    )

    op.bulk_insert(
        category_table,
        [
            {
                "name": name,
                "normalized_name": name.lower(),
                "sort_order": (index + 1) * 10,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
            for index, name in enumerate(CANONICAL_CATEGORIES)
        ],
    )

    existing_categories = conn.execute(
        sa.text(
            """
            SELECT DISTINCT TRIM(category) AS category
            FROM items
            WHERE category IS NOT NULL AND TRIM(category) != ''
            """
        )
    ).fetchall()

    sort_order = (len(CANONICAL_CATEGORIES) + 1) * 10
    for row in existing_categories:
        category = row.category
        normalized = category.lower()
        exists = conn.execute(
            sa.text("SELECT 1 FROM categories WHERE normalized_name = :normalized"),
            {"normalized": normalized},
        ).scalar()
        if exists:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO categories (name, normalized_name, sort_order, created_at, updated_at, version)
                VALUES (:name, :normalized_name, :sort_order, :created_at, :updated_at, :version)
                """
            ),
            {
                "name": category,
                "normalized_name": normalized,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            },
        )
        sort_order += 10

    conn.execute(
        sa.text(
            """
            UPDATE items
            SET
                category_id = (
                    SELECT categories.id
                    FROM categories
                    WHERE categories.normalized_name = lower(trim(items.category))
                ),
                updated_at = created_at,
                version = 1
            """
        )
    )


def _backfill_list_versions() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE shopping_lists SET version = 1"))


def _drop_server_defaults() -> None:
    with op.batch_alter_table("shopping_lists") as batch_op:
        batch_op.alter_column("version", server_default=None)

    with op.batch_alter_table("items") as batch_op:
        batch_op.alter_column("is_purchased", server_default=None)
        batch_op.alter_column("new_during_trip", server_default=None)
        batch_op.alter_column("updated_at", server_default=None)
        batch_op.alter_column("version", server_default=None)

    with op.batch_alter_table("categories") as batch_op:
        batch_op.alter_column("version", server_default=None)

    with op.batch_alter_table("shopping_trips") as batch_op:
        batch_op.alter_column("status", server_default=None)
        batch_op.alter_column("version", server_default=None)

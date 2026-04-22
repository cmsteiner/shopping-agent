"""Smoke tests for Alembic migrations."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings


def _make_alembic_config(db_path: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def test_upgrade_head_on_empty_database(tmp_path):
    db_path = tmp_path / "empty.db"
    config = _make_alembic_config(db_path)
    original_database_url = settings.database_url
    settings.database_url = f"sqlite:///{db_path.as_posix()}"

    try:
        command.upgrade(config, "head")
    finally:
        settings.database_url = original_database_url

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    inspector = inspect(engine)

    assert "categories" in inspector.get_table_names()
    assert "shopping_trips" in inspector.get_table_names()
    assert "list_events" in inspector.get_table_names()

    item_columns = {column["name"] for column in inspector.get_columns("items")}
    assert {"category_id", "notes", "is_purchased", "purchased_at", "new_during_trip", "updated_at", "version"} <= item_columns

    list_columns = {column["name"] for column in inspector.get_columns("shopping_lists")}
    assert "version" in list_columns


def test_upgrade_from_0001_backfills_categories_and_item_category_ids(tmp_path):
    db_path = tmp_path / "backfill.db"
    config = _make_alembic_config(db_path)
    original_database_url = settings.database_url
    settings.database_url = f"sqlite:///{db_path.as_posix()}"

    try:
        command.upgrade(config, "0001")

        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO shopping_lists (status, sent_at, archived_at, created_at)
                    VALUES ('ACTIVE', NULL, NULL, CURRENT_TIMESTAMP)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO items (list_id, name, quantity, unit, brand_pref, category, status, added_by, created_at)
                    VALUES (1, 'Milk', 1, NULL, NULL, 'DAIRY', 'ACTIVE', NULL, CURRENT_TIMESTAMP)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO items (list_id, name, quantity, unit, brand_pref, category, status, added_by, created_at)
                    VALUES (1, 'Soap', 1, NULL, NULL, 'Custom Stuff', 'ACTIVE', NULL, CURRENT_TIMESTAMP)
                    """
                )
            )

        command.upgrade(config, "head")
    finally:
        settings.database_url = original_database_url

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT items.name, items.category, items.category_id, categories.name AS category_name,
                       items.updated_at, items.version
                FROM items
                LEFT JOIN categories ON categories.id = items.category_id
                ORDER BY items.id
                """
            )
        ).mappings().all()

        dairy = next(row for row in rows if row["name"] == "Milk")
        custom = next(row for row in rows if row["name"] == "Soap")

        assert dairy["category"] == "DAIRY"
        assert dairy["category_id"] is not None
        assert dairy["category_name"] == "DAIRY"
        assert dairy["updated_at"] is not None
        assert dairy["version"] == 1

        assert custom["category"] == "Custom Stuff"
        assert custom["category_id"] is not None
        assert custom["category_name"] == "Custom Stuff"


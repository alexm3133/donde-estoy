"""The Alembic migrations must produce exactly the schema the models expect."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401
from app.db import Base


def test_migrations_match_models(tmp_path):
    database = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite+aiosqlite:///{database}"
    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database}"))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"]: c for c in inspector.get_columns(table.name)}
        assert set(migrated) == {c.name for c in table.columns}, table.name
        for column in table.columns:
            assert migrated[column.name]["nullable"] == column.nullable, (
                f"{table.name}.{column.name}"
            )
        migrated_indexes = {
            (i["name"], bool(i["unique"])) for i in inspector.get_indexes(table.name)
        }
        model_indexes = {(i.name, bool(i.unique)) for i in table.indexes}
        assert migrated_indexes == model_indexes, table.name

    command.downgrade(config, "base")
    assert set(inspect(create_engine(f"sqlite:///{database}")).get_table_names()) == {
        "alembic_version"
    }

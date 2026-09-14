"""Alembic-Umgebung. Aufgerufen über ``python -m backend.migrate`` oder die Alembic-CLI."""
import os
import sys

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend import database, models  # noqa: E402

config = context.config
target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    """SQL nur ausgeben (``alembic upgrade head --sql``), ohne Verbindung."""
    context.configure(
        url=database.SQLALCHEMY_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = config.attributes.get("engine") or database.engine
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite kann Spalten nur über Tabellen-Neuaufbau ändern.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

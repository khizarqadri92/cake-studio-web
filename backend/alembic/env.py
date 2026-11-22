from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  (register all models)
from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().db_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode not supported")
run_migrations_online()

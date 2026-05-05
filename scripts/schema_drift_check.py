import argparse
import os
import sys
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "services" / "api"
sys.path.insert(0, str(API_DIR))

from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: F401,E402


IGNORED_TABLES = {"alembic_version"}


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def check_schema(database_url: str) -> list[str]:
    engine = create_engine(database_url)
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    model_tables = set(Base.metadata.tables.keys())
    problems: list[str] = []

    missing_tables = sorted(model_tables - db_tables - IGNORED_TABLES)
    extra_tables = sorted(db_tables - model_tables - IGNORED_TABLES)
    for table in missing_tables:
        problems.append(f"Missing table in DB: {table}")
    for table in extra_tables:
        problems.append(f"Extra table in DB not mapped by models: {table}")

    for table_name, table in Base.metadata.tables.items():
        if table_name not in db_tables:
            continue
        db_columns = {column["name"] for column in inspector.get_columns(table_name)}
        model_columns = {column.name for column in table.columns}
        for column in sorted(model_columns - db_columns):
            problems.append(f"Missing column in DB: {table_name}.{column}")
        for column in sorted(db_columns - model_columns):
            problems.append(f"Extra column in DB not mapped by models: {table_name}.{column}")
    engine.dispose()
    return problems


def run_fresh_check(database_url: str) -> list[str]:
    url = make_url(database_url)
    if url.get_backend_name() not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        return ["Fresh migration check requires PostgreSQL DATABASE_URL."]
    db_name = f"forge_schema_check_{uuid.uuid4().hex[:12]}"
    admin_url = url.set(database="postgres")
    temp_url = url.set(database=db_name)
    temp_database_url = temp_url.render_as_string(hide_password=False)
    admin_engine = create_engine(admin_url)
    with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    try:
        previous_database_url = settings.database_url
        settings.database_url = temp_database_url
        os.environ["DATABASE_URL"] = temp_database_url
        command.upgrade(alembic_config(temp_database_url), "head")
        settings.database_url = previous_database_url
        return check_schema(temp_database_url)
    finally:
        settings.database_url = database_url
        os.environ["DATABASE_URL"] = database_url
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'''
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
            '''))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SQLAlchemy models against migrated database schema.")
    parser.add_argument("--fresh", action="store_true", help="Create a temporary PostgreSQL database, migrate it to head, then compare schema.")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL") or settings.database_url
    problems = run_fresh_check(database_url) if args.fresh else check_schema(database_url)
    if problems:
        print("Schema drift detected:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Schema drift check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Base


EXPECTED_TABLES = {table.name: table for table in Base.metadata.sorted_tables}


def _run_alembic(*args: str) -> int:
    return subprocess.call(["alembic", *args])


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "alembic_version" in table_names or not table_names:
        return _run_alembic("upgrade", "head")

    missing_tables = [name for name in EXPECTED_TABLES if name not in table_names]
    if missing_tables:
        print(
            "Existing database is missing managed tables and cannot be auto-stamped: "
            + ", ".join(sorted(missing_tables)),
            file=sys.stderr,
        )
        return 1

    missing_columns: list[str] = []
    for table_name, table in EXPECTED_TABLES.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        expected_columns = {column.name for column in table.columns}
        missing = sorted(expected_columns - actual_columns)
        if missing:
            missing_columns.append(f"{table_name}: {', '.join(missing)}")

    if missing_columns:
        print(
            "Existing database schema is not aligned with current models and cannot be auto-stamped:\n"
            + "\n".join(missing_columns),
            file=sys.stderr,
        )
        return 1

    print("Existing aligned schema detected without alembic history; stamping head.")
    return _run_alembic("stamp", "head")


if __name__ == "__main__":
    raise SystemExit(main())

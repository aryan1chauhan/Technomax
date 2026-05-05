import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Base


EXPECTED_TABLES = {table.name: table for table in Base.metadata.sorted_tables}


def _run_alembic(*args: str) -> int:
    return subprocess.call(["alembic", *args])


def _connect_with_retry(database_url: str, max_wait_seconds: float = 30.0):
    start = time.monotonic()
    attempt = 0
    delay = 1.0
    last_error: Exception | None = None

    while True:
        attempt += 1
        engine = None
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return engine
        except Exception as exc:
            last_error = exc
            if engine is not None:
                engine.dispose()

            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                break

            sleep_for = min(delay, max_wait_seconds - elapsed)
            print(
                f"Database connection failed (attempt {attempt}): {exc}. "
                f"Retrying in {sleep_for:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(sleep_for)
            delay = min(delay * 2.0, 8.0)

    raise RuntimeError(
        f"Database connection failed after {max_wait_seconds:.0f}s"
    ) from last_error


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    engine = _connect_with_retry(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    # ── Case 1: fresh DB or already alembic-tracked ──────────────────────────
    # Let alembic run all pending migrations from scratch (or from current rev).
    if "alembic_version" in table_names or not table_names:
        return _run_alembic("upgrade", "head")

    # ── Case 2: DB has some managed tables but NO alembic tracking ────────────
    missing_tables = [name for name in EXPECTED_TABLES if name not in table_names]
    if missing_tables:
        # This happens when a previous stack run died before alembic could
        # stamp its version table (e.g. stale Docker volume from an old build).
        # Recovery: create only the missing tables via SQLAlchemy, then stamp.
        print(
            "WARNING: Untracked DB is missing managed tables: "
            + ", ".join(sorted(missing_tables))
            + ". Attempting self-heal via SQLAlchemy create_all...",
            file=sys.stderr,
        )
        try:
            # create_all with an explicit table list only touches those tables.
            Base.metadata.create_all(
                engine,
                tables=[EXPECTED_TABLES[t] for t in missing_tables],
            )
            print(
                "Self-heal OK — created: "
                + ", ".join(sorted(missing_tables))
                + ". Stamping alembic at head.",
                file=sys.stderr,
            )
            return _run_alembic("stamp", "head")
        except Exception as exc:
            print(
                f"Self-heal failed: {exc}\n"
                "Manual recovery: docker compose down -v && docker compose up --build",
                file=sys.stderr,
            )
            return 1

    # ── Case 3: all tables present, no alembic tracking, check columns ────────
    missing_columns: list[str] = []
    for table_name, table in EXPECTED_TABLES.items():
        actual_columns = {col["name"] for col in inspector.get_columns(table_name)}
        expected_columns = {col.name for col in table.columns}
        missing = sorted(expected_columns - actual_columns)
        if missing:
            missing_columns.append(f"{table_name}: {', '.join(missing)}")

    if missing_columns:
        print(
            "Existing database schema is not aligned with current models "
            "and cannot be auto-stamped:\n" + "\n".join(missing_columns),
            file=sys.stderr,
        )
        return 1

    print("Existing aligned schema detected without alembic history; stamping head.")
    return _run_alembic("stamp", "head")


if __name__ == "__main__":
    raise SystemExit(main())

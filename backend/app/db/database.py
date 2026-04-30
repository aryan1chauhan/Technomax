from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DATABASE_URL = settings.database_url

# pool_size=40 per worker × 8 workers = 320 baseline connections
# max_overflow=40 burst per worker = 640 absolute ceiling (< PG high-cap max_connections=700)
engine = create_engine(
    DATABASE_URL,
    pool_size=15,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

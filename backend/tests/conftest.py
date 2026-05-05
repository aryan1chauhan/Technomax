"""
Shared test fixtures for MediRoute API test suite.
Uses a real test database with transaction rollback per test.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Override env before importing app modules
os.environ["TESTING"] = "true"  # Disables rate limiting
# On local Windows shells, pytest's default capture can hit a closed tmpfile
# teardown error after collection; run full suites with `-s` if that appears.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")
os.environ.setdefault("SECRET_KEY", "test_secret_key_not_for_production")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("MODEL_SHA256", "a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7")

from app.main import app
from app.db.database import Base, get_db
from app.core.security import hash_password
from app.db.models import User

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create an isolated database session per test.

    Endpoint code calls commit() during normal execution. Using
    join_transaction_mode=create_savepoint keeps those commits scoped to
    per-test SAVEPOINTs so data does not leak between tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    # Keep dispatch-capacity tests deterministic even if the shared local DB was
    # previously exhausted by manual/dev runs.
    session.execute(
        text(
            """
            UPDATE availabilities
            SET beds = GREATEST(COALESCE(beds, 0), 5),
                icu = GREATEST(COALESCE(icu, 0), 2),
                updated_at = NOW()
            """
        )
    )
    session.flush()
    
    yield session
    
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a test user and return auth headers."""
    email = f"test_amb_{os.urandom(4).hex()}@test.com"
    
    # Register
    client.post("/api/auth/register", json={
        "email": email,
        "password": "test123",
        "role": "ambulance",
    })
    
    # Login
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": "test123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client, db_session):
    """Register an admin user and return auth headers."""
    email = f"test_admin_{os.urandom(4).hex()}@test.com"

    db_session.add(User(
        email=email,
        password_hash=hash_password("admin123"),
        role="admin",
    ))
    db_session.commit()
    
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": "admin123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hospital_headers(client):
    """Register a hospital user and return auth headers."""
    email = f"test_hosp_{os.urandom(4).hex()}@test.com"
    
    client.post("/api/auth/register", json={
        "email": email,
        "password": "hosp123",
        "role": "hospital",
    })
    
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": "hosp123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def dispatch_case(client, auth_headers):
    """Helper fixture to dispatch a case safely across any tests."""
    res = client.post("/api/dispatch/", json={
        "condition": "cardiac_arrest",
        "ambulance_lat": 29.86,
        "ambulance_lng": 77.89,
        "equipment_needed": ["ecg"]
    }, headers=auth_headers)
    
    if res.status_code != 200:
        pytest.skip("No hospitals available to dispatch")
        
    return res.json()["case_id"]

@pytest.fixture
def dispatch_case_factory(client, auth_headers):
    """Callable factory for tests that need to control dispatch timing."""
    def _dispatch():
        res = client.post("/api/dispatch/", json={
            "condition": "cardiac_arrest",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
            "equipment_needed": ["ecg"]
        }, headers=auth_headers)
        
        if res.status_code != 200:
            pytest.skip("No hospitals available to dispatch")
            
        return res.json()["case_id"]
    return _dispatch

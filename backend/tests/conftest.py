import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["PASSWORD_ITERATIONS"] = "1000"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def database():
    Base.metadata.create_all(engine)
    with TestSession() as db:
        for email, role in [("client@test.com", Role.client), ("other@test.com", Role.client), ("ops@test.com", Role.operator), ("admin@test.com", Role.admin)]:
            db.add(User(email=email, password_hash=hash_password("password"), role=role, name=email.split("@")[0]))
        db.commit()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    def override():
        with TestSession() as db: yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as value: yield value
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    def login(email):
        token = client.post("/auth/login", json={"email": email, "password": "password"}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return login

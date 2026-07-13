import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 确保项目根目录在 PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.base import Base, get_db
from main import app


# 使用内存 SQLite 作为测试数据库，每个测试独立
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db():
    """每个测试函数创建新表并返回 session，测试结束后清理。"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """返回 FastAPI 测试客户端。"""
    yield TestClient(app)


@pytest.fixture(scope="function")
def auth_headers():
    """预留认证头，当前系统为个人使用无需认证。"""
    return {}

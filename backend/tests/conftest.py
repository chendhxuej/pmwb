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
from tests.fake_master import install_fake_master
from utils.master_service import master_service_client

# ─── 防御性拦截：把人员中台（8001 master-service）出网调用换到内存实现 ──────
# 背景（防复发）：
#     backend 的 /api/v1/basic-data/* 已改造为代理层，实际数据由
#     services/master（8001）持有。conftest 的 dependency_overrides 只能拦住
#     本地 SQLAlchemy 的接口，**拦不住代理层的 HTTP 调用**。若测试直接调用
#     basic-data 接口，就会真实写入 MySQL `pmwb_master`，在「人员中台 →
#     组织管理」页面留下 CRM_xxxxxxxx 等脏数据（2026-08-28 实证）。
# 方案：整个测试会话把 master_service_client._request 替换为 FakeMasterBackend，
#       所有 basic-data 请求打到内存实现，测试完毕无需清理任何 MySQL 数据。
# --------------------------------------------------------------------------
_fake_master_backend = install_fake_master(__import__("pytest").MonkeyPatch(), master_service_client)


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

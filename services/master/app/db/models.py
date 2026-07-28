"""Master 服务数据模型：组织 + 人员主数据。"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PmwbRole(Base):
    """身份/角色定义表（选人下拉的身份选项来源）。"""

    __tablename__ = "pmwb_role"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    name = Column(String(64), nullable=False, unique=True, comment="角色名称（如：产品经理）")
    sort = Column(Integer, default=0, comment="排序号（小的在前）")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = ({"comment": "人员中台-身份/角色定义表"},)


class PmwbOrg(Base):
    """组织/团队表（选人下拉的分组维度）。"""

    __tablename__ = "pmwb_org"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    name = Column(String(128), nullable=False, unique=True, comment="组织/团队名称")
    description = Column(String(512), comment="组织描述（可空）")
    sort = Column(Integer, default=0, comment="排序号（小的在前）")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    source_trace = Column(String(64), comment="数据来源：manual / email_center / sa_info")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    staffs = relationship(
        "PmwbStaff",
        back_populates="org",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PmwbStaff.sort",
    )

    __table_args__ = ({"comment": "人员中台-组织表"},)


class PmwbStaff(Base):
    """人员主数据表（全站统一人员数据源）。"""

    __tablename__ = "pmwb_staff"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    name = Column(String(64), nullable=False, comment="姓名")
    org_id = Column(
        Integer,
        ForeignKey("pmwb_org.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属组织ID",
    )
    email = Column(String(255), comment="邮箱（可空）")
    phone = Column(String(64), comment="电话（可空）")
    role_hint = Column(String(128), comment="角色/职责备注（可空）")
    sort = Column(Integer, default=0, comment="排序号（小的在前）")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    source_trace = Column(String(64), comment="数据来源：manual / email_center / sa_info")
    legacy_id = Column(String(255), comment="原数据源记录ID（邮件中心Contact.id 或 sa_info.id）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    org = relationship("PmwbOrg", back_populates="staffs")

    __table_args__ = (
        UniqueConstraint("name", "org_id", name="uk_staff_name_org"),
        Index("idx_staff_org", "org_id"),
        {"comment": "人员中台-人员表"},
    )

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from core.SQL.sql_db import Base


class User(Base):
    __tablename__ = 'users'

    user_id   = Column(Integer, primary_key=True, index=True)
    name      = Column(String(255), index=True)
    user_type = Column(String(50))
    embedding = Column(JSON)
    status    = Column(Boolean, default=False)


class Session(Base):
    __tablename__ = 'sessions'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    checked_in_at   = Column(DateTime, nullable=False)
    checked_out_at  = Column(DateTime, nullable=True)   # NULL = currently in lab
    check_in_method = Column(String(20), default='face')  # face | manual | auto_checkout


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id             = Column(Integer, primary_key=True, index=True)
    action_type    = Column(String(30))
    target_user_id = Column(Integer)
    target_name    = Column(String(255))
    performed_by   = Column(String(50), default='admin')
    timestamp      = Column(DateTime)

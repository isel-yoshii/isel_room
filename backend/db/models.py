from __future__ import annotations
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from backend.db import Base


class User(Base):
    __tablename__ = 'users'

    user_id   = Column(Integer, primary_key=True, index=True)
    name      = Column(String(255), index=True)
    user_type = Column(String(50))
    embedding = Column(JSON)
    status    = Column(Boolean, default=False)


class LabSession(Base):
    # Not named Session: every module that touches it also imports flask.session
    # or a SQLAlchemy session.
    __tablename__ = 'sessions'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    checked_in_at   = Column(DateTime, nullable=False, index=True)
    checked_out_at  = Column(DateTime, nullable=True, index=True)
    check_in_method = Column(String(20), default='face')


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id             = Column(Integer, primary_key=True, index=True)
    action_type    = Column(String(30))
    target_user_id = Column(Integer)
    target_name    = Column(String(255))
    performed_by   = Column(String(50), default='admin')
    timestamp      = Column(DateTime, index=True)


class Device(Base):
    __tablename__ = 'devices'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    mac          = Column(String(17), nullable=False, unique=True)
    label        = Column(String(50))
    last_seen_at = Column(DateTime, nullable=True)
    # Set when a person or the nightly job checks the owner out. While set, seeing
    # this device does not check the owner back in — otherwise a phone still on
    # Wi-Fi would undo the checkout a minute later. Cleared by a face/manual
    # check-in, or by the device reappearing after being gone for the grace period.
    locked       = Column(Boolean, default=False, nullable=False)

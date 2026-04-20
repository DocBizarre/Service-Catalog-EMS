from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.sql import func
from database import Base

class App(Base):
    __tablename__ = "apps"
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    url         = Column(String, nullable=False)
    icon        = Column(String)
    description = Column(String)
    tag         = Column(String)
    online      = Column(Integer, default=1)
    created_at  = Column(DateTime, default=func.now())

class User(Base):
    __tablename__ = "users"
    id                   = Column(Integer, primary_key=True)
    username             = Column(String, nullable=False, unique=True)
    email                = Column(String, nullable=False, unique=True)
    password             = Column(String, nullable=False)
    role                 = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    created_at           = Column(DateTime, default=func.now())

class Role(Base):
    __tablename__ = "roles"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, nullable=False, unique=True)
    is_system  = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())

class Permission(Base):
    __tablename__ = "permissions"
    id     = Column(Integer, primary_key=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"))
    role   = Column(String, nullable=False)

class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "app_id"),)
    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    app_id  = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"))

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_log"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    action     = Column(String, nullable=False)
    detail     = Column(String)
    created_at = Column(DateTime, default=func.now())

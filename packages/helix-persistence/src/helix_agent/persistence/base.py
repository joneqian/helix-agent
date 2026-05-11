"""SQLAlchemy DeclarativeBase for Helix-Agent persistence layer."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All ORM models in this package inherit from it."""

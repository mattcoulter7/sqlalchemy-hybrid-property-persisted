from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, clear_mappers

from sqlalchemy_persisted_hybrid_property import install
from sqlalchemy_persisted_hybrid_property.registry import registry


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    """Keep global mapper/event registry state deterministic across dynamic models."""
    install()
    registry.clear()
    yield
    registry.clear()
    clear_mappers()


@pytest.fixture
def base_type():
    class Base(DeclarativeBase):
        pass

    return Base


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session

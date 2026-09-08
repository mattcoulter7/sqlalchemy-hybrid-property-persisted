from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.exceptions import DependencyConfigurationError


def _stored(session, model, pk, column_name):
    return session.execute(select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)).scalar_one()


def test_explicit_nested_dependency_invalidates_only_named_scalar(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "explicit_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

        @hybrid_persisted_property(depends_on="children.value", materialize="python")
        def total(self) -> int:
            return sum(child.value for child in self.children)

    class Child(Base):
        __tablename__ = "explicit_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("explicit_owner.id"))
        value: Mapped[int]
        ignored: Mapped[str] = mapped_column(default="")
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)
    owner = Owner(children=[Child(value=2, ignored="a")])
    session.add(owner)
    session.commit()

    owner.children[0].value = 7
    session.flush()
    assert _stored(session, Owner, owner.id, "total") == 7


def test_collection_dependency_detects_append_and_remove(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "explicit_collection_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner", cascade="all, delete-orphan")

        @hybrid_persisted_property(depends_on="children", materialize="python")
        def child_count(self) -> int:
            return len(self.children)

    class Child(Base):
        __tablename__ = "explicit_collection_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("explicit_collection_owner.id"))
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner()
    session.add(owner)
    session.flush()
    assert _stored(session, Owner, owner.id, "child_count") == 0

    child = Child()
    owner.children.append(child)
    session.flush()
    assert _stored(session, Owner, owner.id, "child_count") == 1

    owner.children.remove(child)
    session.flush()
    assert _stored(session, Owner, owner.id, "child_count") == 0


def test_invalid_explicit_dependency_fails_at_mapper_configuration(base_type):
    Base = base_type

    class Owner(Base):
        __tablename__ = "explicit_invalid"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(depends_on="missing.value")
        def total(self) -> int:
            return self.value

    with pytest.raises(DependencyConfigurationError, match="missing"):
        configure_mappers()

from __future__ import annotations

from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def _stored(session, model, pk, column_name):
    return session.execute(
        select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)
    ).scalar_one()


def test_python_only_property_materializes_from_explicit_dependency(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "python_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner", cascade="all, delete-orphan")

        @hybrid_persisted_property(
            depends_on=["children", "children.value"],
            materialize="python",
        )
        def total(self) -> int:
            return sum(child.value for child in self.children)

    class Child(Base):
        __tablename__ = "python_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("python_owner.id"))
        value: Mapped[int]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner(children=[Child(value=2), Child(value=5)])
    session.add(owner)
    session.flush()
    assert _stored(session, Owner, owner.id, "total") == 7

    owner.children[0].value = 9
    session.flush()
    assert _stored(session, Owner, owner.id, "total") == 14


def test_python_materialization_sets_backing_mapped_attribute_without_touching_hybrid_setter(
    base_type, engine, session
):
    Base = base_type
    setter_calls: list[int] = []

    class Metric(Base):
        __tablename__ = "python_setter"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(depends_on="value", materialize="python")
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.setter
        def _setter(self, value: int) -> None:
            setter_calls.append(value)
            self.value = value // 2

    configure_mappers()
    Base.metadata.create_all(engine)

    row = Metric(value=4)
    session.add(row)
    session.flush()

    assert setter_calls == []
    assert _stored(session, Metric, row.id, "doubled") == 8


def test_auto_falls_back_to_python_when_no_sql_expression_exists(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "python_auto"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(depends_on="value", materialize="auto")
        def label_length(self) -> int:
            return len(f"value={self.value}")

    configure_mappers()
    Base.metadata.create_all(engine)

    row = Metric(value=123)
    session.add(row)
    session.flush()
    assert _stored(session, Metric, row.id, "label_length") == len("value=123")

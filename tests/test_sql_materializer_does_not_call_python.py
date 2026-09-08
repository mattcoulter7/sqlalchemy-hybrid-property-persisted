from __future__ import annotations

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, Session, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_sql_materialization_does_not_evaluate_python_getter(base_type, engine):
    Base = base_type

    class Owner(Base):
        __tablename__ = "sql_only_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner", cascade="all, delete-orphan")

        @hybrid_persisted_property(materialize="sql")
        def total(self) -> int:
            raise AssertionError("Python getter must not be called for SQL materialization")

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return (
                select(func.coalesce(func.sum(Child.value), 0))
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "sql_only_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("sql_only_owner.id"))
        value: Mapped[int]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        owner = Owner(children=[Child(value=2), Child(value=5)])
        session.add(owner)
        session.flush()
        stored = session.execute(select(Owner.__table__.c.total).where(Owner.__table__.c.id == owner.id)).scalar_one()
        assert stored == 7

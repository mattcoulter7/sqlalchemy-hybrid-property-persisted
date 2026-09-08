from __future__ import annotations

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, Session, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_multiple_properties_on_same_owner_are_written_in_one_update(base_type, engine):
    Base = base_type

    class Owner(Base):
        __tablename__ = "multi_prop_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

        @hybrid_persisted_property(materialize="sql")
        def total(self) -> int:
            return sum(c.value for c in self.children)

        @total.inplace.expression
        @classmethod
        def _total_expr(cls):
            return select(func.coalesce(func.sum(Child.value), 0)).where(Child.owner_id == cls.id).correlate(cls).scalar_subquery()

        @hybrid_persisted_property(materialize="sql")
        def count(self) -> int:
            return len(self.children)

        @count.inplace.expression
        @classmethod
        def _count_expr(cls):
            return select(func.count(Child.id)).where(Child.owner_id == cls.id).correlate(cls).scalar_subquery()

    class Child(Base):
        __tablename__ = "multi_prop_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("multi_prop_owner.id"))
        value: Mapped[int]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    from sqlalchemy import event

    with Session(engine, expire_on_commit=False) as session:
        owner = Owner(children=[Child(value=2)])
        session.add(owner)
        session.commit()

        updates: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE") and "multi_prop_owner" in statement:
                updates.append(statement)

        try:
            owner.children[0].value = 7
            session.flush()
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert len(updates) == 1
        assert "total" in updates[0]
        assert "count" in updates[0]

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def _stored(session, model, pk, column_name):
    return session.execute(select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)).scalar_one()


def test_insert_materializes_same_row_hybrid(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "same_row_insert"
        id: Mapped[int] = mapped_column(primary_key=True)
        left: Mapped[int]
        right: Mapped[int]

        @hybrid_persisted_property()
        def total(self) -> int:
            return self.left + self.right

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return cls.left + cls.right

    configure_mappers()
    Base.metadata.create_all(engine)

    row = Metric(left=2, right=5)
    session.add(row)
    session.flush()

    assert _stored(session, Metric, row.id, "total") == 7


def test_update_materializes_same_row_hybrid(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "same_row_update"
        id: Mapped[int] = mapped_column(primary_key=True)
        left: Mapped[int]
        right: Mapped[int]

        @hybrid_persisted_property()
        def total(self) -> int:
            return self.left + self.right

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return cls.left + cls.right

    configure_mappers()
    Base.metadata.create_all(engine)
    row = Metric(left=2, right=5)
    session.add(row)
    session.commit()

    row.right = 10
    session.flush()

    assert _stored(session, Metric, row.id, "total") == 12


def test_noop_flush_does_not_emit_materialization_update(base_type, engine):
    Base = base_type

    class Metric(Base):
        __tablename__ = "same_row_noop"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _doubled_expression(cls):
            return cls.value * 2

    configure_mappers()
    Base.metadata.create_all(engine)

    statements: list[str] = []
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        with Session(engine, expire_on_commit=False) as session:
            row = Metric(value=3)
            session.add(row)
            session.commit()
            statements.clear()
            session.flush()
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert not [s for s in statements if s.lstrip().upper().startswith("UPDATE")]

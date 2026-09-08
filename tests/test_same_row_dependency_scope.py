from __future__ import annotations

from sqlalchemy.orm import Mapped, Session, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_same_row_unrelated_attribute_does_not_materialize(base_type, engine):
    Base = base_type

    class Metric(Base):
        __tablename__ = "same_scope"
        id: Mapped[int] = mapped_column(primary_key=True)
        left: Mapped[int]
        right: Mapped[int]
        ignored: Mapped[str]

        @hybrid_property_persisted(materialize="sql")
        def total(self) -> int:
            return self.left + self.right

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return cls.left + cls.right

    configure_mappers()
    Base.metadata.create_all(engine)

    from sqlalchemy import event

    with Session(engine, expire_on_commit=False) as session:
        row = Metric(left=1, right=2, ignored="a")
        session.add(row)
        session.commit()

        updates: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE") and "same_scope" in statement:
                updates.append(statement)

        try:
            row.ignored = "b"
            session.flush()
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        # The normal row UPDATE is expected; a second persisted-hybrid UPDATE is not.
        assert len(updates) == 1
        assert "ignored" in updates[0]
        assert "total" not in updates[0]

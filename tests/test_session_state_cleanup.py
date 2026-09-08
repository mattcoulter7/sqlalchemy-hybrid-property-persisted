from __future__ import annotations

from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_internal_pending_materialization_state_is_cleared_after_successful_flush(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "state_cleanup"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(materialize="sql")
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _expr(cls):
            return cls.value * 2

    configure_mappers()
    Base.metadata.create_all(engine)
    session.add(Metric(value=2))
    session.flush()

    assert "sqlalchemy_persisted_hybrid.pending" not in session.info


def test_internal_pending_materialization_state_is_cleared_after_rollback(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "state_cleanup_rollback"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(materialize="sql")
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _expr(cls):
            return cls.value * 2

    configure_mappers()
    Base.metadata.create_all(engine)
    row = Metric(value=2)
    session.add(row)
    session.flush()
    row.value = 3
    session.rollback()

    assert "sqlalchemy_persisted_hybrid.pending" not in session.info

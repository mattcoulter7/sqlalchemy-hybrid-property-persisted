from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_sql_materialization_expires_or_synchronizes_hidden_storage_state(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "storage_state"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_property_persisted(materialize="sql")
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _doubled_expression(cls):
            return cls.value * 2

    configure_mappers()
    Base.metadata.create_all(engine)
    descriptor = inspect(Metric).all_orm_descriptors["doubled"]

    row = Metric(value=3)
    session.add(row)
    session.flush()

    # The hidden ORM attribute must never remain confidently stale after a direct
    # post-flush SQL UPDATE. Either synchronize it or expire it so access reloads.
    state = inspect(row)
    if descriptor.storage_key in state.expired_attributes:
        assert getattr(row, descriptor.storage_key) == 6
    else:
        assert getattr(row, descriptor.storage_key) == 6

    row.value = 4
    session.flush()
    assert getattr(row, descriptor.storage_key) == 8

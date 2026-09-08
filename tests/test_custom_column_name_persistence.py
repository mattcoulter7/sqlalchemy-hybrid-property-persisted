from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_custom_column_name_is_written_during_flush(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "custom_persist"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(column_name="reporting_doubled")
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _doubled_expression(cls):
            return cls.value * 2

    configure_mappers()
    Base.metadata.create_all(engine)

    row = Metric(value=6)
    session.add(row)
    session.flush()

    assert (
        session.execute(
            select(Metric.__table__.c.reporting_doubled).where(Metric.__table__.c.id == row.id)
        ).scalar_one()
        == 12
    )

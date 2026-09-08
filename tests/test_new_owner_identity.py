from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_sql_materialization_handles_database_generated_primary_key(base_type, engine, session):
    Base = base_type

    class Metric(Base):
        __tablename__ = "generated_pk_metric"
        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
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

    row = Metric(value=6)
    assert row.id is None
    session.add(row)
    session.flush()

    assert row.id is not None
    assert session.execute(select(Metric.__table__.c.doubled).where(Metric.__table__.c.id == row.id)).scalar_one() == 12

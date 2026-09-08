from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_materialized_update_participates_in_transaction_rollback(base_type, engine):
    Base = base_type

    class Metric(Base):
        __tablename__ = "tx_metric"
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

    with Session(engine) as session:
        row = Metric(value=2)
        session.add(row)
        session.commit()
        row_id = row.id

    with Session(engine) as session:
        row = session.get(Metric, row_id)
        row.value = 9
        session.flush()
        assert session.execute(
            select(Metric.__table__.c.doubled).where(Metric.__table__.c.id == row_id)
        ).scalar_one() == 18
        session.rollback()

    with Session(engine) as session:
        assert session.execute(
            select(Metric.__table__.c.doubled).where(Metric.__table__.c.id == row_id)
        ).scalar_one() == 4

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column
from sqlalchemy.schema import CreateTable

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_postgresql_ddl_contains_real_persisted_column(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "ddl_metric"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_property_persisted(nullable=False)
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    ddl = str(CreateTable(Metric.__table__).compile(dialect=postgresql.dialect()))

    assert "doubled INTEGER NOT NULL" in ddl

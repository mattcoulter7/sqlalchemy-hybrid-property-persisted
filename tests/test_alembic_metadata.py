from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def test_alembic_autogenerate_sees_persisted_column(base_type, engine):
    Base = base_type

    class Metric(Base):
        __tablename__ = "alembic_metric"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()

    # Create a deliberately old schema without the injected reporting column.
    from sqlalchemy import Column, Integer, MetaData, Table

    old = MetaData()
    Table(
        "alembic_metric",
        old,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )
    old.create_all(engine)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diffs = compare_metadata(context, Base.metadata)

    add_columns = [diff for diff in diffs if diff[0] == "add_column"]
    assert len(add_columns) == 1
    assert add_columns[0][2] == "alembic_metric"
    assert add_columns[0][3].name == "doubled"

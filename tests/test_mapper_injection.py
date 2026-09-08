from __future__ import annotations

import pytest
from sqlalchemy import Integer, inspect, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import HybridPersistedProperty, hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.exceptions import PersistedColumnConflictError
from sqlalchemy_persisted_hybrid_property.registry import registry


def test_mapper_injects_real_physical_column_without_replacing_hybrid(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_metric"
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
    mapper = inspect(Metric)
    descriptor = mapper.all_orm_descriptors["total"]

    assert isinstance(descriptor, HybridPersistedProperty)
    assert "total" in Metric.__table__.c
    assert isinstance(Metric.__table__.c.total.type, Integer)
    assert descriptor.storage_key in mapper.attrs
    assert descriptor.storage_key != "total"
    assert mapper.attrs[descriptor.storage_key].columns[0] is Metric.__table__.c.total

    sql = str(select(Metric.total))
    assert "mapper_metric.left + mapper_metric.right" in sql


def test_custom_physical_column_name_is_honored(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_custom_column"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(column_name="reporting_value")
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    descriptor = inspect(Metric).all_orm_descriptors["doubled"]

    assert "reporting_value" in Metric.__table__.c
    assert "doubled" not in Metric.__table__.c
    assert inspect(Metric).attrs[descriptor.storage_key].columns[0].name == "reporting_value"


def test_column_nullability_default_and_server_default_are_applied(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_defaults"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(nullable=False, default=3, server_default="3")
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    column = Metric.__table__.c.doubled

    assert column.nullable is False
    assert column.default is not None
    assert column.server_default is not None


def test_metadata_sees_injected_column_for_migrations(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_metadata"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()

    assert Base.metadata.tables["mapper_metadata"].c.doubled is Metric.__table__.c.doubled


def test_registry_records_descriptor_for_owner_mapper(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_registry"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    descriptors = registry.descriptors_for(inspect(Metric))

    assert [entry.name for entry in descriptors] == ["doubled"]


def test_configuration_is_idempotent(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "mapper_idempotent"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    configure_mappers()

    assert [column.name for column in Metric.__table__.columns].count("doubled") == 1
    assert len(registry.descriptors_for(inspect(Metric))) == 1


def test_existing_physical_column_conflict_fails_loudly(base_type):
    Base = base_type

    with pytest.raises(PersistedColumnConflictError, match="total"):

        class Metric(Base):
            __tablename__ = "mapper_collision"
            id: Mapped[int] = mapped_column(primary_key=True)
            _already_total: Mapped[int] = mapped_column("total")
            left: Mapped[int]
            right: Mapped[int]

            @hybrid_persisted_property()
            def total(self) -> int:
                return self.left + self.right

        configure_mappers()

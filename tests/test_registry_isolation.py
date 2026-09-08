from __future__ import annotations

import gc
import weakref

from sqlalchemy import inspect
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.registry import PersistedHybridRegistry


def test_registry_does_not_duplicate_descriptor_entries(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "registry_duplicate"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    registry = PersistedHybridRegistry()
    mapper = inspect(Metric)
    descriptor = mapper.all_orm_descriptors["doubled"]

    registry.register(mapper, "doubled", descriptor)
    registry.register(mapper, "doubled", descriptor)
    assert len(registry.descriptors_for(mapper)) == 1


def test_registry_clear_removes_entries(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "registry_clear"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

    configure_mappers()
    registry = PersistedHybridRegistry()
    mapper = inspect(Metric)
    descriptor = mapper.all_orm_descriptors["doubled"]
    registry.register(mapper, "doubled", descriptor)

    registry.clear()
    assert registry.descriptors_for(mapper) == ()

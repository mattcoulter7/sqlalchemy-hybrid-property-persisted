from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, inspect
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column

from sqlalchemy_persisted_hybrid_property import HybridPersistedProperty, hybrid_persisted_property


def test_subclass_getter_copy_remains_persisted_hybrid(base_type):
    Base = base_type

    class BaseMetric(Base):
        __tablename__ = "inherit_base"
        id: Mapped[int] = mapped_column(primary_key=True)
        type: Mapped[str]
        value: Mapped[int]
        __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "base"}

        @hybrid_persisted_property(type_=Integer)
        def score(self) -> int:
            return self.value

    class DoubledMetric(BaseMetric):
        __tablename__ = "inherit_double"
        id: Mapped[int] = mapped_column(ForeignKey("inherit_base.id"), primary_key=True)
        __mapper_args__ = {"polymorphic_identity": "double"}

        @BaseMetric.score.getter
        def score(self) -> int:
            return self.value * 2

    configure_mappers()

    descriptor = inspect(DoubledMetric).all_orm_descriptors["score"]
    assert isinstance(descriptor, HybridPersistedProperty)
    assert isinstance(descriptor.persisted_type, Integer)


def test_inplace_expression_on_base_does_not_duplicate_backing_column(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "inherit_inplace"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property()
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _doubled_expr(cls):
            return cls.value * 2

    configure_mappers()
    assert [c.name for c in Metric.__table__.columns].count("doubled") == 1

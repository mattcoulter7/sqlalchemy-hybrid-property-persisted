from __future__ import annotations

from sqlalchemy import select
from sqlmodel import Field

from sqlalchemy_persisted_hybrid_property import HybridPersistedProperty, hybrid_property_persisted
from sqlalchemy_persisted_hybrid_property.sqlmodel import SQLModel


def test_sqlmodel_class_body_accepts_persisted_hybrid_without_per_model_config():
    class Metric(SQLModel, table=True):
        __tablename__ = "sqlmodel_metric"
        id: int | None = Field(default=None, primary_key=True)
        left: int
        right: int

        @hybrid_property_persisted()
        def total(self) -> int:
            return self.left + self.right

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return cls.left + cls.right

    assert isinstance(Metric.__dict__["total"], HybridPersistedProperty)
    assert "total" in Metric.__table__.c


def test_sqlmodel_pydantic_fields_do_not_include_hidden_backing_attribute():
    class Metric(SQLModel, table=True):
        __tablename__ = "sqlmodel_fields"
        id: int | None = Field(default=None, primary_key=True)
        value: int

        @hybrid_property_persisted()
        def doubled(self) -> int:
            return self.value * 2

    descriptor = Metric.__dict__["doubled"]
    assert descriptor.storage_key not in Metric.model_fields
    assert "doubled" not in Metric.model_fields


def test_sqlmodel_instance_validation_and_dump_remain_normal():
    class Metric(SQLModel, table=True):
        __tablename__ = "sqlmodel_dump"
        id: int | None = Field(default=None, primary_key=True)
        value: int

        @hybrid_property_persisted()
        def doubled(self) -> int:
            return self.value * 2

    row = Metric(value=4)
    assert row.doubled == 8
    assert row.model_dump() == {"id": None, "value": 4}


def test_sqlmodel_hybrid_class_expression_remains_queryable():
    class Metric(SQLModel, table=True):
        __tablename__ = "sqlmodel_query"
        id: int | None = Field(default=None, primary_key=True)
        value: int

        @hybrid_property_persisted()
        def doubled(self) -> int:
            return self.value * 2

        @doubled.inplace.expression
        @classmethod
        def _doubled_expression(cls):
            return cls.value * 2

    sql = str(select(Metric.id).where(Metric.doubled > 5))
    assert "sqlmodel_query.value *" in sql

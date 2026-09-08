from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.exceptions import (
    DependencyAmbiguityError,
    PersistedHybridConfigurationError,
)


def test_sql_materialize_requires_sql_expression(base_type):
    Base = base_type

    class Metric(Base):
        __tablename__ = "error_sql_without_expr"
        id: Mapped[int] = mapped_column(primary_key=True)
        value: Mapped[int]

        @hybrid_persisted_property(depends_on="value", materialize="sql")
        def doubled(self) -> int:
            return self.value * 2

    with pytest.raises(PersistedHybridConfigurationError, match="SQL expression"):
        configure_mappers()


def test_auto_dependency_ambiguity_fails_loudly(base_type):
    Base = base_type

    class Address(Base):
        __tablename__ = "ambiguous_address"
        id: Mapped[int] = mapped_column(primary_key=True)
        risk: Mapped[int]

    class Invoice(Base):
        __tablename__ = "ambiguous_invoice"
        id: Mapped[int] = mapped_column(primary_key=True)
        billing_address_id: Mapped[int] = mapped_column(ForeignKey("ambiguous_address.id"))
        shipping_address_id: Mapped[int] = mapped_column(ForeignKey("ambiguous_address.id"))
        billing_address: Mapped[Address] = relationship(foreign_keys=[billing_address_id])
        shipping_address: Mapped[Address] = relationship(foreign_keys=[shipping_address_id])

        @hybrid_persisted_property(materialize="python")
        def risk(self) -> int:
            return self.billing_address.risk

    with pytest.raises(DependencyAmbiguityError):
        configure_mappers()


def test_explicit_path_resolves_ambiguous_graph(base_type):
    Base = base_type

    class Address(Base):
        __tablename__ = "resolved_address"
        id: Mapped[int] = mapped_column(primary_key=True)
        risk: Mapped[int]

    class Invoice(Base):
        __tablename__ = "resolved_invoice"
        id: Mapped[int] = mapped_column(primary_key=True)
        billing_address_id: Mapped[int] = mapped_column(ForeignKey("resolved_address.id"))
        shipping_address_id: Mapped[int] = mapped_column(ForeignKey("resolved_address.id"))
        billing_address: Mapped[Address] = relationship(foreign_keys=[billing_address_id])
        shipping_address: Mapped[Address] = relationship(foreign_keys=[shipping_address_id])

        @hybrid_persisted_property(
            depends_on="billing_address.risk",
            materialize="python",
        )
        def risk(self) -> int:
            return self.billing_address.risk

    configure_mappers()  # must not raise

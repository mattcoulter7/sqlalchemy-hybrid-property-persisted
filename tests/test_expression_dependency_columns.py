from __future__ import annotations

from sqlalchemy import ForeignKey, func, inspect, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted
from sqlalchemy_persisted_hybrid_property.registry import registry


def test_auto_expression_dependency_records_specific_child_columns(base_type):
    Base = base_type

    class Owner(Base):
        __tablename__ = "expr_dep_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

        @hybrid_property_persisted(materialize="sql")
        def total(self) -> int:
            return sum(c.value for c in self.children)

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return (
                select(func.coalesce(func.sum(Child.value), 0))
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "expr_dep_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("expr_dep_owner.id"))
        value: Mapped[int]
        ignored: Mapped[str]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    deps = registry.dependencies_for(inspect(Owner))
    total_dep = next(dep for dep in deps if dep.property_name == "total")

    assert total_dep.references(inspect(Child), "value")
    assert total_dep.references(inspect(Child), "owner_id")
    assert not total_dep.references(inspect(Child), "ignored")

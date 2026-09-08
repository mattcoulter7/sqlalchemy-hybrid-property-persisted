from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey, func, select, update
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.exceptions import BulkMutationUnsupportedError


def test_orm_bulk_update_of_dependency_fails_instead_of_silently_staling_owner(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "bulk_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

        @hybrid_persisted_property(materialize="sql")
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
        __tablename__ = "bulk_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("bulk_owner.id"))
        value: Mapped[int]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)
    session.add(Owner(children=[Child(value=2)]))
    session.commit()

    with pytest.raises(BulkMutationUnsupportedError, match="bulk"):
        session.execute(update(Child).values(value=9))

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, func, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_composite_owner_key_is_supported(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "composite_owner"
        tenant_id: Mapped[int] = mapped_column(primary_key=True)
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

        @hybrid_property_persisted(materialize="sql")
        def total(self) -> int:
            return sum(child.value for child in self.children)

        @total.inplace.expression
        @classmethod
        def _total_expression(cls):
            return (
                select(func.coalesce(func.sum(Child.value), 0))
                .where(
                    Child.owner_tenant_id == cls.tenant_id,
                    Child.owner_id == cls.id,
                )
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "composite_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_tenant_id: Mapped[int]
        owner_id: Mapped[int]
        value: Mapped[int]
        __table_args__ = (
            ForeignKeyConstraint(
                ["owner_tenant_id", "owner_id"],
                ["composite_owner.tenant_id", "composite_owner.id"],
            ),
        )
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner(tenant_id=7, id=11, children=[Child(value=5)])
    session.add(owner)
    session.flush()

    stored = session.execute(
        select(Owner.__table__.c.total).where(
            Owner.__table__.c.tenant_id == 7,
            Owner.__table__.c.id == 11,
        )
    ).scalar_one()
    assert stored == 5

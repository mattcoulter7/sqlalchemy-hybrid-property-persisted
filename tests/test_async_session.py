from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


@pytest.mark.async_
@pytest.mark.asyncio
async def test_async_session_flush_materializes_relationship_hybrid():
    class Base(DeclarativeBase):
        pass

    class Owner(Base):
        __tablename__ = "async_owner"
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
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "async_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("async_owner.id"))
        value: Mapped[int]
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            owner = Owner(children=[Child(value=2), Child(value=5)])
            session.add(owner)
            await session.flush()

            stored = (
                await session.execute(select(Owner.__table__.c.total).where(Owner.__table__.c.id == owner.id))
            ).scalar_one()
            assert stored == 7

            owner.children[0].value = 10
            await session.flush()
            stored = (
                await session.execute(select(Owner.__table__.c.total).where(Owner.__table__.c.id == owner.id))
            ).scalar_one()
            assert stored == 15
    finally:
        await engine.dispose()

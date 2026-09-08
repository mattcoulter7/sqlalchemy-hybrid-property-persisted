from __future__ import annotations

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def test_deleting_owner_does_not_attempt_postflush_materialization(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "delete_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(
            back_populates="owner",
            cascade="all, delete-orphan",
        )

        @hybrid_property_persisted(materialize="sql")
        def child_count(self) -> int:
            return len(self.children)

        @child_count.inplace.expression
        @classmethod
        def _child_count_expression(cls):
            return select(func.count(Child.id)).where(Child.owner_id == cls.id).correlate(cls).scalar_subquery()

    class Child(Base):
        __tablename__ = "delete_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("delete_owner.id"))
        owner: Mapped[Owner] = relationship(back_populates="children")

    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner(children=[Child()])
    session.add(owner)
    session.commit()
    owner_id = owner.id

    session.delete(owner)
    session.flush()

    assert (
        session.execute(
            select(func.count()).select_from(Owner.__table__).where(Owner.__table__.c.id == owner_id)
        ).scalar_one()
        == 0
    )

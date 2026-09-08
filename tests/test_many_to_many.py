from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table, func, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def _stored(session, model, pk, column_name):
    return session.execute(select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)).scalar_one()


def test_many_to_many_collection_append_and_remove_materialize_owner(base_type, engine, session):
    Base = base_type
    association = Table(
        "m2m_owner_tag",
        Base.metadata,
        Column("owner_id", ForeignKey("m2m_owner.id"), primary_key=True),
        Column("tag_id", ForeignKey("m2m_tag.id"), primary_key=True),
    )

    class Owner(Base):
        __tablename__ = "m2m_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        tags: Mapped[list[Tag]] = relationship(secondary=association, back_populates="owners")

        @hybrid_persisted_property(materialize="sql")
        def tag_count(self) -> int:
            return len(self.tags)

        @tag_count.inplace.expression
        @classmethod
        def _tag_count_expression(cls):
            return (
                select(func.count(association.c.tag_id))
                .where(association.c.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Tag(Base):
        __tablename__ = "m2m_tag"
        id: Mapped[int] = mapped_column(primary_key=True)
        owners: Mapped[list[Owner]] = relationship(secondary=association, back_populates="tags")

    configure_mappers()
    Base.metadata.create_all(engine)

    first = Tag()
    second = Tag()
    owner = Owner(tags=[first])
    session.add_all([owner, second])
    session.commit()

    assert _stored(session, Owner, owner.id, "tag_count") == 1

    owner.tags.append(second)
    session.flush()
    assert _stored(session, Owner, owner.id, "tag_count") == 2

    owner.tags.remove(first)
    session.flush()
    assert _stored(session, Owner, owner.id, "tag_count") == 1

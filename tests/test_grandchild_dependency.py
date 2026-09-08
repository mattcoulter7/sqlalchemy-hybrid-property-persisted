from __future__ import annotations

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


def _stored(session, model, pk, column_name):
    return session.execute(select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)).scalar_one()


def test_grandchild_scalar_change_materializes_root_owner(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "grand_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner", cascade="all, delete-orphan")

        @hybrid_property_persisted(materialize="sql")
        def grand_total(self) -> int:
            return sum(gc.value for child in self.children for gc in child.grandchildren)

        @grand_total.inplace.expression
        @classmethod
        def _grand_total_expression(cls):
            return (
                select(func.coalesce(func.sum(Grandchild.value), 0))
                .join(Child, Child.id == Grandchild.child_id)
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "grand_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("grand_owner.id"))
        owner: Mapped[Owner] = relationship(back_populates="children")
        grandchildren: Mapped[list[Grandchild]] = relationship(back_populates="child", cascade="all, delete-orphan")

    class Grandchild(Base):
        __tablename__ = "grand_grandchild"
        id: Mapped[int] = mapped_column(primary_key=True)
        child_id: Mapped[int] = mapped_column(ForeignKey("grand_child.id"))
        value: Mapped[int]
        child: Mapped[Child] = relationship(back_populates="grandchildren")

    configure_mappers()
    Base.metadata.create_all(engine)

    gc = Grandchild(value=2)
    owner = Owner(children=[Child(grandchildren=[gc])])
    session.add(owner)
    session.commit()

    gc.value = 9
    session.flush()

    assert _stored(session, Owner, owner.id, "grand_total") == 9


def test_grandchild_reparent_between_child_branches_updates_both_roots(base_type, engine, session):
    Base = base_type

    class Owner(Base):
        __tablename__ = "grand_reparent_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner", cascade="all, delete-orphan")

        @hybrid_property_persisted(materialize="sql")
        def grand_total(self) -> int:
            return sum(gc.value for child in self.children for gc in child.grandchildren)

        @grand_total.inplace.expression
        @classmethod
        def _grand_total_expression(cls):
            return (
                select(func.coalesce(func.sum(Grandchild.value), 0))
                .join(Child, Child.id == Grandchild.child_id)
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = "grand_reparent_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("grand_reparent_owner.id"))
        owner: Mapped[Owner] = relationship(back_populates="children")
        grandchildren: Mapped[list[Grandchild]] = relationship(back_populates="child")

    class Grandchild(Base):
        __tablename__ = "grand_reparent_gc"
        id: Mapped[int] = mapped_column(primary_key=True)
        child_id: Mapped[int] = mapped_column(ForeignKey("grand_reparent_child.id"))
        value: Mapped[int]
        child: Mapped[Child] = relationship(back_populates="grandchildren")

    configure_mappers()
    Base.metadata.create_all(engine)

    gc = Grandchild(value=6)
    old_child = Child(grandchildren=[gc])
    new_child = Child()
    old_owner = Owner(children=[old_child])
    new_owner = Owner(children=[new_child])
    session.add_all([old_owner, new_owner])
    session.commit()

    gc.child = new_child
    session.flush()

    assert _stored(session, Owner, old_owner.id, "grand_total") == 0
    assert _stored(session, Owner, new_owner.id, "grand_total") == 6

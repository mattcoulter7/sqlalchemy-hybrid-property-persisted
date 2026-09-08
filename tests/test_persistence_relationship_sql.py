from __future__ import annotations

from sqlalchemy import ForeignKey, func, select
from sqlalchemy.orm import Mapped, Session, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def _stored(session: Session, model, pk, column_name: str):
    return session.execute(
        select(model.__table__.c[column_name]).where(model.__table__.c.id == pk)
    ).scalar_one()


def _models(Base, prefix: str):
    class Owner(Base):
        __tablename__ = f"{prefix}_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(
            back_populates="owner",
            cascade="all, delete-orphan",
        )

        @hybrid_persisted_property(materialize="auto")
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

        @hybrid_persisted_property(materialize="auto")
        def child_count(self) -> int:
            return len(self.children)

        @child_count.inplace.expression
        @classmethod
        def _child_count_expression(cls):
            return (
                select(func.count(Child.id))
                .where(Child.owner_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

    class Child(Base):
        __tablename__ = f"{prefix}_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int | None] = mapped_column(ForeignKey(f"{prefix}_owner.id"))
        value: Mapped[int]
        ignored: Mapped[str] = mapped_column(default="")
        owner: Mapped[Owner | None] = relationship(back_populates="children")

    return Owner, Child


def test_child_insert_is_visible_to_sql_materializer_in_same_flush(base_type, engine, session):
    Base = base_type
    Owner, Child = _models(Base, "rel_insert")
    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner(children=[Child(value=3), Child(value=4)])
    session.add(owner)
    session.flush()

    # This catches an incorrect implementation that executes the aggregate UPDATE
    # in before_flush, before child INSERTs have reached the database.
    assert _stored(session, Owner, owner.id, "total") == 7
    assert _stored(session, Owner, owner.id, "child_count") == 2


def test_child_scalar_update_materializes_owner(base_type, engine, session):
    Base = base_type
    Owner, Child = _models(Base, "rel_update")
    configure_mappers()
    Base.metadata.create_all(engine)

    owner = Owner(children=[Child(value=3), Child(value=4)])
    session.add(owner)
    session.commit()

    owner.children[0].value = 10
    session.flush()

    assert _stored(session, Owner, owner.id, "total") == 14
    assert _stored(session, Owner, owner.id, "child_count") == 2


def test_unrelated_child_column_does_not_recompute_column_scoped_hybrid(base_type, engine):
    Base = base_type
    Owner, Child = _models(Base, "rel_irrelevant")
    configure_mappers()
    Base.metadata.create_all(engine)

    from sqlalchemy import event

    updates: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE") and "rel_irrelevant_owner" in statement:
            updates.append(statement)

    try:
        with Session(engine, expire_on_commit=False) as session:
            owner = Owner(children=[Child(value=3, ignored="a")])
            session.add(owner)
            session.commit()
            updates.clear()
            owner.children[0].ignored = "b"
            session.flush()
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert updates == []


def test_child_removal_materializes_owner_after_delete(base_type, engine, session):
    Base = base_type
    Owner, Child = _models(Base, "rel_remove")
    configure_mappers()
    Base.metadata.create_all(engine)

    first = Child(value=3)
    second = Child(value=4)
    owner = Owner(children=[first, second])
    session.add(owner)
    session.commit()

    owner.children.remove(first)
    session.flush()

    assert _stored(session, Owner, owner.id, "total") == 4
    assert _stored(session, Owner, owner.id, "child_count") == 1


def test_child_delete_via_session_delete_materializes_old_owner(base_type, engine, session):
    Base = base_type
    Owner, Child = _models(Base, "rel_delete")
    configure_mappers()
    Base.metadata.create_all(engine)

    first = Child(value=3)
    second = Child(value=4)
    owner = Owner(children=[first, second])
    session.add(owner)
    session.commit()

    session.delete(first)
    session.flush()

    assert _stored(session, Owner, owner.id, "total") == 4
    assert _stored(session, Owner, owner.id, "child_count") == 1


def test_relationship_reparent_updates_old_and_new_owners(base_type, engine, session):
    Base = base_type
    Owner, Child = _models(Base, "rel_reparent")
    configure_mappers()
    Base.metadata.create_all(engine)

    child = Child(value=8)
    old = Owner(children=[child])
    new = Owner()
    session.add_all([old, new])
    session.commit()

    child.owner = new
    session.flush()

    assert _stored(session, Owner, old.id, "total") == 0
    assert _stored(session, Owner, old.id, "child_count") == 0
    assert _stored(session, Owner, new.id, "total") == 8
    assert _stored(session, Owner, new.id, "child_count") == 1


def test_fk_only_reparent_updates_old_and_new_owners_even_if_relationships_unloaded(
    base_type, engine
):
    Base = base_type
    Owner, Child = _models(Base, "rel_fk_reparent")
    configure_mappers()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        old = Owner(children=[Child(value=8)])
        new = Owner()
        session.add_all([old, new])
        session.commit()
        old_id, new_id = old.id, new.id
        child_id = old.children[0].id

    with Session(engine, expire_on_commit=False) as session:
        child = session.get(Child, child_id)
        assert child is not None
        child.owner_id = new_id
        session.flush()

        assert _stored(session, Owner, old_id, "total") == 0
        assert _stored(session, Owner, new_id, "total") == 8


def test_fk_set_to_none_updates_old_owner(base_type, engine):
    Base = base_type
    Owner, Child = _models(Base, "rel_orphan_fk")
    configure_mappers()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        owner = Owner(children=[Child(value=8)])
        session.add(owner)
        session.commit()
        owner_id = owner.id
        child_id = owner.children[0].id

    with Session(engine, expire_on_commit=False) as session:
        child = session.get(Child, child_id)
        child.owner_id = None
        session.flush()
        assert _stored(session, Owner, owner_id, "total") == 0
        assert _stored(session, Owner, owner_id, "child_count") == 0


def test_multiple_impacted_owners_are_batched_by_owner_mapper(base_type, engine):
    Base = base_type
    Owner, Child = _models(Base, "rel_batch")
    configure_mappers()
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        owners = [Owner(children=[Child(value=index)]) for index in (1, 2, 3)]
        session.add_all(owners)
        session.commit()

        from sqlalchemy import event

        owner_updates: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE") and "rel_batch_owner" in statement:
                owner_updates.append(statement)

        try:
            for owner in owners:
                owner.children[0].value += 10
            session.flush()
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert len(owner_updates) == 1
        assert [_stored(session, Owner, owner.id, "total") for owner in owners] == [11, 12, 13]

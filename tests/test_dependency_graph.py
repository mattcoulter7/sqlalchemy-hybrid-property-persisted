from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey, inspect
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property.dependencies import DependencyGraph
from sqlalchemy_persisted_hybrid_property.exceptions import (
    DependencyAmbiguityError,
    DependencyConfigurationError,
)


def test_graph_resolves_unique_relationship_path(base_type):
    Base = base_type

    class Owner(Base):
        __tablename__ = "dep_owner"
        id: Mapped[int] = mapped_column(primary_key=True)
        children: Mapped[list[Child]] = relationship(back_populates="owner")

    class Child(Base):
        __tablename__ = "dep_child"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(ForeignKey("dep_owner.id"))
        owner: Mapped[Owner] = relationship(back_populates="children")
        grandchildren: Mapped[list[Grandchild]] = relationship(back_populates="child")

    class Grandchild(Base):
        __tablename__ = "dep_grandchild"
        id: Mapped[int] = mapped_column(primary_key=True)
        child_id: Mapped[int] = mapped_column(ForeignKey("dep_child.id"))
        child: Mapped[Child] = relationship(back_populates="grandchildren")

    configure_mappers()
    graph = DependencyGraph.from_mappers([inspect(Owner), inspect(Child), inspect(Grandchild)])
    path = graph.path(inspect(Grandchild), inspect(Owner))

    assert [step.relationship.key for step in path.steps] == ["child", "owner"]


def test_graph_rejects_ambiguous_paths(base_type):
    Base = base_type

    class Address(Base):
        __tablename__ = "dep_address"
        id: Mapped[int] = mapped_column(primary_key=True)

    class Invoice(Base):
        __tablename__ = "dep_invoice"
        id: Mapped[int] = mapped_column(primary_key=True)
        billing_address_id: Mapped[int] = mapped_column(ForeignKey("dep_address.id"))
        shipping_address_id: Mapped[int] = mapped_column(ForeignKey("dep_address.id"))
        billing_address: Mapped[Address] = relationship(foreign_keys=[billing_address_id])
        shipping_address: Mapped[Address] = relationship(foreign_keys=[shipping_address_id])

    configure_mappers()
    graph = DependencyGraph.from_mappers([inspect(Address), inspect(Invoice)])

    with pytest.raises(DependencyAmbiguityError):
        graph.path(inspect(Address), inspect(Invoice))


def test_graph_handles_cycles_without_recursion(base_type):
    Base = base_type

    class Node(Base):
        __tablename__ = "dep_node"
        id: Mapped[int] = mapped_column(primary_key=True)
        parent_id: Mapped[int | None] = mapped_column(ForeignKey("dep_node.id"))
        parent: Mapped[Node | None] = relationship(remote_side="Node.id", back_populates="children")
        children: Mapped[list[Node]] = relationship(back_populates="parent")

    configure_mappers()
    graph = DependencyGraph.from_mappers([inspect(Node)])
    path = graph.path(inspect(Node), inspect(Node))
    assert path.steps == ()


def test_explicit_dependency_path_validation_rejects_unknown_attribute(base_type):
    Base = base_type

    class Owner(Base):
        __tablename__ = "dep_invalid_owner"
        id: Mapped[int] = mapped_column(primary_key=True)

    configure_mappers()
    graph = DependencyGraph.from_mappers([inspect(Owner)])

    with pytest.raises(DependencyConfigurationError, match="missing"):
        graph.validate_explicit_path(inspect(Owner), "missing.value")

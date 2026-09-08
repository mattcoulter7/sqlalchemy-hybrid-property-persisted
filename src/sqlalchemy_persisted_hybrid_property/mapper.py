from __future__ import annotations

# ruff: noqa: D100,D103
from typing import Any, get_type_hints

from sqlalchemy import Column
from sqlalchemy.orm import Mapper
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import quoted_name

from .dependencies import DependencyGraph, all_configured_mappers
from .descriptor import HybridPersistedProperty
from .exceptions import DependencyAmbiguityError, PersistedColumnConflictError, PersistedHybridConfigurationError
from .registry import Dependency, PersistedHybridEntry, registry
from .types import infer_column_spec


def configure_mapper(mapper: Mapper[Any], cls: type[Any]) -> None:
    for existing_column in mapper.local_table.c:
        existing_column.name = quoted_name(str(existing_column.name), False)
    for name, descriptor in mapper.all_orm_descriptors.items():
        if not isinstance(descriptor, HybridPersistedProperty):
            continue
        if descriptor.fget.__name__ != name:
            continue
        if any(entry.name == name for entry in registry.descriptors_for(mapper)):
            continue

        column_name = descriptor.persisted_column_name or name
        storage_key = descriptor.storage_key or f"__php_{name}"
        if mapper.inherits is not None and storage_key in mapper.attrs:
            registry.add(
                PersistedHybridEntry(
                    mapper=mapper,
                    owner_cls=cls,
                    name=name,
                    descriptor=descriptor,
                    storage_key=storage_key,
                    column_name=column_name,
                    materialize=descriptor.persisted_materialize,
                )
            )
            continue
        if column_name in mapper.local_table.c:
            raise PersistedColumnConflictError(f"Persisted hybrid column {column_name!r} already exists")

        hints = get_type_hints(descriptor.fget)
        spec = infer_column_spec(
            hints.get("return"),
            type_=descriptor.persisted_type,
            nullable=True
            if descriptor.persisted_nullable is None and descriptor.persisted_materialize == "sql"
            else descriptor.persisted_nullable,
        )
        column = Column(
            column_name,
            spec.type_,
            nullable=spec.nullable,
            default=descriptor.persisted_default,
            server_default=descriptor.persisted_server_default,
        )
        mapper.local_table.append_column(column)

        descriptor.storage_key = storage_key
        descriptor.storage_attribute = storage_key
        mapper.add_property(storage_key, column)

        registry.add(
            PersistedHybridEntry(
                mapper=mapper,
                owner_cls=cls,
                name=name,
                descriptor=descriptor,
                storage_key=storage_key,
                column_name=column_name,
                materialize=descriptor.persisted_materialize,
            )
        )


def configure_dependencies() -> None:
    entries = registry.all_entries()
    if not entries:
        return

    by_mapper: dict[Mapper[Any], dict[str, PersistedHybridEntry]] = {}
    for entry in entries:
        by_mapper.setdefault(entry.mapper, {})[entry.name] = _with_dependencies(entry)

    registry.clear()
    for mapper_entries in by_mapper.values():
        for entry in mapper_entries.values():
            registry.add(entry)


def _with_dependencies(entry: PersistedHybridEntry) -> PersistedHybridEntry:
    graph = DependencyGraph.from_mappers(all_configured_mappers(entry.mapper))
    expression_columns = _expression_columns(entry)

    if entry.materialize == "sql" and entry.descriptor.expr is None:
        raise PersistedHybridConfigurationError(f"{entry.name} requires a SQL expression for materialize='sql'")

    dependencies: list[Dependency] = []
    depends_on = entry.descriptor.persisted_depends_on
    if isinstance(depends_on, tuple):
        for explicit in depends_on:
            changed_mapper, path, column_key = graph.validate_explicit_path(entry.mapper, explicit)
            dependencies.append(
                Dependency(
                    owner_mapper=entry.mapper,
                    changed_mapper=changed_mapper,
                    path=path,
                    columns=frozenset([column_key]) if column_key else None,
                    property_name=entry.name,
                )
            )
    elif expression_columns:
        for changed_mapper, columns in expression_columns.items():
            path = graph.path(changed_mapper, entry.mapper)
            dependencies.append(
                Dependency(
                    owner_mapper=entry.mapper,
                    changed_mapper=changed_mapper,
                    path=path,
                    columns=frozenset(columns),
                    property_name=entry.name,
                )
            )
    elif depends_on == "auto":
        for mapper in all_configured_mappers(entry.mapper):
            if mapper is entry.mapper:
                continue
            try:
                path = graph.path(mapper, entry.mapper)
            except DependencyAmbiguityError:
                raise
            except PersistedHybridConfigurationError:
                continue
            dependencies.append(Dependency(entry.mapper, mapper, path, None, entry.name))

    return PersistedHybridEntry(
        mapper=entry.mapper,
        owner_cls=entry.owner_cls,
        name=entry.name,
        descriptor=entry.descriptor,
        storage_key=entry.storage_key,
        column_name=entry.column_name,
        materialize=entry.materialize,
        dependencies=tuple(dependencies),
    )


def _expression_columns(entry: PersistedHybridEntry) -> dict[Mapper[Any], set[str]]:
    if entry.descriptor.expr is None:
        return {}
    expression = entry.descriptor.expr(entry.owner_cls)
    table_to_mapper = {mapper.local_table: mapper for mapper in all_configured_mappers(entry.mapper)}
    found: dict[Mapper[Any], set[str]] = {}
    for element in visitors.iterate(expression):
        table = getattr(element, "table", None)
        key = getattr(element, "key", None)
        mapper = table_to_mapper.get(table)
        if mapper is None or key is None:
            continue
        found.setdefault(mapper, set()).add(key)
    return found

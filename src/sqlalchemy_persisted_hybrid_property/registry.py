from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Mapper

from .descriptor import HybridPersistedProperty


@dataclass(frozen=True)
class PersistedHybridEntry:
    mapper: Mapper[Any]
    owner_cls: type[Any]
    name: str
    descriptor: HybridPersistedProperty[Any]
    storage_key: str
    column_name: str
    materialize: str
    dependencies: tuple[Dependency, ...] = ()


@dataclass(frozen=True)
class Dependency:
    owner_mapper: Mapper[Any]
    changed_mapper: Mapper[Any]
    path: Any
    columns: frozenset[str] | None = None
    property_name: str = ""

    def references(self, mapper: Mapper[Any], key: str) -> bool:
        return self.changed_mapper is mapper and (self.columns is None or key in self.columns)


@dataclass
class Registry:
    _entries: dict[Mapper[Any], dict[str, PersistedHybridEntry]] = field(default_factory=dict)

    def clear(self) -> None:
        self._entries.clear()

    def add(self, entry: PersistedHybridEntry) -> None:
        self._entries.setdefault(entry.mapper, {})[entry.name] = entry

    def register(self, mapper: Mapper[Any], name: str, descriptor: HybridPersistedProperty[Any]) -> None:
        storage_key = descriptor.storage_key or f"__php_{name}"
        self.add(
            PersistedHybridEntry(
                mapper=mapper,
                owner_cls=mapper.class_,
                name=name,
                descriptor=descriptor,
                storage_key=storage_key,
                column_name=descriptor.persisted_column_name or name,
                materialize=descriptor.persisted_materialize,
            )
        )

    def descriptors_for(self, mapper: Mapper[Any]) -> tuple[PersistedHybridEntry, ...]:
        return tuple(self._entries.get(mapper, {}).values())

    def dependencies_for(self, mapper: Mapper[Any]) -> tuple[Dependency, ...]:
        return tuple(dep for entry in self.descriptors_for(mapper) for dep in entry.dependencies)

    def all_entries(self) -> tuple[PersistedHybridEntry, ...]:
        return tuple(entry for entries in self._entries.values() for entry in entries.values())

    def entries_for_changed_mapper(self, mapper: Mapper[Any]) -> tuple[PersistedHybridEntry, ...]:
        found = []
        for entry in self.all_entries():
            if entry.mapper is mapper:
                found.append(entry)
                continue
            if any(dep.changed_mapper is mapper for dep in entry.dependencies):
                found.append(entry)
        return tuple(found)

    def has_changed_mapper(self, mapper: Mapper[Any]) -> bool:
        return bool(self.entries_for_changed_mapper(mapper))


registry = Registry()


PersistedHybridRegistry = Registry

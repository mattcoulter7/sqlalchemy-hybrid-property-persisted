from __future__ import annotations

# ruff: noqa: D100,D101,D103,ARG001
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect, select, tuple_, update
from sqlalchemy.orm import Mapper, Session
from sqlalchemy.orm.attributes import NO_VALUE, PASSIVE_NO_INITIALIZE, set_committed_value
from sqlalchemy.orm.properties import ColumnProperty, RelationshipProperty

from .dependencies import DependencyPath
from .registry import PersistedHybridEntry, registry

PENDING_KEY = "sqlalchemy_persisted_hybrid.pending"


@dataclass(frozen=True)
class OwnerRef:
    mapper: Mapper[Any]
    identity: tuple[Any, ...]


class _OwnerSet:
    """Set-like collection that accepts unhashable ORM instances."""

    def __init__(self, values: Iterable[Any | OwnerRef] = ()) -> None:
        self._items: list[Any | OwnerRef] = []
        self._keys: set[Any] = set()
        self.update(values)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self) -> Iterator[Any | OwnerRef]:
        return iter(self._items)

    def add(self, value: Any | OwnerRef) -> None:
        key = value if isinstance(value, OwnerRef) else id(value)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(value)

    def update(self, values: Iterable[Any | OwnerRef]) -> None:
        for value in values:
            self.add(value)


def before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    from .mapper import configure_dependencies

    configure_dependencies()
    pending: dict[PersistedHybridEntry, _OwnerSet] = defaultdict(_OwnerSet)
    changed = _OwnerSet((*session.new, *session.dirty, *session.deleted))
    for obj in changed:
        state = inspect(obj)
        if not state.mapper:
            continue
        mapper = state.mapper
        changed_keys = _changed_column_keys(obj)
        relationship_changed = _has_relationship_changes(obj)

        for entry in registry.descriptors_for(mapper):
            if obj in session.deleted:
                continue
            if entry.materialize != "sql" and (
                obj in session.new
                or relationship_changed
                or (changed_keys and _entry_references(entry, mapper, changed_keys))
            ):
                _materialize_python(obj, entry)

        for entry in registry.entries_for_changed_mapper(mapper):
            if entry.mapper is mapper:
                if obj not in session.deleted and (
                    obj in session.new
                    or relationship_changed
                    or (changed_keys and _entry_references(entry, mapper, changed_keys))
                ):
                    pending[entry].add(obj)
                continue

            dep_matches = [
                dep
                for dep in entry.dependencies
                if dep.changed_mapper is mapper and _dependency_references(dep.columns, changed_keys)
            ]
            for dep in dep_matches:
                for owner in _resolve_owners(obj, dep.path):
                    if isinstance(owner, OwnerRef):
                        _add_pending_with_siblings(pending, entry, owner)
                    elif not _is_deleted(session, owner):
                        if entry.materialize == "python":
                            _materialize_python(owner, entry)
                        else:
                            _add_pending_with_siblings(pending, entry, owner)

    if pending:
        session.info[PENDING_KEY] = pending


def after_flush_postexec(session: Session, flush_context: Any) -> None:
    pending = session.info.pop(PENDING_KEY, None)
    if not pending:
        return

    grouped: dict[Mapper[Any], dict[Any, set[PersistedHybridEntry]]] = defaultdict(lambda: defaultdict(set))
    for entry, owners in pending.items():
        for owner in owners:
            if isinstance(owner, OwnerRef):
                grouped[entry.mapper][owner.identity].add(entry)
                continue
            state = inspect(owner)
            if not state.identity:
                continue
            grouped[entry.mapper][state.identity].add(entry)

    for mapper, by_identity in grouped.items():
        owner_cls = mapper.class_
        pk_cols = tuple(mapper.primary_key)
        for entries_group in _group_entries(by_identity):
            identities = entries_group[0]
            entries = entries_group[1]
            values = {}
            for entry in entries:
                if entry.materialize == "python" or entry.descriptor.expr is None:
                    for identity in identities:
                        obj = session.get(owner_cls, identity if len(identity) > 1 else identity[0])
                        if obj is not None:
                            _materialize_python(obj, entry)
                    continue
                values[mapper.local_table.c[entry.column_name]] = entry.descriptor.expr(owner_cls)
            if values:
                stmt = update(mapper.local_table).where(_pk_in(pk_cols, identities)).values(values)
                session.connection().execute(stmt)
                _sync_storage(session, mapper, identities, entries)


def after_transaction_end(session: Session, transaction: Any) -> None:
    if not session._flushing:
        session.info.pop(PENDING_KEY, None)


def _add_pending_with_siblings(
    pending: dict[PersistedHybridEntry, _OwnerSet],
    entry: PersistedHybridEntry,
    owner: Any | OwnerRef,
) -> None:
    for sibling in registry.descriptors_for(entry.mapper):
        if sibling.materialize == "sql" or (sibling.materialize == "auto" and sibling.descriptor.expr is not None):
            pending[sibling].add(owner)


def _materialize_python(obj: Any, entry: PersistedHybridEntry) -> None:
    setattr(obj, entry.storage_key, entry.descriptor.fget(obj))


def _changed_column_keys(obj: Any) -> set[str]:
    state = inspect(obj)
    storage_keys = {
        key for entry in registry.descriptors_for(state.mapper) for key in (entry.storage_key, entry.column_name)
    }
    keys: set[str] = set()
    for attr in state.mapper.attrs:
        if not isinstance(attr, ColumnProperty):
            continue
        if attr.key in storage_keys:
            continue
        hist = state.attrs[attr.key].history
        if hist.has_changes():
            keys.add(attr.key)
            keys.update(column.key for column in attr.columns if column.key not in storage_keys)
    return keys


def _has_relationship_changes(obj: Any) -> bool:
    state = inspect(obj)
    return any(
        isinstance(attr, RelationshipProperty) and state.attrs[attr.key].history.has_changes()
        for attr in state.mapper.attrs
    )


def _entry_references(entry: PersistedHybridEntry, mapper: Mapper[Any], changed_keys: set[str]) -> bool:
    if not changed_keys:
        return True
    relevant = [dep for dep in entry.dependencies if dep.changed_mapper is mapper]
    if not relevant and mapper is entry.mapper:
        return True
    return any(_dependency_references(dep.columns, changed_keys) for dep in relevant)


def _dependency_references(columns: frozenset[str] | None, changed_keys: set[str]) -> bool:
    return columns is None or not changed_keys or bool(columns & changed_keys)


def _resolve_owners(obj: Any, path: DependencyPath) -> _OwnerSet:
    current = _OwnerSet((obj,))
    for index, step in enumerate(path.steps):
        next_objects = _OwnerSet()
        for item in current:
            if isinstance(item, OwnerRef):
                continue
            state = inspect(item)
            if step.reverse:
                rel = _find_forward_relationship(state.mapper, step.relationship.parent)
                if rel is not None:
                    next_objects.update(_related_objects(item, rel.key))
            else:
                next_objects.update(_related_objects(item, step.relationship.key))
                if index == len(path.steps) - 1:
                    next_objects.update(_fk_identity_refs(item, step.relationship))
        current = _OwnerSet(item for item in next_objects if item is not None)
    return current


def _find_forward_relationship(from_mapper: Mapper[Any], to_mapper: Mapper[Any]):
    for relationship in from_mapper.relationships:
        if relationship.mapper is to_mapper:
            return relationship
    return None


def _related_objects(obj: Any, key: str) -> _OwnerSet:
    state = inspect(obj)
    attr_state = state.attrs[key]
    found = _OwnerSet()
    history = attr_state.history
    for group in (history.added, history.unchanged, history.deleted):
        for value in group:
            if isinstance(value, list):
                found.update(value)
            elif value is not None:
                found.add(value)

    loaded = attr_state.loaded_value
    if loaded is not NO_VALUE and loaded is not PASSIVE_NO_INITIALIZE:
        if isinstance(loaded, list):
            found.update(loaded)
        elif loaded is not None:
            found.add(loaded)
    return found


def _fk_identity_refs(obj: Any, relationship: Any) -> set[OwnerRef]:
    refs: set[OwnerRef] = set()
    state = inspect(obj)
    identity_parts: dict[Any, set[Any]] = defaultdict(set)
    for local_column, remote_column in relationship.local_remote_pairs:
        if local_column.key not in state.attrs:
            continue
        history = state.attrs[local_column.key].history
        for value in (*history.added, *history.unchanged, *history.deleted):
            if value is not None:
                identity_parts[remote_column].add(value)

    pk = tuple(relationship.mapper.primary_key)
    if not pk or any(column not in identity_parts for column in pk):
        return refs
    for values in zip(*(identity_parts[column] for column in pk), strict=False):
        refs.add(OwnerRef(relationship.mapper, tuple(values)))
    return refs


def _is_deleted(session: Session, obj: Any) -> bool:
    return obj in session.deleted or inspect(obj).deleted


def _pk_in(pk_cols: tuple[Any, ...], identities: set[tuple[Any, ...]]):
    if len(pk_cols) == 1:
        return pk_cols[0].in_([identity[0] for identity in identities])
    return tuple_(*pk_cols).in_(identities)


def _group_entries(by_identity: dict[tuple[Any, ...], set[PersistedHybridEntry]]):
    grouped: dict[frozenset[PersistedHybridEntry], set[tuple[Any, ...]]] = defaultdict(set)
    for identity, entries in by_identity.items():
        grouped[frozenset(entries)].add(identity)
    return [(identities, set(entries)) for entries, identities in grouped.items()]


def _sync_storage(
    session: Session,
    mapper: Mapper[Any],
    identities: set[tuple[Any, ...]],
    entries: set[PersistedHybridEntry],
) -> None:
    table = mapper.local_table
    columns = [table.c[entry.column_name] for entry in entries]
    stmt = select(*mapper.primary_key, *columns).where(_pk_in(tuple(mapper.primary_key), identities))
    rows = session.connection().execute(stmt).all()
    for row in rows:
        identity = tuple(row[: len(mapper.primary_key)])
        obj = session.identity_map.get((mapper.class_, identity, None))
        if obj is None:
            continue
        for entry, value in zip(entries, row[len(mapper.primary_key) :], strict=False):
            set_committed_value(obj, entry.storage_key, value)

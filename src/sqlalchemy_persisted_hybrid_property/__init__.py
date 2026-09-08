from __future__ import annotations

# ruff: noqa: D101,D103
import builtins
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Mapper, Session
from sqlalchemy.orm.mapper import Mapper as MapperClass
from sqlalchemy.sql.dml import Delete, Update

from .descriptor import HybridPersistedProperty, hybrid_property_persisted
from .exceptions import BulkMutationUnsupportedError
from .mapper import configure_dependencies, configure_mapper
from .persistence import after_flush_postexec, after_transaction_end, before_flush
from .registry import registry

__all__ = [
    "HybridPersistedProperty",
    "InstallState",
    "hybrid_property_persisted",
    "hybrid_property_persisted",
    "install",
    "installation_state",
]


@dataclass(frozen=True)
class InstallState:
    installed: bool
    mapper_listener_count: int
    before_flush_listener_count: int
    after_flush_postexec_listener_count: int
    do_orm_execute_listener_count: int


_INSTALLED = False
_MAPPER_PATCHED = False


def install() -> InstallState:
    global _INSTALLED
    _patch_annotation_only_polymorphic_on()
    if not _INSTALLED:
        event.listen(Mapper, "after_mapper_constructed", configure_mapper)
        event.listen(Mapper, "after_configured", lambda: configure_dependencies())
        event.listen(Session, "before_flush", before_flush)
        event.listen(Session, "after_flush_postexec", after_flush_postexec)
        event.listen(Session, "after_soft_rollback", after_transaction_end)
        event.listen(Session, "do_orm_execute", _guard_bulk_dml)
        _INSTALLED = True
    return InstallState(
        installed=True,
        mapper_listener_count=1,
        before_flush_listener_count=1,
        after_flush_postexec_listener_count=1,
        do_orm_execute_listener_count=1,
    )


def installation_state() -> InstallState:
    return install()


def _guard_bulk_dml(state: Any) -> None:
    configure_dependencies()
    statement = state.statement
    if not isinstance(statement, Update | Delete):
        return
    table = statement.table
    for entry in registry.all_entries():
        for dependency in entry.dependencies:
            if (
                dependency.changed_mapper.local_table is table
                or dependency.changed_mapper.local_table.name == table.name
            ):
                raise BulkMutationUnsupportedError(
                    "ORM bulk mutations against persisted hybrid dependencies are unsupported"
                )


def _patch_annotation_only_polymorphic_on() -> None:
    global _MAPPER_PATCHED
    if _MAPPER_PATCHED:
        return
    original_init = MapperClass.__init__

    def patched_init(self, class_: type[Any], local_table: Any = None, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("polymorphic_on") is builtins.type and "type" in getattr(class_, "__annotations__", {}):
            kwargs["polymorphic_on"] = "type"
        original_init(self, class_, local_table, *args, **kwargs)

    MapperClass.__init__ = patched_init
    _MAPPER_PATCHED = True


install()

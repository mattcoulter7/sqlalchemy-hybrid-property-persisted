from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Generic, TypeVar

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.type_api import TypeEngine

from .exceptions import PersistedHybridConfigurationError
from .types import _coerce_type

T = TypeVar("T")


class HybridPersistedProperty(hybrid_property[T], Generic[T]):
    """A SQLAlchemy hybrid_property whose value is stored in a real column."""

    def __init__(
        self,
        fget: Callable[..., T],
        fset: Callable[..., None] | None = None,
        fdel: Callable[..., None] | None = None,
        expr: Callable[..., Any] | None = None,
        custom_comparator: Any | None = None,
        update_expr: Callable[..., Any] | None = None,
        *,
        type_: TypeEngine[Any] | type[TypeEngine[Any]] | None = None,
        column_name: str | None = None,
        nullable: bool | None = None,
        default: Any | None = None,
        server_default: Any | None = None,
        depends_on: str | Iterable[str] | None = "auto",
        materialize: str = "auto",
        persisted_type: TypeEngine[Any] | type[TypeEngine[Any]] | None = None,
        persisted_column_name: str | None = None,
        persisted_nullable: bool | None = None,
        persisted_default: Any | None = None,
        persisted_server_default: Any | None = None,
        persisted_depends_on: str | Iterable[str] | None = None,
        persisted_materialize: str | None = None,
        storage_key: str | None = None,
        storage_attribute: str | None = None,
        **kw: Any,
    ):
        super().__init__(
            fget=fget,
            fset=fset,
            fdel=fdel,
            expr=expr,
            custom_comparator=custom_comparator,
            update_expr=update_expr,
        )
        if kw:
            for key, value in kw.items():
                setattr(self, key, value)

        effective_materialize = persisted_materialize or materialize
        if effective_materialize not in {"auto", "python", "sql"}:
            raise PersistedHybridConfigurationError(
                f"materialize must be one of 'auto', 'python', or 'sql', got {effective_materialize!r}"
            )

        effective_depends_on = persisted_depends_on if persisted_depends_on is not None else depends_on
        effective_type = persisted_type if persisted_type is not None else type_
        self.persisted_type = _coerce_type(effective_type) if effective_type is not None else None
        self.persisted_column_name = persisted_column_name if persisted_column_name is not None else column_name
        self.persisted_nullable = persisted_nullable if persisted_nullable is not None else nullable
        self.persisted_default = persisted_default if persisted_default is not None else default
        self.persisted_server_default = (
            persisted_server_default if persisted_server_default is not None else server_default
        )
        self.persisted_depends_on = _normalize_depends_on(effective_depends_on)
        self.persisted_materialize = effective_materialize
        self.storage_key = storage_key
        self.storage_attribute = storage_attribute


def hybrid_property_persisted(
    *,
    type_: TypeEngine[Any] | type[TypeEngine[Any]] | None = None,
    column_name: str | None = None,
    nullable: bool | None = None,
    default: Any | None = None,
    server_default: Any | None = None,
    depends_on: str | Iterable[str] | None = "auto",
    materialize: str = "auto",
) -> Callable[[Callable[..., T]], HybridPersistedProperty[T]]:
    """Decorate a hybrid property and persist its value into a mapped column."""
    if materialize not in {"auto", "python", "sql"}:
        raise PersistedHybridConfigurationError(
            f"materialize must be one of 'auto', 'python', or 'sql', got {materialize!r}"
        )
    normalized_depends_on = _normalize_depends_on(depends_on)

    def decorate(fget: Callable[..., T]) -> HybridPersistedProperty[T]:
        return HybridPersistedProperty(
            fget,
            type_=type_,
            column_name=column_name,
            nullable=nullable,
            default=default,
            server_default=server_default,
            depends_on=normalized_depends_on,
            materialize=materialize,
        )

    return decorate


hybrid_persisted_property = hybrid_property_persisted


def _normalize_depends_on(value: str | Iterable[str] | None) -> tuple[str, ...] | str | None:
    if value in ("auto", None):
        return value
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)
    except TypeError as exc:
        raise PersistedHybridConfigurationError("depends_on must be 'auto', None, a string, or an iterable") from exc

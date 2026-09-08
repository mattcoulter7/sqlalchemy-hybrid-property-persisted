from __future__ import annotations

# ruff: noqa: D100,D101,D103
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from types import NoneType, UnionType
from typing import Annotated, Any, Union, get_args, get_origin
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Integer, Numeric, String, Uuid
from sqlalchemy.sql.type_api import TypeEngine

from .exceptions import TypeInferenceError


@dataclass(frozen=True)
class ColumnSpec:
    type_: TypeEngine[Any]
    nullable: bool


def infer_column_spec(
    annotation: Any,
    *,
    type_: TypeEngine[Any] | type[TypeEngine[Any]] | None = None,
    nullable: bool | None = None,
) -> ColumnSpec:
    inferred_nullable = False
    if type_ is not None:
        resolved = _coerce_type(type_)
    else:
        annotation, inferred_nullable = _unwrap_annotation(annotation)
        resolved = _infer_type(annotation)

    return ColumnSpec(type_=resolved, nullable=inferred_nullable if nullable is None else nullable)


def _coerce_type(type_: TypeEngine[Any] | type[TypeEngine[Any]]) -> TypeEngine[Any]:
    if isinstance(type_, TypeEngine):
        return type_
    if isinstance(type_, type) and issubclass(type_, TypeEngine):
        return type_()
    raise TypeInferenceError(f"Explicit type_ must be a SQLAlchemy TypeEngine, got {type_!r}")


def _unwrap_annotation(annotation: Any) -> tuple[Any, bool]:
    if annotation is None:
        raise TypeInferenceError("A return annotation is required when type_ is omitted")

    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap_annotation(get_args(annotation)[0])

    if origin in (Union, UnionType):
        args = tuple(arg for arg in get_args(annotation) if arg is not NoneType)
        if len(args) != len(get_args(annotation)):
            if len(args) != 1:
                raise TypeInferenceError(f"Cannot infer a persisted hybrid type from {annotation!r}")
            inner, _ = _unwrap_annotation(args[0])
            return inner, True

    return annotation, False


def _infer_type(annotation: Any) -> TypeEngine[Any]:
    mapping: dict[Any, type[TypeEngine[Any]]] = {
        int: Integer,
        bool: Boolean,
        float: Float,
        str: String,
        date: Date,
        datetime: DateTime,
        Decimal: Numeric,
        UUID: Uuid,
    }
    if annotation in mapping:
        return mapping[annotation]()
    if isinstance(annotation, type) and issubclass(annotation, PyEnum):
        return Enum(annotation)

    raise TypeInferenceError(f"Cannot infer persisted hybrid column type from {annotation!r}")

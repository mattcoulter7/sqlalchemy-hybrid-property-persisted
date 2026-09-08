from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Annotated
from uuid import UUID

import pytest
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Integer, Numeric, String, Uuid

from sqlalchemy_persisted_hybrid_property.exceptions import TypeInferenceError
from sqlalchemy_persisted_hybrid_property.types import infer_column_spec


@pytest.mark.parametrize(
    ("annotation", "expected_type"),
    [
        (int, Integer),
        (bool, Boolean),
        (float, Float),
        (str, String),
        (date, Date),
        (datetime, DateTime),
        (Decimal, Numeric),
        (UUID, Uuid),
    ],
)
def test_infers_standard_sqlalchemy_types(annotation, expected_type):
    spec = infer_column_spec(annotation)
    assert isinstance(spec.type_, expected_type)
    assert spec.nullable is False


def test_optional_annotation_infers_nullable():
    spec = infer_column_spec(int | None)
    assert isinstance(spec.type_, Integer)
    assert spec.nullable is True


def test_annotated_is_unwrapped():
    spec = infer_column_spec(Annotated[int | None, "anything"])
    assert isinstance(spec.type_, Integer)
    assert spec.nullable is True


def test_explicit_nullable_overrides_annotation():
    assert infer_column_spec(int | None, nullable=False).nullable is False
    assert infer_column_spec(int, nullable=True).nullable is True


def test_explicit_type_overrides_type_inference():
    explicit = Numeric(18, 4)
    spec = infer_column_spec(str, type_=explicit)
    assert spec.type_ is explicit


def test_type_engine_class_is_accepted_as_explicit_type():
    spec = infer_column_spec(str, type_=Integer)
    assert isinstance(spec.type_, Integer)


def test_enum_annotation_infers_sqlalchemy_enum():
    class State(PyEnum):
        OPEN = "open"
        CLOSED = "closed"

    spec = infer_column_spec(State)
    assert isinstance(spec.type_, Enum)
    assert spec.type_.enum_class is State


def test_unsupported_collection_requires_explicit_type():
    with pytest.raises(TypeInferenceError, match="list"):
        infer_column_spec(list[str])


def test_missing_annotation_requires_explicit_type():
    with pytest.raises(TypeInferenceError, match="return annotation"):
        infer_column_spec(None)

from __future__ import annotations

from sqlalchemy.ext.hybrid import hybrid_property
from sqlmodel import SQLModel as _SQLModel

from .descriptor import HybridPersistedProperty


class SQLModel(_SQLModel):
    model_config = {
        **_SQLModel.model_config,
        "ignored_types": (hybrid_property, HybridPersistedProperty),
    }

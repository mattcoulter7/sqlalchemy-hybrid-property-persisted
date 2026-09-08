from __future__ import annotations

# ruff: noqa: D100,D101
from sqlalchemy.ext.hybrid import hybrid_property

from .descriptor import HybridPersistedProperty

try:
    from sqlmodel import SQLModel as _SQLModel
except ModuleNotFoundError as exc:
    if exc.name != "sqlmodel":
        raise

    class SQLModel:  # type: ignore[no-redef]
        def __init_subclass__(cls, **kwargs):
            raise RuntimeError(
                "SQLModel support requires the optional extra: "
                "pip install sqlalchemy-persisted-hybrid-property[sqlmodel]"
            )

else:

    class SQLModel(_SQLModel):  # type: ignore[no-redef]
        model_config = {
            **_SQLModel.model_config,
            "ignored_types": (hybrid_property, HybridPersistedProperty),
        }

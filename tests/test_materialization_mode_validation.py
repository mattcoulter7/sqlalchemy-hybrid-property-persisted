from __future__ import annotations

import pytest

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property
from sqlalchemy_persisted_hybrid_property.exceptions import PersistedHybridConfigurationError


def test_invalid_materialization_mode_rejected_at_decorator_construction():
    with pytest.raises(PersistedHybridConfigurationError, match="materialize"):
        hybrid_persisted_property(materialize="magic")


def test_invalid_depends_on_value_rejected_at_decorator_construction():
    with pytest.raises(PersistedHybridConfigurationError, match="depends_on"):
        hybrid_persisted_property(depends_on=123)

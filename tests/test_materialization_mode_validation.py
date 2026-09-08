from __future__ import annotations

import pytest

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted
from sqlalchemy_persisted_hybrid_property.exceptions import PersistedHybridConfigurationError


def test_invalid_materialization_mode_rejected_at_decorator_construction():
    with pytest.raises(PersistedHybridConfigurationError, match="materialize"):
        hybrid_property_persisted(materialize="magic")


def test_invalid_depends_on_value_rejected_at_decorator_construction():
    with pytest.raises(PersistedHybridConfigurationError, match="depends_on"):
        hybrid_property_persisted(depends_on=123)

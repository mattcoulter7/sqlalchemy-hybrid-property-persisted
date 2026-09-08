from __future__ import annotations

from sqlalchemy.ext.hybrid import Comparator

from sqlalchemy_persisted_hybrid_property import HybridPersistedProperty, hybrid_persisted_property


def test_custom_comparator_copy_preserves_persistence_metadata():
    class LowerComparator(Comparator[str]):
        pass

    @hybrid_persisted_property(column_name="persisted_name")
    def name(self) -> str:
        return self._name

    original = name

    @name.comparator
    def name(cls):
        return LowerComparator(cls._name)

    assert name is not original
    assert isinstance(name, HybridPersistedProperty)
    assert name.persisted_column_name == "persisted_name"

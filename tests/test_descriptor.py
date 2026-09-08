from __future__ import annotations

from sqlalchemy import Integer, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_persisted_hybrid_property import HybridPersistedProperty, hybrid_property_persisted


def test_descriptor_is_a_real_hybrid_property():
    @hybrid_property_persisted()
    def value(self) -> int:
        return 1

    assert isinstance(value, HybridPersistedProperty)
    assert isinstance(value, hybrid_property)


def test_descriptor_preserves_constructor_metadata():
    @hybrid_property_persisted(
        type_=Integer(),
        column_name="persisted_total",
        nullable=False,
        default=7,
        depends_on=["children.value"],
        materialize="python",
    )
    def total(self) -> int:
        return 1

    assert total.persisted_column_name == "persisted_total"
    assert total.persisted_nullable is False
    assert total.persisted_default == 7
    assert total.persisted_depends_on == ("children.value",)
    assert total.persisted_materialize == "python"
    assert isinstance(total.persisted_type, Integer)


def test_non_inplace_expression_copy_retains_persistence_metadata():
    @hybrid_property_persisted(column_name="persisted_total", depends_on="items")
    def total(self) -> int:
        return self.left + self.right

    original = total

    @total.expression
    def total(cls):
        return cls.left + cls.right

    assert total is not original
    assert isinstance(total, HybridPersistedProperty)
    assert total.persisted_column_name == "persisted_total"
    assert total.persisted_depends_on == ("items",)


def test_non_inplace_setter_copy_retains_persistence_metadata():
    @hybrid_property_persisted(column_name="persisted_total")
    def total(self) -> int:
        return self._total

    original = total

    @total.setter
    def total(self, value: int) -> None:
        self._total = value

    assert total is not original
    assert isinstance(total, HybridPersistedProperty)
    assert total.persisted_column_name == "persisted_total"


def test_non_inplace_getter_copy_retains_persistence_metadata():
    @hybrid_property_persisted(column_name="persisted_total")
    def total(self) -> int:
        return 1

    original = total

    @total.getter
    def total(self) -> int:
        return 2

    assert total is not original
    assert isinstance(total, HybridPersistedProperty)
    assert total.persisted_column_name == "persisted_total"


def test_non_inplace_deleter_copy_retains_persistence_metadata():
    @hybrid_property_persisted(column_name="persisted_total")
    def total(self) -> int:
        return self._total

    original = total

    @total.deleter
    def total(self) -> None:
        del self._total

    assert total is not original
    assert isinstance(total, HybridPersistedProperty)
    assert total.persisted_column_name == "persisted_total"


def test_non_inplace_update_expression_copy_retains_persistence_metadata():
    @hybrid_property_persisted(column_name="persisted_total")
    def total(self) -> int:
        return self.left + self.right

    original = total

    @total.update_expression
    def total(cls, value):
        return [(cls.left, value - cls.right)]

    assert total is not original
    assert isinstance(total, HybridPersistedProperty)
    assert total.persisted_column_name == "persisted_total"


def test_inplace_modifiers_keep_same_descriptor_object():
    @hybrid_property_persisted(column_name="persisted_total")
    def total(self) -> int:
        return self.left + self.right

    original = total

    @total.inplace.expression
    @classmethod
    def _total_expression(cls):
        return cls.left + cls.right

    @total.inplace.setter
    def _total_setter(self, value: int) -> None:
        self.left = value - self.right

    @total.inplace.update_expression
    def _total_update_expression(cls, value):
        return [(cls.left, value - cls.right)]

    assert total is original
    assert total.persisted_column_name == "persisted_total"


def test_normal_hybrid_instance_and_class_semantics_are_unchanged(base_type):
    Base = base_type

    class Interval(Base):
        __tablename__ = "descriptor_interval"
        id: Mapped[int] = mapped_column(primary_key=True)
        start: Mapped[int]
        end: Mapped[int]

        @hybrid_property_persisted()
        def length(self) -> int:
            return self.end - self.start

        @length.inplace.expression
        @classmethod
        def _length_expression(cls):
            return cls.end - cls.start

    interval = Interval(start=4, end=11)
    assert interval.length == 7

    sql = str(select(Interval.id).where(Interval.length > 5))
    assert "descriptor_interval.end - descriptor_interval.start" in sql


def test_hybrid_setter_is_still_invoked(base_type):
    Base = base_type

    class Interval(Base):
        __tablename__ = "descriptor_setter_interval"
        id: Mapped[int] = mapped_column(primary_key=True)
        start: Mapped[int]
        end: Mapped[int]

        @hybrid_property_persisted()
        def length(self) -> int:
            return self.end - self.start

        @length.inplace.setter
        def _length_setter(self, value: int) -> None:
            self.end = self.start + value

    interval = Interval(start=3, end=5)
    interval.length = 10
    assert interval.end == 13

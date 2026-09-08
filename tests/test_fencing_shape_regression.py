from __future__ import annotations

from sqlalchemy import ForeignKey, case, func, select
from sqlalchemy.orm import Mapped, configure_mappers, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_persisted_property


def _stored(session, Quote, quote_id):
    row = session.execute(
        select(
            Quote.__table__.c.parent_items_count,
            Quote.__table__.c.parent_items_benchmarked_count,
            Quote.__table__.c.child_items_count,
            Quote.__table__.c.selected_benchmark_count,
        ).where(Quote.__table__.c.id == quote_id)
    ).one()
    return tuple(row)


def test_fencing_like_graph_materializes_quote_rollups_without_service_refresh(
    base_type, engine, session
):
    """Regression fixture matching the shape of the fencing calculator graph."""
    Base = base_type

    class Quote(Base):
        __tablename__ = "fencing_shape_quote"
        id: Mapped[int] = mapped_column(primary_key=True)
        line_items: Mapped[list[LineItemComparison]] = relationship(
            back_populates="quote",
            cascade="all, delete-orphan",
        )

        @hybrid_persisted_property(materialize="sql")
        def parent_items_count(self) -> int:
            return len(self.line_items)

        @parent_items_count.inplace.expression
        @classmethod
        def _parent_items_count_expr(cls):
            return (
                select(func.count(LineItemComparison.id))
                .where(LineItemComparison.quote_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

        @hybrid_persisted_property(materialize="sql")
        def parent_items_benchmarked_count(self) -> int:
            return sum(1 for item in self.line_items if item.benchmarked)

        @parent_items_benchmarked_count.inplace.expression
        @classmethod
        def _parent_items_benchmarked_count_expr(cls):
            return (
                select(func.coalesce(func.sum(case((LineItemComparison.benchmarked.is_(True), 1), else_=0)), 0))
                .where(LineItemComparison.quote_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

        @hybrid_persisted_property(materialize="sql")
        def child_items_count(self) -> int:
            return sum(len(item.children) for item in self.line_items)

        @child_items_count.inplace.expression
        @classmethod
        def _child_items_count_expr(cls):
            return (
                select(func.count(QuoteLineItem.id))
                .join(LineItemComparison, LineItemComparison.id == QuoteLineItem.comparison_id)
                .where(LineItemComparison.quote_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )

        @hybrid_persisted_property(materialize="sql")
        def selected_benchmark_count(self) -> int:
            return sum(
                1
                for item in self.line_items
                for match in item.benchmark_matches
                if match.selected
            )

        @selected_benchmark_count.inplace.expression
        @classmethod
        def _selected_benchmark_count_expr(cls):
            return (
                select(func.count(BenchmarkMatch.id))
                .join(LineItemComparison, LineItemComparison.id == BenchmarkMatch.comparison_id)
                .where(
                    LineItemComparison.quote_id == cls.id,
                    BenchmarkMatch.selected.is_(True),
                )
                .correlate(cls)
                .scalar_subquery()
            )

    class LineItemComparison(Base):
        __tablename__ = "fencing_shape_comparison"
        id: Mapped[int] = mapped_column(primary_key=True)
        quote_id: Mapped[int] = mapped_column(ForeignKey("fencing_shape_quote.id"))
        benchmarked: Mapped[bool] = mapped_column(default=False)
        quote: Mapped[Quote] = relationship(back_populates="line_items")
        children: Mapped[list[QuoteLineItem]] = relationship(
            back_populates="comparison",
            cascade="all, delete-orphan",
        )
        benchmark_matches: Mapped[list[BenchmarkMatch]] = relationship(
            back_populates="comparison",
            cascade="all, delete-orphan",
        )

    class QuoteLineItem(Base):
        __tablename__ = "fencing_shape_line_item"
        id: Mapped[int] = mapped_column(primary_key=True)
        comparison_id: Mapped[int] = mapped_column(ForeignKey("fencing_shape_comparison.id"))
        comparison: Mapped[LineItemComparison] = relationship(back_populates="children")

    class BenchmarkMatch(Base):
        __tablename__ = "fencing_shape_benchmark"
        id: Mapped[int] = mapped_column(primary_key=True)
        comparison_id: Mapped[int] = mapped_column(ForeignKey("fencing_shape_comparison.id"))
        selected: Mapped[bool] = mapped_column(default=False)
        comparison: Mapped[LineItemComparison] = relationship(back_populates="benchmark_matches")

    configure_mappers()
    Base.metadata.create_all(engine)

    first = LineItemComparison(
        benchmarked=False,
        children=[QuoteLineItem(), QuoteLineItem()],
        benchmark_matches=[BenchmarkMatch(selected=False), BenchmarkMatch(selected=True)],
    )
    second = LineItemComparison(
        benchmarked=True,
        children=[QuoteLineItem()],
        benchmark_matches=[BenchmarkMatch(selected=False)],
    )
    quote = Quote(line_items=[first, second])
    session.add(quote)
    session.flush()

    assert _stored(session, Quote, quote.id) == (2, 1, 3, 1)

    # Exercise three different dependent mapper levels in one flush.
    first.benchmarked = True
    first.children.pop()
    second.benchmark_matches[0].selected = True
    session.flush()

    assert _stored(session, Quote, quote.id) == (2, 2, 2, 2)

    # Deleting a parent branch must invalidate the owning quote via old relationship history.
    quote.line_items.remove(first)
    session.flush()

    assert _stored(session, Quote, quote.id) == (1, 1, 1, 1)

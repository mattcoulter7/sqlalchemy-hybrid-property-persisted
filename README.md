<div align="center">

# SQLAlchemy Persisted Hybrid Property

Persist selected SQLAlchemy `hybrid_property` values into real database columns, while keeping normal hybrid descriptor behavior for Python access and SQL queries.

This is useful when a value is derived from ORM state, should still be queryable as a hybrid expression, but also needs to exist physically in the table for reads, migrations, reporting, indexing, or compatibility with code that expects a stored column.

![Python](https://img.shields.io/badge/Python-3.12-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![UV](https://img.shields.io/badge/UV-Fast-6E40C9?style=for-the-badge)
![Hatchling](https://img.shields.io/badge/Hatchling-PEP517-6E40C9?style=for-the-badge)
![Ruff](https://img.shields.io/badge/Ruff-Lint-000000?style=for-the-badge)
![Pre-commit](https://img.shields.io/badge/Pre--commit-Hooks-000000?style=for-the-badge)
![Pytest](https://img.shields.io/badge/Pytest-Unit%2BAsync-08979C?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Cov-Reports-08979C?style=for-the-badge)
![GitHub Actions](https://img.shields.io/badge/Actions-CI%2FCD-F7B500?style=for-the-badge&logo=github-actions)
![PyPI](https://img.shields.io/badge/PyPI-Publish-3775A9?style=for-the-badge&logo=pypi&logoColor=white)
![Makefile](https://img.shields.io/badge/Makefile-Scripts-F7B500?style=for-the-badge)

[![CI](https://github.com/mattcoulter7/sqlalchemy-persisted-hybrid-property/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/mattcoulter7/sqlalchemy-persisted-hybrid-property/actions/workflows/ci.yaml)

</div>


---

## Table of Contents
<!-- toc -->

- [Introduction](#introduction)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Formatting and linting](#formatting-and-linting)
- [CICD](#cicd)
- [Credits](#credits)

<!-- tocstop -->

---

## Introduction

This template repository aims to streamline the creation, testing, and publishing of isolated Python packages.

---

## Quick Start
Since this is just a package, and not a service, there is no real "run" action. But you can run the tests immediately.

Here are a list of available commands via make.

### Bare Metal (i.e. your machine)
1. `make install` - install the required dependencies.
2. `make test` - runs the tests.

## Installation

### For Dev work on the repo

Install `uv`, (_if you haven't already_)
https://docs.astral.sh/uv/getting-started/installation/#installation-methods
```shell
brew install uv
```

Initialise pre-commit (validates ruff on commit.)
```shell
uv run pre-commit install
```

Install dependencies (including dev dependencies)
```shell
uv sync
```

If you are adding a new dev dependency, please run:
```shell
uv add --dev {your-new-package}
```

## Quick Example

```python
from sqlalchemy import ForeignKey, Integer, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted


class Base(DeclarativeBase):
    pass


class Quote(Base):
    __tablename__ = "quote"

    id: Mapped[int] = mapped_column(primary_key=True)
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="quote")

    @hybrid_property_persisted(
        type_=Integer,
        nullable=False,
        default=0,
        materialize="auto",
    )
    def line_item_count(self) -> int:
        return len(self.line_items)

    @line_item_count.inplace.expression
    @classmethod
    def _line_item_count_expression(cls):
        return (
            select(func.count(LineItem.id))
            .where(LineItem.quote_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )


class LineItem(Base):
    __tablename__ = "line_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quote.id"))
    quote: Mapped[Quote] = relationship(back_populates="line_items")
```

The mapped table receives a real column:

```sql
line_item_count INTEGER NOT NULL
```

Then normal ORM work is enough:

```python
quote.line_items.append(LineItem())
session.add(quote)
session.flush()
```

The package updates the hidden backing column during the flush lifecycle. You keep using `quote.line_item_count` as a hybrid property.

## API

```python
@hybrid_property_persisted(
    type_=None,
    column_name=None,
    nullable=None,
    default=None,
    server_default=None,
    depends_on="auto",
    materialize="auto",
)
def value(self) -> int:
    ...
```

`type_` may be a SQLAlchemy type instance or class. If omitted, common return annotations are inferred: `int`, `bool`, `float`, `str`, `date`, `datetime`, `Decimal`, `UUID`, enums, and nullable unions like `int | None`.

`column_name` defaults to the property name.

`nullable` defaults from the return annotation for Python materialization. For SQL materialization, nullable storage is allowed so rows with database-generated primary keys can be inserted before the post-flush SQL update runs.

`depends_on` controls invalidation:

```python
depends_on="auto"
depends_on="value"
depends_on=["children", "children.value"]
```

`auto` infers dependencies from the SQL expression when available, and otherwise from unambiguous mapper relationship paths. Ambiguous paths fail loudly; use explicit paths in that case.

`materialize` controls how values are written:

```python
materialize="auto"    # prefer SQL expression, fall back to Python getter
materialize="sql"     # require a hybrid SQL expression
materialize="python"  # evaluate the Python getter on the owner object
```

## SQLModel

Use the SQLModel shim if you want persisted hybrids in SQLModel classes:

```python
from sqlmodel import Field

from sqlalchemy_persisted_hybrid_property import hybrid_property_persisted
from sqlalchemy_persisted_hybrid_property.sqlmodel import SQLModel


class Metric(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    value: int

    @hybrid_property_persisted()
    def doubled(self) -> int:
        return self.value * 2
```

The hidden backing attribute is ignored by Pydantic/SQLModel fields and does not appear in `model_dump()`.

## How It Works

The package is SQLAlchemy-native. It subclasses SQLAlchemy's `hybrid_property` instead of wrapping or cloning it, so `.expression`, `.setter`, `.update_expression`, custom comparators, and `.inplace` modifiers keep normal hybrid semantics.

During mapper construction, persisted hybrid descriptors are discovered via SQLAlchemy mapper descriptors. A physical `Column` is injected into the mapped table and mapped under a hidden storage key such as `__php_line_item_count`, leaving the public hybrid name untouched.

During flush, changed ORM instances are resolved back to affected owner instances using SQLAlchemy inspection, relationship metadata, and attribute history. Relationship removals, deletes, reparenting, unloaded FK changes, many-to-many collections, composite primary keys, and async sessions are supported by the test suite.

When a SQL expression is available, materialization uses batched SQL like:

```sql
UPDATE quote
SET line_item_count = (
    SELECT count(...)
)
WHERE quote.id IN (...)
```

This avoids calling the Python getter for SQL-capable properties and keeps inserts/deletes visible by running after ORM DML has reached the database. Python materialization writes the hidden mapped attribute directly, so SQLAlchemy naturally persists the stored value.

## Alembic

Injected columns are added to `Base.metadata`, so Alembic autogenerate can see them as long as your models and this package are imported before autogenerate runs.

---

## Formatting and linting

We use Ruff as the formatter and linter.
The pre-commit has hooks which runs checking and applies linting automatically.
The CI validates the linting, ensuring main is always looking clean.

You can manually use these commands too:
1. `make lint` - check for linting issues.
2. `make format` - fix linting issues.

---

## CICD

### Publishing to PyPI

We publish to PyPI using GitHub releases and PyPI trusted publishing. Steps are as follows:

1. Manually update the version in `pyproject.toml` file using a PR and merge to main. Use `uv version --bump {patch/minor/major}` to update the version.
2. Create a new release in GitHub with the tag name as the version number. This will trigger the `publish` workflow. In the Release window, type in the version number and it will prompt to create a new tag.
3. Verify the release on PyPI.

---

## Credits
This template repository has taken inspiration from the following repositories.
- [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template)

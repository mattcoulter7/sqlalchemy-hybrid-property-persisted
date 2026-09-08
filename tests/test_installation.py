from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from sqlalchemy_persisted_hybrid_property import install


def test_install_is_idempotent():
    install()
    install()
    install()

    # Package exposes this for introspection/testing rather than relying on private
    # SQLAlchemy event registry internals.
    from sqlalchemy_persisted_hybrid_property import installation_state

    state = installation_state()
    assert state.installed is True
    assert state.mapper_listener_count == 1
    assert state.before_flush_listener_count == 1
    assert state.after_flush_postexec_listener_count == 1
    assert state.do_orm_execute_listener_count == 1


def test_sqlmodel_is_optional_project_extra():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    core_dependencies = "\n".join(pyproject["project"]["dependencies"])

    assert "aiosqlite" not in core_dependencies
    assert "alembic" not in core_dependencies
    assert "greenlet" not in core_dependencies
    assert "sqlmodel" not in core_dependencies
    assert pyproject["project"]["optional-dependencies"]["sqlmodel"] == ["sqlmodel>=0.0.27,<0.1"]


def test_core_import_and_sqlmodel_module_do_not_require_sqlmodel():
    script = """
import importlib.abc
import sys


class BlockSqlModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "sqlmodel" or fullname.startswith("sqlmodel."):
            raise ModuleNotFoundError("blocked sqlmodel", name="sqlmodel")
        return None


sys.meta_path.insert(0, BlockSqlModel())

import sqlalchemy_persisted_hybrid_property
from sqlalchemy_persisted_hybrid_property.sqlmodel import SQLModel

try:
    class Metric(SQLModel):
        pass
except RuntimeError as exc:
    assert "sqlalchemy-persisted-hybrid-property[sqlmodel]" in str(exc)
else:
    raise AssertionError("SQLModel placeholder should explain the missing extra")
"""
    subprocess.run([sys.executable, "-c", script], check=True)

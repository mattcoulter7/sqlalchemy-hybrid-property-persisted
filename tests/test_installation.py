from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Mapper, Session

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

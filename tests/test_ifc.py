#!/usr/bin/env python3

from __future__ import annotations as __annotations

import pytest

from passlib.ifc import PasswordHash


def test_instantiating_abstract_class_raises_exception():

    with pytest.raises(TypeError, match="Can't instantiate abstract class PasswordHash without an implementation for abstract methods"):
        PasswordHash()


def test_password_hash_subclass_can_be_instantiated():
    """
    Verify that a subclass of PasswordHash can be instantiated.
    """

    class TestAlgo(PasswordHash):

        @classmethod
        def hash(cls, secret: str | bytes, **kwds: object) -> str:
            return '<not implemented>'

        @classmethod
        def verify(cls, secret: str | bytes, hash: str | bytes, **kwds: object) -> bool:
            return False

        @classmethod
        def using(cls, relaxed: bool = False, **kwds: object) -> type[TestAlgo]:
            return cls

        @classmethod
        def identify(cls, hash: str | bytes) -> bool:
            return False

        @classmethod
        def needs_update(cls, hash: str | bytes, secret: str | bytes | None = None) -> bool:
            return True

    obj = TestAlgo()
    assert isinstance(obj, PasswordHash)
    assert callable(obj.hash)
    assert callable(obj.verify)
    assert callable(obj.using)
    assert callable(obj.identify)
    assert callable(obj.needs_update)


if __name__ == '__main__':
    pytest.main()

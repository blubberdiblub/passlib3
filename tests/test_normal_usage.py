#!/usr/bin/env python3

from __future__ import annotations as __annotations

import pytest

from passlib.context import CryptContext


def test_instantiate_crypt_context() -> None:

    CryptContext(schemes=['sha256_crypt'])


def test_crypt_context_with_sha256() -> None:

    crypt_ctx = CryptContext(schemes=['sha256_crypt'])
    assert crypt_ctx.schemes() == ('sha256_crypt',)
    assert crypt_ctx.default_scheme() =='sha256_crypt'

    digest = crypt_ctx.hash(b'foobar')
    assert isinstance(digest, str)
    assert crypt_ctx.verify(b'foobar', digest) is True


if __name__ == '__main__':
    pytest.main()

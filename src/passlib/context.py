#!/usr/bin/env python3

from __future__ import annotations as _annotations

from importlib import import_module as _import_module

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal
    from .ifc import PasswordHash


class CryptContext:

    _schemes: dict[str, PasswordHash]
    _default: str | None
    _deprecated: set[str]

    def __init__(
        self,
        schemes: Sequence[str],
        default: str | None = None,
        deprecated: Sequence[str] | Sequence[Literal['auto']] = (),
    ) -> None:
        self._default = default
        self._deprecated = set(deprecated)
        if 'auto' in self._deprecated:
            if len(self._deprecated) > 1:
                raise ValueError(
                    "'auto' cannot be used together with explicit scheme names in 'deprecated'"
                )
            self._deprecated = set()
            auto_deprecated = True
        else:
            auto_deprecated = False

        self._schemes = {}
        for scheme in schemes:
            try:
                module = _import_module('.' + scheme, package='passlib.hash')
            except ImportError:
                raise ValueError(f"cannot find module for scheme {scheme!r}") from None

            try:
                self._schemes[scheme] = getattr(module, scheme)
            except AttributeError:
                raise ValueError(f"cannot find class for scheme {scheme!r}") from None

            if self._default is None and scheme not in self._deprecated:
                self._default = scheme
            elif auto_deprecated and scheme != self._default:
                self._deprecated.add(scheme)

    def schemes(self) -> tuple[str, ...]:
        return tuple(self._schemes.keys())

    def default_scheme(self) -> str | None:
        return self._default

    def hash(self, secret: str | bytes, scheme: str | None = None, **kwds: object) -> str:
        assert scheme is None
        assert not kwds

        if scheme is None:
            if self._default is None:
                raise ValueError("no default scheme set")
            scheme = self._default

        try:
            algo = self._schemes[scheme]
        except KeyError:
            raise ValueError(f"unknown scheme: {scheme!r}") from None

        return algo.hash(secret, **kwds)

    def verify(self, secret: str | bytes, hash: str | bytes, scheme: str | None = None, **kwds: object) -> bool:
        assert scheme is None
        assert not kwds

        if scheme is None:
            if self._default is None:
                raise ValueError("no default scheme set")
            scheme = self._default

        try:
            algo = self._schemes[scheme]
        except KeyError:
            raise ValueError(f"unknown scheme: {scheme!r}") from None

        return algo.verify(secret, hash, **kwds)

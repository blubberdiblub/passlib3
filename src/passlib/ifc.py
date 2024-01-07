#!/usr/bin/env python3

from __future__ import annotations as _annotations

from abc import ABC as _ABC, abstractmethod as _abstractmethod

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Literal, Type


class PasswordHash(_ABC):

    name: str
    settings_kwds: tuple[Literal['salt', 'salt_size', 'rounds', 'ident', 'truncate_error', 'relaxed'] | str, ...]
    context_kwds: tuple[Literal['user', 'encoding'] | str,...]
    truncate_size: int | None  # `None` means algo doesn't truncate the secret

    max_salt_size: int | None  # TODO: find out what to provide for saltless algos
    min_salt_size: int  # TODO: find out what to provide for saltless algos
    default_salt_size: int  # TODO: find out what to provide for saltless algos
    salt_chars: str  # TODO: figure out the actual semantics of this and why it supposedly needs to be bytes for a few algos

    max_rounds: int | None  # TODO: find out what to provide for non-iterated algos
    min_rounds: int  # TODO: find out what to provide for non-iterated algos
    default_rounds: int  # TODO: find out what to provide for non-iterated algos
    rounds_cost: Literal['linear', 'log2']  # TODO: find out what to provide for non-iterated algos

    @classmethod
    @_abstractmethod
    def hash(cls, secret: str | bytes, **kwds: object) -> str:
        raise NotImplementedError

    @classmethod
    @_abstractmethod
    def verify(cls, secret: str | bytes, hash: str | bytes, **kwds: object) -> bool:
        raise NotImplementedError

    @classmethod
    @_abstractmethod
    def using(cls, relaxed: bool = False, **kwds: object) -> Type[PasswordHash]:
        raise NotImplementedError

    @classmethod
    @_abstractmethod
    def identify(cls, hash: str | bytes) -> bool:
        raise NotImplementedError

    @classmethod
    @_abstractmethod
    def needs_update(cls, hash: str | bytes, secret: str | bytes | None = None) -> bool:
        raise NotImplementedError

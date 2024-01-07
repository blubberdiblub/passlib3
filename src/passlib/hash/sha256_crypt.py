#!/usr/bin/env python3

from __future__ import annotations as _annotations

import os

from ctypes import cdll, CDLL, c_char_p, c_ulong, c_int, c_void_p, POINTER, pointer, get_errno, set_errno, byref

from ..ifc import PasswordHash


libc = CDLL('libc.so.6')

free = libc['free']
free.argtypes = [c_void_p]
free.restype = None

libcrypt = CDLL('libcrypt.so.1', use_errno=True)

crypt_gensalt_ra = libcrypt['crypt_gensalt_ra']
crypt_gensalt_ra.argtypes = [
    c_char_p,
    c_ulong,
    c_char_p,
    c_int
]
crypt_gensalt_ra.restype = c_char_p

crypt_ra = libcrypt['crypt_ra']
crypt_ra.argtypes = [c_char_p, c_char_p, POINTER(c_void_p), POINTER(c_int)]
crypt_ra.restype = c_char_p


class sha256_crypt(PasswordHash):

    @classmethod
    def hash(cls, secret: str | bytes, **kwds: object) -> str:
        assert not kwds

        if isinstance(secret, str):
            secret = secret.encode('utf-8')

        assert b'\0' not in secret

        assert set_errno(0) == 0
        setting = crypt_gensalt_ra(b'$5$', 0, None, 0)
        if setting is None or get_errno() != 0:
            if setting is not None:
                free(setting)
            raise RuntimeError(f"crypt_gensalt_ra() failed with error {os.strerror(get_errno())}")

        data_p = c_void_p(None)
        size = c_int(0)
        assert set_errno(0) == 0
        rv1 = crypt_ra(secret, setting, byref(data_p), byref(size))
        # FIXME: why does freeing setting here crash?
        if rv1 is None or get_errno() != 0:
            free(data_p)
            raise RuntimeError(f"crypt_ra() failed with error {os.strerror(get_errno())}")

        result = rv1.decode('ascii')
        free(data_p)

        return result

    @classmethod
    def verify(cls, secret: str | bytes, hash: str | bytes, **kwds: object) -> bool:
        assert not kwds

        if isinstance(secret, str):
            secret = secret.encode('utf-8')

        if isinstance(hash, str):
            hash = hash.encode('ascii')

        assert b'\0' not in secret
        assert b'\0' not in hash

        data_p = c_void_p(None)
        size = c_int(0)
        assert set_errno(0) == 0
        rv1 = crypt_ra(secret, hash, byref(data_p), byref(size))
        if rv1 is None or get_errno() != 0:
            free(data_p)
            raise RuntimeError(f"crypt_ra() failed with error {os.strerror(get_errno())}")

        result = rv1 == hash
        free(data_p)

        return result

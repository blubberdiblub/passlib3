#!/usr/bin/env python3

from __future__ import annotations as __annotations

import importlib as __importlib
import sys as __sys

from pathlib import Path as __Path

import numpy.random as __npr
import pytest

from typing import TYPE_CHECKING  # isort: skip

if TYPE_CHECKING:
    from numpy.random import Generator as RNG
    from pytest import FixtureRequest

__sys.path.insert(0, str((__Path(__file__).parent / '..' / 'src').resolve()))
__importlib.import_module('passlib')
__sys.path.insert(0, str((__Path(__file__).parent / '..').resolve()))
__importlib.import_module('_get_tzinfo')


@pytest.fixture(scope='session')
def nondeterministic_rng() -> RNG:

    return __npr.default_rng()


@pytest.fixture(scope='function', params=[67890])
def deterministic_rng(request: FixtureRequest) -> RNG:

    return __npr.default_rng(request.param)

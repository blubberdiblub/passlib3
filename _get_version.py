#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess

from os import PathLike

from packaging.version import (
    parse as parse_version,
    Version,
    VERSION_PATTERN,
)


def get_version_from_git(path: PathLike[str]) -> str:

    head = subprocess.check_output([
        'git', '-C', path, 'symbolic-ref', '--short', 'HEAD',
    ], text=True).strip()

    refs = [line.split()[1].split('/', maxsplit=2)[2] for line in subprocess.check_output([
        'git', '-C', path, 'show-ref',
        '--tags',
        '--heads',
    ], text=True).splitlines()]

    refs = [
        ref for ref in refs
        if re.fullmatch(VERSION_PATTERN, ref.rsplit('/', maxsplit=1)[-1], re.VERBOSE)
    ]

    describe = subprocess.check_output([
        'git', '-C', path, 'describe',
        '--dirty',
        '--all',
        f'--candidates={len(refs)}',
        '--long',
        *(f'--match={ref}' for ref in refs),
        '--always',
        '--first-parent',
    ], text=True).strip()

    dirty = describe.endswith('-dirty')
    *local, describe = describe.removesuffix('-dirty').split('/')
    if local and local[0] in ('heads', 'tags'):
        local = local[1:]
    if head not in ('main', 'master', 'develop'):
        local[:0] = [head]

    parts = describe.rsplit('-', maxsplit=2)
    match parts:
        case version_str, post, commit:
            if re.fullmatch(VERSION_PATTERN, version_str, re.VERBOSE):
                v = parse_version(version_str)
                if v.local:
                    local.append(v.local)
            else:
                v = Version('0.0')
                local.append(version_str)
            post = int(post)
            if post or dirty:
                local.append(commit)
        case commit, *local:
            v = Version('0.0')
            post = 0
            local[:0] = ['g' + commit]
        case _:
            raise NotImplementedError()

    if dirty:
        local.append('dirty')

    parts = [
        v.base_version,
        f'{v.pre[0]}{v.pre[1]}' if v.pre else '',
        f'.post{(v.post or 0) + post}' if post or dirty or v.post is not None else '',
        f'.dev{v.dev}' if v.dev is not None else '',
    ]

    return f'{''.join(parts)}{'+' + '.'.join(local) if local else ''}'

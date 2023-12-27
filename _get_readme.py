#!/usr/bin/env python3

from __future__ import annotations

import mimetypes

from email.headerregistry import HeaderRegistry
from functools import partial
from os import PathLike
from pathlib import Path


_make_content_type = partial(HeaderRegistry()['content-type'], 'content-type')

if not mimetypes.inited:
    mimetypes.init()

mimetypes.add_type('text/plain', '.txt', strict=True)
mimetypes.add_type('text/x-rst', '.rst', strict=False)
mimetypes.add_type('text/markdown', '.md', strict=True)


def get_readme(
    dir: PathLike[str] | str,
    source: dict[str, str] | str | None,
) -> tuple[str, str] | tuple[None, None]:

    dir = Path(dir)
    path = Path('')
    text = None
    content_type = None

    match source:
        case {'file': str(name),
              'content-type': str(content_type),
              **rest} if 'text' not in rest:
            path = dir / name
            content_type = _make_content_type(content_type)

        case {'text': str(text),
              'content-type': str(content_type),
              **rest} if 'file' not in rest:
            content_type = _make_content_type(content_type)

        case str(name):
            path = dir / name

        case None:
            for name, content_type in [
                ('README.md', 'text/markdown; variant=gfm'),
                ('README.rst', 'text/x-rst'),
                ('README.txt', 'text/plain'),
                ('README', 'text/plain'),
            ]:
                path = dir / name
                if path.exists():
                    break
            else:
                return None, None

            content_type = _make_content_type(f'{content_type}; charset=utf-8')

        case _:
            raise ValueError("invalid description entry")

    if text is None:
        if content_type is None:
            mimetype, coding = mimetypes.guess_type(path, strict=False)
            if not mimetype or not mimetype.startswith('text/'):
                raise TypeError("file must be of text type")
            if coding is not None:
                raise TypeError("file coding {coding} not supported")
            content_type = _make_content_type(f'{mimetype}; charset=utf-8')

        text = path.read_text(encoding=content_type.params.get('charset', 'utf-8'))

    else:
        assert content_type is not None

    if content_type.params.get('charset') != 'utf-8':
        variant = content_type.params.get('variant')
        variant = f'; variant={variant}' if variant else ''
        content_type = _make_content_type(f'{content_type.content_type}{variant}; charset=utf-8')

    return text, content_type

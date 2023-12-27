#!/usr/bin/env python3

from __future__ import annotations

import os
import stat
import sys
import tomllib

from base64 import urlsafe_b64encode as base64url_encode
from csv import Dialect, QUOTE_MINIMAL, writer as csv_writer
from datetime import datetime as DateTime, UTC
from functools import update_wrapper
from hashlib import sha256
from importlib import import_module
from io import StringIO
from itertools import product
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import tzinfo as TZInfo
    from hashlib import _Hash as Hash
    from os import PathLike
    from typing import Any


PROJECT_PATH = Path(__file__).parent
SRC_PATH = PROJECT_PATH / 'src'
TESTS_PATH = PROJECT_PATH / 'tests'

sys.path.insert(0, str(PROJECT_PATH.resolve()))

PYPROJECT_PATH = PROJECT_PATH / 'pyproject.toml'
PYPROJECT = tomllib.load(PYPROJECT_PATH.open(mode='rb')) if PYPROJECT_PATH.exists() else {}
PROJECT = PYPROJECT.get('project', {})
PROJECT_NAME = PROJECT.get('name') or PROJECT_PATH.resolve().name
PROJECT_VERSION = PROJECT.get('version') or import_module('_get_version').get_version_from_git(
    PROJECT_PATH
)
PROJECT_TAG = PROJECT.get('tag', 'py3-none-any')
PROJECT_SUMMARY = PROJECT.get('description') or None
PROJECT_DESCRIPTION, PROJECT_DESCRIPTION_CONTENT_TYPE = import_module('_get_readme').get_readme(
    PROJECT_PATH, PROJECT.get('readme')
)

METADATA = [
    ('Metadata-Version', '2.1'),
    ('Name', PROJECT_NAME),
    ('Version', PROJECT_VERSION),
    *([('Summary', PROJECT_SUMMARY)] if PROJECT_SUMMARY else []),
    *(
        [('Description-Content-Type', str(PROJECT_DESCRIPTION_CONTENT_TYPE))]
        if PROJECT_DESCRIPTION_CONTENT_TYPE
        else []
    ),
    *([('Description', PROJECT_DESCRIPTION)] if PROJECT_DESCRIPTION else []),
]

WHEEL = [
    ('Wheel-Version', '1.0'),
    ('Generator', f'{PROJECT_NAME}/{Path(__file__).name}'),
    ('Root-Is-Purelib', 'true'),
    *(('Tag', '-'.join(m)) for m in product(*(p.split('.') for p in PROJECT_TAG.split('-')))),
]

DIST_INFO_NAME = f'{PROJECT_NAME}-{PROJECT_VERSION}.dist-info'
WHEEL_FILENAME = f'{PROJECT_NAME}-{PROJECT_VERSION}-{PROJECT_TAG}.whl'


def prepare_metadata_for_build_wheel(
    metadata_directory: PathLike[str] | str,
    config_settings: dict[str, str] | None = None,
    **_kwargs: dict[str, str],
):
    metadata_directory = Path(metadata_directory)
    print(file=sys.stderr)
    print("prepare_metadata_for_build_wheel", file=sys.stderr)
    print("================================", file=sys.stderr)
    print(f"{metadata_directory = !r}", file=sys.stderr)
    print(f"{config_settings = !r}", file=sys.stderr)
    print(f"{_kwargs = !r}", file=sys.stderr)
    sys.stderr.flush()
    assert not _kwargs

    dist_info_path = metadata_directory / DIST_INFO_NAME
    dist_info_path.mkdir()

    (dist_info_path / 'WHEEL').write_text(
        '\n'.join(f'{k}: {v}' for k, v in WHEEL) + '\n', encoding='utf-8', newline='\r\n'
    )

    (dist_info_path / 'METADATA').write_text(
        '\n'.join(f'{k}: {v}' for k, v in METADATA if k.lower() != 'description')
        + '\n'
        + ('\n' + PROJECT_DESCRIPTION if PROJECT_DESCRIPTION else ''),
        encoding='utf-8',
        newline='\r\n',
    )

    return DIST_INFO_NAME


class Wheel(ZipFile):
    class __RecordDialect(Dialect):
        delimiter = ','
        doublequote = False
        escapechar = '\\'
        lineterminator = '\n'
        quotechar = '"'
        quoting = QUOTE_MINIMAL
        skipinitialspace = True
        strict = True

    def __init__(self, path: PathLike[str] | str, **kwargs: Any) -> None:
        super().__init__(
            path,
            mode='x',
            compression=ZIP_DEFLATED,
            allowZip64=True,
            compresslevel=8,
            strict_timestamps=False,
            **kwargs,
        )
        self.__dist_info_prefix: PurePosixPath | None = None
        self.__dist_info: dict[PurePosixPath, tuple[bytes, Hash] | None] = {}
        self.__record: dict[PurePosixPath, tuple[Hash, int]] = {}
        self.__buf: bytearray = bytearray(64 * 1024)
        self.__modified: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)

        try:
            get_tzinfo: Callable[[], TZInfo] = import_module('_get_tzinfo').get_tzinfo
        except (ImportError, AttributeError):
            self.__tz = None
        else:
            self.__tz = get_tzinfo()

        self.__min_dt = DateTime(1980, 1, 1).astimezone(tz=self.__tz)
        self.__max_dt = DateTime(2107, 12, 31, 23, 59, 59, 999999).astimezone(tz=self.__tz)

    def make_zipinfo(
        self,
        path: PathLike[str] | str,
        *,
        typ: int | None = None,
        dt: DateTime | tuple[int, ...] | float | int | None = None,
        traversable: bool = True,
        executable: bool = True,
        writable: bool = True,
    ) -> ZipInfo:
        typ = stat.S_IFMT(typ or 0)
        if not stat.S_ISDIR(typ) and isinstance(path, str) and path.endswith('/'):
            assert not typ
            typ = stat.S_IFDIR
        elif not typ:
            typ = stat.S_IFREG

        path = PurePosixPath(path)
        assert not path.is_absolute()

        if isinstance(dt, (float, int)):
            dt = DateTime.fromtimestamp(dt, tz=UTC)
        elif not isinstance(dt, DateTime):
            dt = DateTime(*((1980, 1, 1) if dt is None else dt))

        dt = dt.astimezone(tz=self.__tz)
        if dt < self.__min_dt:
            if self._strict_timestamps:
                raise ValueError(f"timestamp must not be before {self.__min_dt}")
            dt = self.__min_dt
        elif dt > self.__max_dt:
            if self._strict_timestamps:
                raise ValueError(f"timestamp must not be after {self.__max_dt}")
            dt = self.__max_dt

        mode = 0o2775 if stat.S_ISDIR(typ) else 0o775
        if not (traversable if stat.S_ISDIR(typ) else executable):
            mode &= ~0o111
        if not writable:
            mode &= ~0o222

        dos_attr = 0x10 if stat.S_ISDIR(typ) else 0
        if not writable:
            dos_attr |= 1
        if any(part.startswith('.') for part in path.parts):
            dos_attr |= 2

        path = path.as_posix()
        zinfo = ZipInfo(path + '/' if stat.S_ISDIR(typ) else path, date_time=dt.timetuple()[:6])
        zinfo.create_system = 3
        zinfo.external_attr = (typ | mode) << 16 | dos_attr
        match typ:
            case stat.S_IFDIR:
                zinfo.CRC = 0
            case stat.S_IFREG:
                zinfo.compress_type = self.compression
                zinfo._compresslevel = self.compresslevel
            case _:
                raise NotImplemented("unsupported file type")

        return zinfo

    def _collect_tree_info(
        self,
        rel: PurePosixPath,
        tree: Path,
        out_dirs: list[tuple[ZipInfo | PurePosixPath, list[tuple[Path, ZipInfo]]]],
    ) -> tuple[int, int, int, int, int, int]:
        tree_zinfo = self.make_zipinfo(rel, typ=stat.S_IFDIR)
        is_dist_info = bool(rel.parts) and rel.parts[0].endswith('.dist-info')

        dirs: list[Path] = []
        files: list[tuple[Path, ZipInfo]] = []
        for path in tree.iterdir():
            if path.is_symlink():
                continue

            if path.is_dir():
                if path.name != '__pycache__':
                    dirs.append(path)
            elif path.is_file():
                arc_path = rel / path.name
                if is_dist_info:
                    zinfo = self.make_zipinfo(arc_path, typ=stat.S_IFREG)
                else:
                    st = path.lstat()
                    zinfo = self.make_zipinfo(
                        arc_path,
                        typ=st.st_mode,
                        dt=st.st_mtime,
                        executable=os.access(path, os.X_OK),
                        writable=os.access(path, os.W_OK),
                    )
                    if zinfo.date_time > tree_zinfo.date_time:
                        tree_zinfo.date_time = zinfo.date_time
                files.append((path, zinfo))

        files.sort(key=lambda path_zinfo: path_zinfo[0].name.casefold())
        out_dirs.append((tree_zinfo if not is_dist_info else rel, files))

        dirs.sort(key=lambda path: path.name.casefold())
        for dir in dirs:
            date_time = self._collect_tree_info(rel / dir.name, dir, out_dirs)
            if not is_dist_info and date_time > tree_zinfo.date_time:
                tree_zinfo.date_time = date_time

        return tree_zinfo.date_time

    def add_tree(self, root: PathLike[str] | str, tree: PathLike[str] | str) -> None:
        root = PurePosixPath(root)
        root = root.relative_to(root.root)
        dirs: list[tuple[ZipInfo | PurePosixPath, list[tuple[Path, ZipInfo]]]] = []
        date_time = self._collect_tree_info(root, Path(tree), dirs)
        if date_time > self.__modified:
            self.__modified = date_time

        for dir, files in dirs:
            if isinstance(dir, ZipInfo):
                self._add_dir(dir, files)
            else:
                self._add_dist_info(dir, files)

    def _add_dir(self, dir: ZipInfo, files: list[tuple[Path, ZipInfo]]) -> None:
        buf = memoryview(self.__buf)
        if dir.filename not in './':
            self.mkdir(dir)
        for path, zinfo in files:
            hash = sha256()
            with open(path, mode='rb') as src, self.open(zinfo, 'w') as dst:
                nbytes = src.readinto(buf)
                while nbytes > 0:
                    dst.write(buf[:nbytes])
                    hash.update(buf[:nbytes])
                    nbytes = src.readinto(buf)
            self.__record[PurePosixPath(zinfo.filename)] = hash, zinfo.file_size

    def _add_dist_info(self, dir: PurePosixPath, files: list[tuple[Path, ZipInfo]]) -> None:
        if self.__dist_info_prefix is None:
            self.__dist_info_prefix = PurePosixPath(dir.parts[0])
        rel = dir.relative_to(self.__dist_info_prefix)

        self.__dist_info[rel] = None

        for path, _ in files:
            content = path.read_bytes()
            self.__dist_info[rel / path.name] = content, sha256(content)

    def close(self) -> None:
        if self.fp is None:
            return

        assert self.__dist_info_prefix is not None

        for rel, file in self.__dist_info.items():
            path = self.__dist_info_prefix / rel
            typ = stat.S_IFREG if file else stat.S_IFDIR
            zinfo = self.make_zipinfo(path, typ=typ, dt=self.__modified, executable=False)
            if file:
                content, hash = file
                with self.open(zinfo, 'w') as dst:
                    dst.write(content)
                self.__record[path] = hash, zinfo.file_size
            else:
                self.mkdir(zinfo)
        self.__dist_info = None

        with StringIO(newline='\n') as record:
            writer = csv_writer(record, dialect=self.__RecordDialect)
            for rel, (hash, size) in self.__record.items():
                digest = base64url_encode(hash.digest()).decode('ascii').rstrip('=')
                writer.writerow((rel, f'{hash.name}={digest}', size))
            self.__record = None

            path = self.__dist_info_prefix / 'RECORD'
            writer.writerow((path, None, None))

            zinfo = self.make_zipinfo(path, dt=self.__modified, executable=False)
            with self.open(zinfo, 'w') as dst:
                dst.write(record.getvalue().encode('utf-8'))

        self.__buf = None
        super().close()


def _build_wheel(
    wheel_directory: PathLike[str] | str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: PathLike[str] | str | None = None,
    editable: bool = False,
):
    wheel_directory = Path(wheel_directory)
    if metadata_directory is not None:
        metadata_directory = Path(metadata_directory)
    print(file=sys.stderr)
    print("_build_wheel", file=sys.stderr)
    print("============", file=sys.stderr)
    print(f"{wheel_directory = !r}", file=sys.stderr)
    print(f"{config_settings = !r}", file=sys.stderr)
    print(f"{metadata_directory = !r}", file=sys.stderr)
    print(f"{editable = !r}", file=sys.stderr)
    sys.stderr.flush()
    with Wheel(wheel_directory / WHEEL_FILENAME) as f:
        f.add_tree('.', SRC_PATH)
        f.add_tree('tests', 'tests')
        if metadata_directory is not None:
            f.add_tree(DIST_INFO_NAME, metadata_directory)
    return WHEEL_FILENAME


def build_wheel(
    wheel_directory: PathLike[str] | str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: PathLike[str] | str | None = None,
    **_kwargs: dict[str, str],
) -> str:
    assert not _kwargs
    return _build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
        editable=False,
    )


def build_editable(
    wheel_directory: PathLike[str] | str,
    config_settings: dict[str, str] | None = None,
    metadata_directory: PathLike[str] | str | None = None,
    **_kwargs: dict[str, str],
) -> str:
    assert not _kwargs
    return _build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
        editable=True,
    )


def build_sdist(
    sdist_directory: PathLike[str] | str,
    config_settings: dict[str, str] | None = None,
    **_kwargs: dict[str, str],
):
    sdist_directory = Path(sdist_directory)
    print(file=sys.stderr)
    print("build_sdist", file=sys.stderr)
    print("===========", file=sys.stderr)
    print(f"{sdist_directory = !r}", file=sys.stderr)
    print(f"{config_settings = !r}", file=sys.stderr)
    print(f"{_kwargs = !r}", file=sys.stderr)
    sys.stderr.flush()
    assert not _kwargs
    raise NotImplementedError("not yet implemented")


def digest_args(f: Callable[..., int]) -> Callable[[], int]:
    def _f(args: Sequence[str] | None = None, progname: str | None = None) -> int:
        args: list[str] = sys.argv[1:] if args is None else list(args)
        help = f"{progname or sys.argv[0]} [-h|--help] [-V|--version] <command> [args...]"
        remaining: list[str] = []
        verbosity = 0

        while args:
            if len(args[0]) > 2 and args[0][0] == '-':
                if args[0][1] != '-':
                    args[:1] = args[0][:2], '-' + args[0][2:]
                elif '=' in args[0][3:]:
                    assert args[0][2].isidentifier()
                    args[:1] = args[0].split('=', maxsplit=1)

            match args:
                case ['--help', *_] | ['-h', *_]:
                    print(help, flush=True)
                    raise SystemExit(0)
                case ['--version', *_] | ['-V', *_]:
                    print(PROJECT_NAME, PROJECT_VERSION, flush=True)
                    raise SystemExit(0)
                case ['--verbose', *args] | ['-v', *args]:
                    verbosity += 1
                    continue
                case ['--quiet', *args] | ['-q', *args]:
                    verbosity -= 1
                    continue
                case ['--', *args]:
                    remaining.extend(args)
                    break
                case [arg, *args]:
                    if arg.startswith('-'):
                        print(f"ERROR: unrecognized option {arg!r}", flush=True, file=sys.stderr)
                        raise SystemExit(2)
                    remaining.append(arg)
                case _:
                    assert False

        if not remaining:
            print("ERROR: missing command", flush=True, file=sys.stderr)
            print(help, flush=True, file=sys.stderr)
            raise SystemExit(2)

        return f(remaining[0], *remaining[1:], verbosity=verbosity)

    return update_wrapper(_f, f, assigned=('__doc__', '__name__', '__qualname__', '__module__'))


@digest_args
def do(cmd: str, *args: str, verbosity: int = 0) -> int:

    import locale
    from contextlib import suppress
    with suppress(locale.Error):
        locale.setlocale(locale.LC_ALL, '')

    from pip._internal.commands import create_command

    match cmd:
        case 'wheel':
            command = create_command('wheel', isolated=True)
            return command.main([
                '--use-pep517',
                '--isolated',
                *(['-' + 'v' * verbosity] if verbosity > 0 else []),
                *(['-' + 'q' * -verbosity] if verbosity < 0 else []),
                '--no-input',
                '--disable-pip-version-check',
                *args,
                '--',
                '.',
            ])
        case _:
            pass

    print(f"{cmd = !r}")
    print(f"{args = !r}")
    return 0


if __name__ == '__main__':
    raise SystemExit(do())

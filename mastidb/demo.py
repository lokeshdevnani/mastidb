"""Sample datasets the CLI can fetch and ingest.

Wikipedia (~24k rows) is committed in a git clone, so we use that copy when
it's there. Menu items are too big for git; they're pulled from NYPL on demand.
Pip installs have neither, so both fall back to a download into ~/.cache/mastidb.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WIKIPEDIA_URL = (
    'https://raw.githubusercontent.com/lokeshdevnani/mastidb/main/'
    'tests/datasets/wikipedia.json'
)
MENU_URL = 'https://s3.amazonaws.com/menusdata.nypl.org/gzips/2021_08_01_07_01_17_data.tgz'
MENU_SOURCE_PAGE = 'http://menus.nypl.org/data'
MENU_FILES = ('Dish.csv', 'Menu.csv', 'MenuItem.csv', 'MenuPage.csv')

ALIASES = {
    'wiki': 'wikipedia',
    'menu': 'menuitem',
    'menus': 'menuitem',
}


@dataclass(frozen=True)
class Dataset:
    name: str
    blurb: str
    rows: str
    size: str
    starter: bool
    default_data_dir: str
    queries: tuple[str, ...]


DATASETS = {
    'wikipedia': Dataset(
        name='wikipedia',
        blurb='Wikipedia edits (the Druid tutorial sample)',
        rows='24,433',
        size='~11 MB',
        starter=True,
        default_data_dir='/tmp/wikipedia',
        queries=(
            'SELECT COUNT(*)',
            "SELECT cityName, added WHERE countryName = 'India' ORDER BY added DESC LIMIT 5",
            'SELECT channel, SUM(added) GROUP BY channel ORDER BY SUM(added) DESC LIMIT 5',
        ),
    ),
    'menuitem': Dataset(
        name='menuitem',
        blurb="NYPL menu items — the million-row benchmark",
        rows='~1.3M',
        size='~35 MB download',
        starter=False,
        default_data_dir='/tmp/menuitem',
        queries=(
            'SELECT COUNT(id)',
            'SELECT menu_page_id, COUNT(id) GROUP BY menu_page_id ORDER BY COUNT(id) DESC LIMIT 10',
            "SELECT COUNT(id) WHERE price = '0.25'",
        ),
    ),
}


@dataclass(frozen=True)
class SourceFile:
    path: str
    origin: str  # 'repo' | 'cache' | 'download'


class DatasetError(Exception):
    """Unknown name, or a download/extract failed."""


def resolve_name(name: str) -> str:
    key = name.lower().strip()
    key = ALIASES.get(key, key)
    if key not in DATASETS:
        known = ', '.join(DATASETS)
        raise DatasetError(f"Unknown dataset {name!r}. Choose {known}.")
    return key


def cache_dir() -> str:
    xdg = os.environ.get('XDG_CACHE_HOME')
    root = os.path.join(xdg, 'mastidb') if xdg else os.path.join(
        os.path.expanduser('~'), '.cache', 'mastidb'
    )
    os.makedirs(root, exist_ok=True)
    return root


def ensure_source(name: str, force: bool = False, progress=None) -> SourceFile:
    name = resolve_name(name)
    if name == 'wikipedia':
        return _ensure_wikipedia(force, progress)
    return _ensure_menuitem(force, progress)


def human_bytes(num_bytes: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num_bytes < 1024 or unit == 'GB':
            return f'{num_bytes:.1f} {unit}'
        num_bytes /= 1024
    return f'{num_bytes:.1f} GB'


def _repo_file(*parts: str) -> str:
    return os.path.join(_REPO_ROOT, *parts)


def _menu_complete(directory: str) -> bool:
    return all(os.path.isfile(os.path.join(directory, name)) for name in MENU_FILES)


def _ensure_wikipedia(force: bool, progress) -> SourceFile:
    local = _repo_file('tests', 'datasets', 'wikipedia.json')
    if os.path.isfile(local):
        return SourceFile(local, 'repo')

    dest = os.path.join(cache_dir(), 'wikipedia.json')
    if os.path.isfile(dest) and not force:
        return SourceFile(dest, 'cache')

    try:
        _download(WIKIPEDIA_URL, dest, progress)
    except (urllib.error.URLError, OSError) as err:
        raise DatasetError(
            f'Failed to download wikipedia: {err}\n'
            f'You can also fetch it from {WIKIPEDIA_URL}'
        ) from err
    return SourceFile(dest, 'download')


def _ensure_menuitem(force: bool, progress) -> SourceFile:
    local_dir = _repo_file('tests', 'dataset_menu')
    if _menu_complete(local_dir) and not force:
        return SourceFile(os.path.join(local_dir, 'MenuItem.csv'), 'repo')

    cached = os.path.join(cache_dir(), 'menu')
    if _menu_complete(cached) and not force:
        return SourceFile(os.path.join(cached, 'MenuItem.csv'), 'cache')

    # Contributors: drop the CSVs where million_test.py already looks.
    dest_dir = local_dir if os.path.isdir(_repo_file('tests')) else cached
    os.makedirs(dest_dir, exist_ok=True)

    archive_fd, archive_path = tempfile.mkstemp(suffix='.tgz', dir=dest_dir)
    os.close(archive_fd)
    try:
        _download(MENU_URL, archive_path, progress)
        extracted = _extract_menu(archive_path, dest_dir)
    except KeyboardInterrupt:
        raise
    except (urllib.error.URLError, tarfile.TarError, OSError) as err:
        raise DatasetError(
            f'Failed to download menuitem: {err}\n'
            f'The dataset can also be downloaded by hand from {MENU_SOURCE_PAGE}'
        ) from err
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)

    missing = [name for name in MENU_FILES if name not in extracted]
    if missing:
        raise DatasetError(
            f"Archive did not contain {', '.join(missing)}. "
            f'See {MENU_SOURCE_PAGE}'
        )
    return SourceFile(os.path.join(dest_dir, 'MenuItem.csv'), 'download')


def _download(url: str, dest: str, progress) -> None:
    with urllib.request.urlopen(url) as response:  # noqa: S310 - fixed https URLs
        total = int(response.headers.get('Content-Length') or 0)
        if progress is not None:
            progress.start(url, total)
        downloaded = 0
        os.makedirs(os.path.dirname(os.path.abspath(dest)) or '.', exist_ok=True)
        with open(dest, 'wb') as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress.update(downloaded)
        if progress is not None:
            progress.done()


def _extract_menu(archive_path: str, dest: str) -> list[str]:
    extracted: list[str] = []
    with tarfile.open(archive_path, 'r:gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = os.path.basename(member.name)
            if name not in MENU_FILES:
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            out_path = os.path.join(dest, name)
            with source, open(out_path, 'wb') as out:
                shutil.copyfileobj(source, out, length=1024 * 1024)
            extracted.append(name)
    return extracted

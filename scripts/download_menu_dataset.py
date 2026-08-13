#!/usr/bin/env python3
"""Fetch the dataset the benchmarks run on.

The New York Public Library's "What's on the Menu?" dump — four CSVs, ~146 MB
extracted, of which `MenuItem.csv` (~1.3M rows) is what `tests/million_test.py`
ingests. Too big to keep in git, so it lives outside the repo and gets pulled
on demand.

    python scripts/download_menu_dataset.py

Already have the files? It says so and does nothing. Pass --force to refetch.

Only needs the standard library, so it works before you've installed anything.
"""

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

DATASET_URL = "https://s3.amazonaws.com/menusdata.nypl.org/gzips/2021_08_01_07_01_17_data.tgz"
SOURCE_PAGE = "http://menus.nypl.org/data"

WANTED = ('Dish.csv', 'Menu.csv', 'MenuItem.csv', 'MenuPage.csv')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEST = os.path.join(REPO_ROOT, 'tests', 'dataset_menu')


def human(num_bytes: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num_bytes < 1024 or unit == 'GB':
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def already_downloaded(dest: str) -> bool:
    return all(os.path.exists(os.path.join(dest, name)) for name in WANTED)


def download(url: str, target_path: str) -> None:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as response:  # noqa: S310 - fixed https URL
        total = int(response.headers.get('Content-Length') or 0)
        downloaded = 0
        with open(target_path, 'wb') as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  {human(downloaded)} / {human(total)}  ({pct}%)", end='', flush=True)
                else:
                    print(f"\r  {human(downloaded)}", end='', flush=True)
    print()


def extract(archive_path: str, dest: str) -> list[str]:
    """Pull the CSVs out, flattening any directory structure in the archive."""
    print(f"Extracting into {dest}")
    extracted = []
    with tarfile.open(archive_path, 'r:gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = os.path.basename(member.name)
            if name not in WANTED:
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            # Write by hand rather than tar.extract() so a crafted archive
            # can't place files outside dest.
            out_path = os.path.join(dest, name)
            with source, open(out_path, 'wb') as out:
                shutil.copyfileobj(source, out, length=1024 * 1024)
            print(f"  {name}  {human(os.path.getsize(out_path))}")
            extracted.append(name)
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dest', default=DEFAULT_DEST,
                        help=f"where to put the CSVs (default: {os.path.relpath(DEFAULT_DEST, REPO_ROOT)})")
    parser.add_argument('--force', action='store_true',
                        help="download again even if the CSVs are already there")
    args = parser.parse_args()

    dest = os.path.abspath(args.dest)
    os.makedirs(dest, exist_ok=True)

    if already_downloaded(dest) and not args.force:
        print(f"Dataset already present in {dest} — nothing to do.")
        print("Pass --force to download it again.")
        return 0

    archive_fd, archive_path = tempfile.mkstemp(suffix='.tgz', dir=dest)
    os.close(archive_fd)
    try:
        download(DATASET_URL, archive_path)
        extracted = extract(archive_path, dest)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except (urllib.error.URLError, tarfile.TarError, OSError) as err:
        print(f"\nFailed: {err}")
        print(f"The dataset can also be downloaded by hand from {SOURCE_PAGE}")
        return 1
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)

    missing = [name for name in WANTED if name not in extracted]
    if missing:
        print(f"Warning: archive did not contain {', '.join(missing)}")
        print("The archive layout may have changed; see " + SOURCE_PAGE)
        return 1

    print(f"\nDone. {len(extracted)} files in {dest}")
    print("Now build a table from it:")
    print("  python -c \"from mastidb import Table; "
          "Table.from_ingest_source('/tmp/menuitem', 'tests/dataset_menu/MenuItem.csv')\"")
    return 0


if __name__ == '__main__':
    sys.exit(main())

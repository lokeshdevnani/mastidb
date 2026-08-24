from __future__ import annotations

import logging
import os
import sys
import time

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table as RichTable

from .demo import DATASETS, DatasetError, SourceFile, ensure_source, human_bytes, resolve_name
from .table import Table

logging.basicConfig(level=logging.WARN, format='[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s')

console = Console(highlight=False)


def set_verbosity(ctx, param, value):
    """Set the logging level based on the verbosity option."""
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    logging.getLogger().setLevel(levels[min(len(levels) - 1, value)])


def _verbose(f):
    return click.option(
        '--verbose', '-v', count=True, callback=set_verbosity, expose_value=False, is_eager=True,
        help='More logs. Repeat for more detail (-v, -vv).',
    )(f)

_EXAMPLES = {
    'demo': [
        'mastidb demo',
        'mastidb demo wikipedia',
        'mastidb demo menuitem',
        'mastidb demo wikipedia -d /tmp/wikipedia',
    ],
    'console': [
        'mastidb console -d /tmp/wikipedia',
        'mastidb console --data-dir=/tmp/menuitem',
    ],
    'ingest': [
        'mastidb ingest -d ./mytable -s ./data.csv',
        'mastidb ingest -d ./mytable -s ./data.csv --segments 4',
    ],
    'query': [
        'mastidb query -d /tmp/wikipedia "SELECT COUNT(*)"',
        'mastidb query -d /tmp/menuitem "SELECT COUNT(id)"',
    ],
}


class MastidbCommand(click.Command):
    def format_help(self, ctx, formatter):
        _print_command_help(self, ctx)


class MastidbGroup(click.Group):
    def format_help(self, ctx, formatter):
        _print_root_help()

    def command(self, *args, **kwargs):
        kwargs.setdefault('cls', MastidbCommand)
        kwargs.setdefault('context_settings', {'help_option_names': ['-h', '--help']})
        return super().command(*args, **kwargs)


def _print_root_help():
    console.print()
    console.print("[bold magenta]MastiDB[/]  [dim]— a 'serious' OLAP engine written in Python[/]")
    console.print()
    console.print('[bold]Commands[/]')
    commands = RichTable(box=None, show_header=False, padding=(0, 2, 0, 2))
    commands.add_column('name', style='cyan', no_wrap=True)
    commands.add_column('help')
    commands.add_row('demo', 'Download a sample dataset and load it')
    commands.add_row('ingest', 'Load a CSV, TSV, or JSON file')
    commands.add_row('console', 'Interactive SQL prompt')
    commands.add_row('query', 'Run one SQL query and exit')
    console.print(commands)
    console.print()
    console.print('[bold]Try a demo[/]  [dim](no file of your own needed)[/]')
    console.print('  [cyan]mastidb demo wikipedia[/]     [dim]24k Wikipedia edits, small and fast[/]')
    console.print('  [cyan]mastidb demo menuitem[/]      [dim]1.3M NYPL menu items, the benchmark[/]')
    console.print()
    console.print('[bold]Then[/]')
    _cmd('mastidb console -d /tmp/wikipedia')
    _cmd('mastidb query -d /tmp/wikipedia "SELECT COUNT(*)"')
    console.print()
    console.print('[dim]-h, --help on any command for options and examples.[/]')
    console.print()


def _cmd(text: str) -> None:
    """Print a copy-pasteable command without wrapping it onto two lines."""
    console.print(f'  [cyan]{text}[/]', overflow='ignore', crop=False)


def _print_command_help(cmd: click.Command, ctx: click.Context):
    console.print()
    console.print(f"[bold magenta]{cmd.name}[/]  [dim]{cmd.get_short_help_str()}[/]")
    console.print()
    console.print('[bold]Usage[/]')
    usage = f'  [cyan]mastidb {cmd.name}[/] [dim]\\[OPTIONS][/]'
    for param in cmd.params:
        if isinstance(param, click.Argument):
            metavar = (param.metavar or param.name or 'ARG').upper()
            usage += f' [{metavar}]' if not param.required else f' {metavar}'
    console.print(usage)
    console.print()

    options = [p for p in cmd.params if isinstance(p, click.Option)]
    arguments = [p for p in cmd.params if isinstance(p, click.Argument)]
    if arguments:
        console.print('[bold]Arguments[/]')
        table = RichTable(box=None, show_header=False, padding=(0, 2, 0, 2))
        table.add_column('name', style='cyan', no_wrap=True)
        table.add_column('help')
        for param in arguments:
            table.add_row(
                (param.metavar or param.name or '').upper(),
                getattr(param, 'help', None) or _argument_help(cmd.name or '', param),
            )
        console.print(table)
        console.print()

    if options:
        console.print('[bold]Options[/]')
        table = RichTable(box=None, show_header=False, padding=(0, 2, 0, 2))
        table.add_column('flags', style='cyan', no_wrap=True)
        table.add_column('help')
        for param in options:
            flags = ', '.join(sorted(param.opts, key=lambda opt: (opt.startswith('--'), opt)))
            table.add_row(flags, _option_help(param))
        table.add_row('-h, --help', 'Show this message')
        console.print(table)
        console.print()

    examples = _EXAMPLES.get(cmd.name or '', [])
    if examples:
        console.print('[bold]Examples[/]')
        for example in examples:
            _cmd(example)
        console.print()

    if cmd.name in ('console', 'query', 'ingest'):
        console.print('[bold]No data yet?[/]')
        console.print('  [cyan]mastidb demo wikipedia[/]     [dim]# download + load a small sample[/]')
        console.print()


def _argument_help(command_name: str, param: click.Argument) -> str:
    if command_name == 'demo':
        return 'wikipedia or menuitem. Omit to list datasets.'
    if command_name == 'query':
        return 'SQL to run, in quotes.'
    return param.name or ''


def _option_help(param: click.Option) -> str:
    text = param.help or ''
    extras = []
    if param.required:
        extras.append('[yellow]required[/]')
    default = param.default
    if (
        default not in (None, False, '')
        and not param.count
        and not param.is_flag
        and not callable(default)
    ):
        extras.append(f'[dim]default: {default}[/]')
    if extras:
        text = f"{text}  {' '.join(extras)}" if text else ' '.join(extras)
    return text


def _die_no_table(data_dir: str) -> None:
    console.print(f'[red]No MastiDB table at[/] [cyan]{data_dir}[/]')
    console.print()
    console.print('[bold]Load a demo:[/]')
    console.print('  [cyan]mastidb demo wikipedia[/]     [dim]24k Wikipedia edits, small and fast[/]')
    console.print('  [cyan]mastidb demo menuitem[/]      [dim]1.3M NYPL menu items, the benchmark[/]')
    console.print()
    console.print('[bold]Or ingest your own file:[/]')
    console.print(f'  [cyan]mastidb ingest -d {data_dir} -s[/] [dim]path/to/file.csv[/]')
    sys.exit(1)


def _load_table(data_dir: str) -> Table:
    if not os.path.isdir(data_dir):
        _die_no_table(data_dir)
    try:
        return Table.from_data_dir(data_dir)
    except (ValueError, OSError):
        _die_no_table(data_dir)
        raise  # unreachable; keeps type-checkers happy


def _table_stats(table: Table) -> tuple[int, int, int]:
    rows = sum(segment.get_row_count() for segment in table.segments)
    cols = len(table.column_names())
    return rows, cols, len(table.segments)


def _stats_line(rows: int, cols: int, nseg: int) -> str:
    seg = 'segment' if nseg == 1 else 'segments'
    return f'{rows:,} rows  ·  {cols} columns  ·  {nseg} {seg}'


def _ingest(data_dir: str, source_file: str, segments: int) -> Table:
    console.print(f'Ingesting [cyan]{source_file}[/]  →  [cyan]{data_dir}[/]')
    t0 = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task('Building segments…', total=None)
        table = Table.from_ingest_source(data_dir, source_file, num_segments=segments)
    elapsed = time.time() - t0
    rows, cols, nseg = _table_stats(table)
    console.print(
        f'[green]✓[/] Ingested [bold]{rows:,}[/] rows, {cols} columns, '
        f'{nseg} {"segment" if nseg == 1 else "segments"}  [dim]in {elapsed:.2f}s[/]'
    )
    return table


def _print_next_steps(dataset_name: str, data_dir: str) -> None:
    meta = DATASETS[dataset_name]
    console.print()
    console.print('[bold]Open a prompt[/]')
    _cmd(f'mastidb console -d {data_dir}')
    console.print()
    console.print('[bold]Or run a query[/]')
    for sql in meta.queries:
        _cmd(f'mastidb query -d {data_dir} "{sql}"')
    console.print()


class _DownloadProgress:
    def __init__(self) -> None:
        self._progress: Progress | None = None
        self._task: int | None = None

    def start(self, url: str, total: int) -> None:
        console.print(f'Downloading [cyan]{url}[/]')
        self._progress = Progress(
            TextColumn('  '),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        )
        self._progress.start()
        self._task = self._progress.add_task('download', total=total or None)

    def update(self, downloaded: int) -> None:
        if self._progress is not None and self._task is not None:
            self._progress.update(self._task, completed=downloaded)

    def done(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None


def _announce_source(source: SourceFile) -> None:
    size = human_bytes(os.path.getsize(source.path)) if os.path.isfile(source.path) else ''
    if source.origin == 'repo':
        console.print(f'Using local [cyan]{source.path}[/]  [dim]{size}[/]')
    elif source.origin == 'cache':
        console.print(f'Using cached [cyan]{source.path}[/]  [dim]{size}[/]')
    else:
        console.print(f'Saved [cyan]{source.path}[/]  [dim]{size}[/]')


@click.group(cls=MastidbGroup, context_settings={'help_option_names': ['-h', '--help']})
def mastidb():
    """MastiDB CLI."""


@mastidb.command()
@click.argument('dataset', required=False)
@click.option('--data-dir', '-d', type=click.Path(), default=None,
              help='Where to write the table. Default: /tmp/<dataset>.')
@click.option('--segments', default=1, type=int, help='Split the file into this many segments.')
@click.option('--force', is_flag=True, help='Download and ingest again even if already present.')
@_verbose
def demo(dataset, data_dir, segments, force):
    """Download a sample dataset and load it."""
    if not dataset:
        _list_datasets()
        return

    try:
        name = resolve_name(dataset)
    except DatasetError as err:
        console.print(f'[red]{err}[/]')
        sys.exit(2)

    meta = DATASETS[name]
    dest = data_dir or meta.default_data_dir

    if not force and os.path.isdir(dest):
        try:
            table = Table.from_data_dir(dest)
        except (ValueError, OSError):
            table = None
        if table is not None:
            rows, cols, nseg = _table_stats(table)
            console.print(f'[green]✓[/] [bold]{name}[/] already loaded at [cyan]{dest}[/]')
            console.print(f'  {_stats_line(rows, cols, nseg)}')
            console.print('[dim]Pass --force to download and ingest again.[/]')
            _print_next_steps(name, dest)
            return

    try:
        source = ensure_source(name, force=force, progress=_DownloadProgress())
    except DatasetError as err:
        console.print(f'[red]{err}[/]')
        sys.exit(1)
    except KeyboardInterrupt:
        console.print('\n[yellow]Interrupted.[/]')
        sys.exit(130)

    _announce_source(source)
    _ingest(dest, source.path, segments)
    _print_next_steps(name, dest)


def _list_datasets():
    console.print()
    console.print('[bold magenta]Demo datasets[/]')
    console.print()
    table = RichTable(box=None, show_header=True, padding=(0, 2, 0, 0))
    table.add_column('Name', style='cyan', no_wrap=True)
    table.add_column('Rows', justify='right')
    table.add_column('Size', style='dim')
    table.add_column('What it is')
    for meta in DATASETS.values():
        tag = '  [green]start here[/]' if meta.starter else ''
        table.add_row(meta.name, meta.rows, meta.size, meta.blurb + tag)
    console.print(table)
    console.print()
    console.print('[bold]Load one[/]')
    console.print('  [cyan]mastidb demo wikipedia[/]     [dim]# small, good first try[/]')
    console.print('  [cyan]mastidb demo menuitem[/]      [dim]# the million-row set[/]')
    console.print()


@mastidb.command('console')
@click.option('--data-dir', '-d', required=True, type=click.Path(),
              help='Directory of an ingested table.')
@_verbose
def console_cmd(data_dir):
    """Interactive SQL prompt."""
    from .app import MastiDBConsole
    table = _load_table(data_dir)
    rows, cols, nseg = _table_stats(table)
    console.print(
        f'[dim]table[/] [cyan]{data_dir}[/]  [dim]{_stats_line(rows, cols, nseg)}[/]'
    )
    MastiDBConsole(table, data_dir).run()


@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(),
              help='Directory to write the table into.')
@click.option('--source-file', '-s', required=True, type=click.Path(exists=True),
              help='CSV, TSV, JSON, or ndJSON file to ingest.')
@click.option('--segments', default=1, type=int, help='Split the file into this many segments.')
@_verbose
def ingest(data_dir, source_file, segments):
    """Load a CSV, TSV, or JSON file."""
    _ingest(data_dir, source_file, segments)
    console.print()
    console.print('[bold]Next[/]')
    _cmd(f'mastidb console -d {data_dir}')
    _cmd(f'mastidb query -d {data_dir} "SELECT COUNT(*)"')
    console.print()


@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(),
              help='Directory of an ingested table.')
@click.argument('sql')
@_verbose
def query(data_dir, sql):
    """Run one SQL query and print the result."""
    from .app import MastiDBConsole
    table = _load_table(data_dir)
    MastiDBConsole(table, data_dir).print_results(sql)


if __name__ == '__main__':
    mastidb()

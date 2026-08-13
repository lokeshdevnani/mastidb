import logging
import time
import click
from .table import Table

logging.basicConfig(level=logging.WARN, format='[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s')

def set_verbosity(ctx, param, value):
    """ Set the logging level based on the verbosity option """
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    logging.getLogger().setLevel(levels[min(len(levels)-1, value)])


@click.group()
def mastidb():
    """
    MastiDB CLI - A command line interface for interacting with MastiDB.

    \b
    Examples:
    \b
      Launch the MastiDB console:
        mastidb console -d /path/to/data
        mastidb console --data-dir=/path/to/data
      
      \b
      Ingest a file into MastiDB:
        mastidb ingest -d /path/to/data -s /path/to/source/file.csv
        mastidb ingest --data-dir=/path/to/data --source-file=/path/to/source/file.csv

      \b
      Run a single query:
        mastidb query -d /path/to/data "SELECT COUNT(id)"
    """
    pass

@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(), help='Directory where data files are stored.')
@click.option('--verbose', '-v', count=True, callback=set_verbosity, expose_value=False, is_eager=True, help="Increase verbosity (can be used multiple times. Eg. -v, -vv, -vvv).")
def console(data_dir):
    """
    Launch the MastiDB console.

    \b
    Examples:
    \b
    mastidb console -d /path/to/data
    mastidb console --data-dir=/path/to/data
    """
    from .app import MastiDBConsole
    click.echo(f"Launching MastiDB console with data directory: {data_dir}")
    table = Table.from_data_dir(data_dir)
    MastiDBConsole(table, data_dir).run()
    # Logic for launching console

@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(), help='Directory where data files are stored.')
@click.option('--source-file', '-s', required=True, type=click.Path(exists=True), help='Path to source file to ingest (csv, tsv, json).')
@click.option('--segments', default=1, type=int, help='Split the file into this many segments.')
@click.option('--verbose', '-v', count=True, callback=set_verbosity, expose_value=False, is_eager=True, help="Increase verbosity (can be used multiple times. Eg. -v, -vv, -vvv).")
def ingest(data_dir, source_file, segments):
    """
    Ingest a file into MastiDB.

    \b
    Examples:
    \b
    mastidb ingest -d /path/to/data -s /path/to/source/file.csv
    mastidb ingest --data-dir=/path/to/data --source-file=/path/to/source/file.csv
    mastidb ingest -d /path/to/data -s /path/to/source/file.csv --segments 4
    """
    click.echo(f"Ingesting file {source_file} into data directory: {data_dir}")
    t0 = time.time()
    table = Table.from_ingest_source(data_dir, source_file, num_segments=segments)
    elapsed = time.time() - t0
    rows = sum(segment.get_row_count() for segment in table.segments)
    cols = len(table.column_names())
    click.echo("Ingested %d rows, %d columns, %d segment(s). Took %.2f seconds." % (
        rows, cols, len(table.segments), elapsed))
    # Logic for file ingestion

@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(), help='Directory where data files are stored.')
@click.argument('sql')
@click.option('--verbose', '-v', count=True, callback=set_verbosity, expose_value=False, is_eager=True, help="Increase verbosity (can be used multiple times. Eg. -v, -vv, -vvv).")
def query(data_dir, sql):
    """
    Run a SQL query and print the result.

    \b
    Examples:
    \b
    mastidb query -d /path/to/data "SELECT COUNT(id)"
    """
    from .app import MastiDBConsole
    table = Table.from_data_dir(data_dir)
    MastiDBConsole(table, data_dir).print_results(sql)

if __name__ == '__main__':
    mastidb()

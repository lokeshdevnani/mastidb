import logging
import click
from .segment import Segment

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
    segment = Segment.load(data_dir)
    MastiDBConsole(segment).run()
    # Logic for launching console

@mastidb.command()
@click.option('--data-dir', '-d', required=True, type=click.Path(), help='Directory where data files are stored.')
@click.option('--source-file', '-s', required=True, type=click.Path(exists=True), help='Path to source file to ingest (csv, tsv, json).')
@click.option('--verbose', '-v', count=True, callback=set_verbosity, expose_value=False, is_eager=True, help="Increase verbosity (can be used multiple times. Eg. -v, -vv, -vvv).")
def ingest(data_dir, source_file):
    """
    Ingest a file into MastiDB.

    \b
    Examples:
    \b
    mastidb ingest -d /path/to/data -s /path/to/source/file.csv
    mastidb ingest --data-dir=/path/to/data --source-file=/path/to/source/file.csv
    """
    click.echo(f"Ingesting file {source_file} into data directory: {data_dir}")
    Segment.create(data_dir, source_file)
    # Logic for file ingestion

if __name__ == '__main__':
    mastidb()
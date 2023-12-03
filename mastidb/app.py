#!/Library/Frameworks/Python.framework/Versions/3.9/bin/python3

import time
from mo_parsing import ParseException # type: ignore
from pygments.lexers.sql import SqlLexer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, TextColumn
from rich.table import Table
from rich import print
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from parse_helpers import ParsedQuery
from segment import Segment
from segment_query_processor import SegmentQueryProcessor
from result_set import ResultSet
import logging

class MastiDBConsole:
    def __init__(self, segment):
        self.console = Console()
        self.segment = segment
        self.sql_completer = WordCompleter([
            'select', 'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having'
            'and', 'or', '=', 'in',
            'asc', 'desc',
            'current_date', 'current_time', 'current_timestamp',
            'count', 'sum', 'distinct',
        ], ignore_case=True)
        self.style = Style.from_dict({
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'scrollbar.background': 'bg:#88aaaa',
            'scrollbar.button': 'bg:#222222',
        })

    def run(self):
        session = PromptSession(lexer=PygmentsLexer(SqlLexer), completer=self.sql_completer, style=self.style)
        while True:
            try:
                sql = session.prompt('MastiDB > ')
                self.print_results(sql)
            except ParseException as e:
                print(":x:  Oh no, your query is giving the database a headache. ")
                print(e)
            except NotImplementedError as e:
                print(":eyes:  Whoopsie! This feature is still in the land of unicorns and rainbows. "
                      "Send a PR to bring it back to reality!")
                print(e)
            except EOFError:  # Control-D pressed.
                break
            except ValueError as e:
                print(":interrobang:  The database is scratching its head, "
                      "trying to understand your values. :man_gesturing_no:")
                print(e)
            except KeyboardInterrupt:
                print(":zzz:  Someone pulled the plug on the database. ")
                exit(0)
            except Exception as e:
                print(":x:  Uh-oh, something went wrong. Remember, even databases have their clumsy days!")
                print(e.error_message)
        print('GoodBye!')

    def print_results(self, sql):
        with Progress(
                SpinnerColumn("monkey"),
                *Progress.get_default_columns(),
                TimeElapsedColumn(),
                console=self.console,
                transient=True,
        ) as progress:
            task = progress.add_task("[green] Crunching data", total=None)
            result_set, time_total, time_cpu = self.get_results(sql)
            row_count = len(result_set.get_results())

        console_table = self.build_console_table(result_set)
        if row_count < 50:
            self.console.print(console_table, justify="center")
        else:
            with self.console.pager(styles=True):
                self.console.print(console_table, justify="center")
        self.console.print(f"Fetched %d rows. Took %.2f seconds. CPU time %.2f" % (row_count, time_total, time_cpu))

    def build_console_table(self, result_set: ResultSet):
        table = Table(title="MastiDB")
        colors = ["magenta", "cyan", "yellow", "red"]
        for i, col in enumerate(result_set.columns):
            table.add_column(col, no_wrap=False, style=colors[i % len(colors)])

        results = result_set.get_results()
        for i in range(0, min(len(results), 1000)):
            result = results[i]
            result_row_str: list[str] = [str(item) for item in result]
            table.add_row(*result_row_str)

        return table

    def get_results(self, sql):
        t0_total, t0_cpu = time.time(), time.process_time()
        parsed_query = ParsedQuery.parse_from_sql(sql)
        qp = SegmentQueryProcessor(self.segment, parsed_query)
        results = qp.process_query()
        time_total, time_cpu = time.time() - t0_total, time.process_time() - t0_cpu
        return results, time_total, time_cpu


if __name__ == '__main__':
    segment = Segment.load('/tmp/menuitem')
    MastiDBConsole(segment).run()
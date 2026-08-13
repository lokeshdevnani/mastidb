#!/Library/Frameworks/Python.framework/Versions/3.9/bin/python3

import os
import time
from .query_executor import QueryExecutor
from mo_parsing import ParseException # type: ignore
from pygments.lexers.sql import SqlLexer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, TextColumn
from rich.table import Table as RichTable
from rich import print
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
import traceback
from .table import Table
from .result_set import ResultSet

SQL_KEYWORDS = [
    'select', 'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
    'and', 'or', '=', 'in',
    'asc', 'desc',
    'current_date', 'current_time', 'current_timestamp',
    'count', 'sum', 'avg', 'distinct',
]

# Last keyword before the cursor decides what to float to the top.
_COLUMN_HINTS = {
    'select', 'where', 'and', 'or', 'by', 'group', 'order', 'having',
    'count', 'sum', 'avg', 'distinct', 'as',
}


class SqlCompleter(Completer):
    """Keywords, the table name, and columns — tagged so the menu can tell them apart."""

    def __init__(self, columns: list[str], table_name: str = ''):
        self.columns = columns
        self.table_name = table_name

    def get_completions(self, document: Document, complete_event):
        word = document.get_word_before_cursor()
        prefix = word.lower()
        before_word = document.text_before_cursor[:-len(word)] if word else document.text_before_cursor
        hint = self._hint(before_word)

        scored: list[tuple[int, Completion]] = []
        if self.table_name and self.table_name.lower().startswith(prefix):
            scored.append((0 if hint == 'from' else 2, Completion(
                self.table_name,
                start_position=-len(word),
                display_meta='table',
                style='fg:#ff87d7',
            )))
        for column in self.columns:
            if column.lower().startswith(prefix):
                scored.append((0 if hint == 'column' else 1, Completion(
                    column,
                    start_position=-len(word),
                    display_meta='column',
                    style='fg:#87ffff',
                )))
        for keyword in SQL_KEYWORDS:
            if keyword.lower().startswith(prefix):
                scored.append((3, Completion(
                    keyword,
                    start_position=-len(word),
                    display_meta='keyword',
                )))

        seen: set[str] = set()
        for _, completion in sorted(scored, key=lambda item: (item[0], item[1].text.lower())):
            key = completion.text.lower()
            if key in seen:
                continue
            seen.add(key)
            yield completion

    def _hint(self, text_before_cursor: str) -> str:
        tokens = text_before_cursor.lower().replace(',', ' ').split()
        for token in reversed(tokens):
            if token == 'from':
                return 'from'
            if token in _COLUMN_HINTS:
                return 'column'
        return ''


def _console_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add('enter', eager=True)
    def _enter(event):
        buf = event.current_buffer
        state = buf.complete_state
        if state and state.completions:
            buf.apply_completion(state.current_completion or state.completions[0])
            return
        buf.validate_and_handle()

    @kb.add('c-c', eager=True)
    def _ctrl_c(event):
        buf = event.current_buffer
        if buf.text:
            buf.reset()
            return
        event.app.exit(exception=KeyboardInterrupt)

    return kb


class MastiDBConsole:
    def __init__(self, table: Table, data_dir: str = ''):
        self.console = Console()
        self.table = table
        table_name = os.path.basename(os.path.normpath(data_dir)) if data_dir else ''
        self.sql_completer = SqlCompleter(table.column_names(), table_name)
        self.style = Style.from_dict({
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'completion-menu.meta.completion': 'bg:#008888 #eeeeee',
            'completion-menu.meta.completion.current': 'bg:#00aaaa #000000',
            'scrollbar.background': 'bg:#88aaaa',
            'scrollbar.button': 'bg:#222222',
        })

    def run(self):
        session = PromptSession(
            lexer=PygmentsLexer(SqlLexer),
            completer=self.sql_completer,
            style=self.style,
            key_bindings=_console_key_bindings(),
        )
        while True:
            try:
                sql = session.prompt('MastiDB > ')
                if not sql.strip():
                    continue
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
                print(f":x:  Uh-oh, something went wrong. Remember, even databases have their clumsy days! {e}")
                print(traceback.format_exc())
        print('GoodBye!')

    def print_results(self, sql: str):
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

    def build_console_table(self, result_set: ResultSet) -> RichTable:
        table = RichTable(title="MastiDB")
        colors = ["magenta", "cyan", "yellow", "red"]
        for i, col in enumerate(result_set.columns):
            table.add_column(col, no_wrap=False, style=colors[i % len(colors)])

        results = result_set.get_results()
        for i in range(0, min(len(results), 1000)):
            result = results[i]
            result_row_str: list[str] = [str(item) for item in result]
            table.add_row(*result_row_str)

        return table

    def get_results(self, sql: str):
        t0_total, t0_cpu = time.time(), time.process_time()
        results = QueryExecutor(self.table).execute(sql)
        time_total, time_cpu = time.time() - t0_total, time.process_time() - t0_cpu
        return results, time_total, time_cpu

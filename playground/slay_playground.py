"""Glue between the playground page and the slaython package.

The page loads this module inside Pyodide and calls run() and translate().
It also works under normal Python, which is how it gets tested.
"""

import builtins
import io
import linecache
import sys
import types

from slaython import transpile
from slaython.runner import compile_slay, print_error

FILENAME = "main.slay"


def _reopen_stdin():
    # exit() / touchgrass() closes sys.stdin; reopen fd 0 so hmu() works next run.
    if sys.stdin is None or sys.stdin.closed:
        sys.stdin = open(0, "r", encoding="utf-8", closefd=False)


def _report(exc, file=None):
    """Print exc the Slaython way, hiding this module's own frames."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
        tb = tb.tb_next
    print_error(exc.with_traceback(tb), file=file or sys.stderr)


def _flush():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:  # noqa: BLE001 - a closed or odd stream is not worth an error
            pass


def run(source):
    """Run Slaython source as __main__.

    Returns [exit_code, exited], where exited is True when the program
    stopped itself with touchgrass() / exit().
    """
    _reopen_stdin()
    # Cache the source under a file-like name so tracebacks show the lines.
    linecache.cache[FILENAME] = (len(source), None, io.StringIO(source).readlines(), FILENAME)
    try:
        code = compile_slay(source, FILENAME)
    except Exception as exc:  # noqa: BLE001 - SyntaxError, mostly
        _report(exc)
        _flush()
        return [1, False]

    main = types.ModuleType("__main__")
    main.__builtins__ = builtins
    saved_main = sys.modules.get("__main__")
    sys.modules["__main__"] = main
    try:
        exec(code, main.__dict__)
    except SystemExit as exc:
        status = exc.code
        if status is None:
            return [0, True]
        if isinstance(status, int):
            return [status, True]
        print(status, file=sys.stderr)
        return [1, True]
    except BaseException as exc:  # noqa: BLE001 - report everything, like python does
        _report(exc)
        return [1, False]
    finally:
        if saved_main is not None:
            sys.modules["__main__"] = saved_main
        _flush()
    return [0, False]


def translate(source):
    """Return [ok, text]: the Python version of source, or the error."""
    try:
        return [True, transpile(source, FILENAME)]
    except Exception as exc:  # noqa: BLE001
        buf = io.StringIO()
        _report(exc, buf)
        return [False, buf.getvalue()]

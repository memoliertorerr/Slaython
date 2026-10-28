"""Compile and run Slaython code: files, strings, and error reporting."""

import io
import itertools
import linecache
import os
import sys
import tokenize
import traceback
import types

from .importer import install
from .compiler import compile_source
from .transpiler import EDITS_BY_FILE, IncompleteSource, python_col_to_slang
from .vibes import vibe_for

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_counter = itertools.count(1)


def compile_slay(source, filename="<slay>", mode="exec"):
    """Compile Slaython source to a Python code object."""
    if filename.startswith("<"):
        # Keep the slang source around so tracebacks can show it.
        lines = io.StringIO(source).readlines()
        linecache.cache[filename] = (len(source), None, lines, filename)
    return compile_source(source, filename, mode)


def _caller_namespaces(globals_, locals_):
    if globals_ is None:
        frame = sys._getframe(2)
        globals_ = frame.f_globals
        if locals_ is None:
            locals_ = frame.f_locals
    return globals_, locals_


def slay(source, globals=None, locals=None):
    """Run Slaython code from Python, in the caller's namespace by default.

        from slaython import slay
        slay('yap("hello from slaython")')
    """
    g, l = _caller_namespaces(globals, locals)
    exec(compile_slay(source, f"<slay-{next(_counter)}>"), g, l)


def slay_eval(source, globals=None, locals=None):
    """Evaluate a Slaython expression and return its value."""
    g, l = _caller_namespaces(globals, locals)
    return eval(compile_slay(source.strip(), f"<slay-{next(_counter)}>", "eval"), g, l)


def read_source(path):
    """Read a source file, honouring any coding cookie."""
    if path == "-":
        return sys.stdin.read()
    # Read the bytes once (pipes like /dev/stdin can't be rewound), then
    # decode the way Python does for .py files.
    with open(path, "rb") as f:
        data = f.read()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return io.TextIOWrapper(io.BytesIO(data), encoding=encoding).read()


def print_error(exc, file=None):
    """Print a traceback without Slaython's own frames, then a vibe line."""
    file = file or sys.stderr
    if isinstance(exc, IncompleteSource):  # unfinished code is just a syntax error here
        plain = SyntaxError(exc.msg, (exc.filename, exc.lineno, exc.offset, exc.text))
        plain.__traceback__ = exc.__traceback__
        exc = plain
    tb = exc.__traceback__
    while tb is not None and os.path.dirname(
            os.path.abspath(tb.tb_frame.f_code.co_filename)) == _PACKAGE_DIR:
        tb = tb.tb_next
    te = traceback.TracebackException(type(exc), exc, tb)
    _map_columns(te)
    file.write("".join(te.format()))
    _write_vibe(exc, file)


def _write_vibe(exc, file=None):
    line = vibe_for(exc)
    if line:
        (file or sys.stderr).write(line + "\n")


def _map_columns(te, seen=None):
    """Move traceback carets from Python columns to Slaython columns."""
    seen = set() if seen is None else seen
    if te is None or id(te) in seen:
        return
    seen.add(id(te))
    for fs in te.stack:
        edits = EDITS_BY_FILE.get(fs.filename)
        if not edits or getattr(fs, "colno", None) is None:
            continue
        if fs.lineno is not None:
            fs.colno = python_col_to_slang(edits, fs.lineno, fs.colno)
        if fs.end_colno is not None and fs.end_lineno is not None:
            fs.end_colno = python_col_to_slang(edits, fs.end_lineno, fs.end_colno)
    _map_columns(te.__cause__, seen)
    _map_columns(te.__context__, seen)
    for sub in getattr(te, "exceptions", None) or ():
        _map_columns(sub, seen)


def run_file(path, argv=()):
    """Run a .slay file as __main__. Returns an exit code."""
    install()
    from_stdin = path == "-"
    path = "<stdin>" if from_stdin else os.path.abspath(path)
    try:
        source = read_source("-" if from_stdin else path)
    except OSError as exc:
        sys.stderr.write(f"slaython: can't open file {path!r}: {exc.strerror or exc}\n")
        _write_vibe(exc)
        return 2
    try:
        code = compile_slay(source, path)
    except SyntaxError as exc:
        print_error(exc)
        return 1
    main = types.ModuleType("__main__")
    if not from_stdin:
        main.__file__ = path
    main.__builtins__ = __builtins__
    sys.modules["__main__"] = main
    sys.argv = ["-" if from_stdin else path, *argv]
    sys.path.insert(0, "" if from_stdin else os.path.dirname(path))
    try:
        exec(code, main.__dict__)
    except SystemExit:
        raise
    except KeyboardInterrupt as exc:
        sys.stderr.write("\n")
        _write_vibe(exc)
        return 130
    except BaseException as exc:  # noqa: BLE001 - report everything, like python does
        print_error(exc)
        return 1
    return 0

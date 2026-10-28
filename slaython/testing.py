"""`slaython test`: run test functions in test_*.slay / *_test.slay files.

Every module-level function whose name starts with `test` is a test, and so
is every `test*` method of a blueprint (class) whose name starts with `Test`.
Async (lowkey) tests run with asyncio. A test passes (W) if it returns,
and fails (L) if it raises; ongod (assert) is the usual way to check things.
"""

import asyncio
import importlib.util
import inspect
import os
import sys
import time
import traceback

from .importer import SlayLoader, install
from .vibes import vibe_for


def find_test_files(paths):
    found = []
    for path in paths or ["."]:
        if os.path.isfile(path):
            found.append(os.path.abspath(path))
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
            for name in sorted(files):
                if name.endswith(".slay") and (name.startswith("test_") or name.endswith("_test.slay")):
                    found.append(os.path.abspath(os.path.join(root, name)))
    return found


def _display_path(path):
    rel = os.path.relpath(path)
    return path if rel.startswith("..") else rel


def _load(path):
    directory = os.path.dirname(path)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    name = os.path.splitext(os.path.basename(path))[0]
    loader = SlayLoader(name, path)
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def _collect(module):
    tests = []
    for name, obj in vars(module).items():
        if name.startswith("test") and inspect.isfunction(obj) and obj.__module__ == module.__name__:
            tests.append((name, obj))
        elif name.startswith("Test") and inspect.isclass(obj) and obj.__module__ == module.__name__:
            for meth_name, meth in vars(obj).items():
                if meth_name.startswith("test") and inspect.isfunction(meth):
                    tests.append((f"{name}.{meth_name}", _bound(obj, meth_name)))
    return tests


def _bound(cls, meth_name):
    def run():
        return getattr(cls(), meth_name)()
    return run


def _run_one(func):
    result = func()
    if inspect.isawaitable(result):
        asyncio.run(result)


def _short(exc):
    text = str(exc) or type(exc).__name__
    if isinstance(exc, AssertionError):
        return f"ongod failed: {text}" if str(exc) else "ongod failed"
    return f"{type(exc).__name__}: {text}"


def run_tests(paths=(), verbose=False, out=None):
    """Run the tests and return an exit code (0 = all W)."""
    out = out or sys.stdout
    install()
    files = find_test_files(list(paths))
    if not files:
        out.write("no test files found (looking for test_*.slay or *_test.slay)\n")
        return 5
    wins = losses = 0
    started = time.perf_counter()
    for path in files:
        rel = _display_path(path)
        try:
            module = _load(path)
        except Exception as exc:  # noqa: BLE001 - a broken file is one L
            losses += 1
            out.write(f"L {rel}: couldn't load: {_short(exc)}\n")
            if verbose:
                out.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            continue
        for name, func in _collect(module):
            try:
                _run_one(func)
            except Exception as exc:  # noqa: BLE001
                losses += 1
                out.write(f"L {rel}::{name}: {_short(exc)}\n")
                if verbose:
                    out.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                    vibe = vibe_for(exc)
                    if vibe:
                        out.write(vibe + "\n")
            else:
                wins += 1
                out.write(f"W {rel}::{name}\n")
    took = time.perf_counter() - started
    total = wins + losses
    if total == 0:
        out.write("found test files but no test functions\n")
        return 5
    verdict = "all W, no cap" if losses == 0 else "took some Ls"
    out.write(f"\n{wins} W, {losses} L in {took:.2f}s: {verdict}\n")
    return 0 if losses == 0 else 1

"""`slaython test`: run test functions in test_*.slay / *_test.slay files.

Every module-level function whose name starts with `test` is a test, and so
is every `test*` method of a blueprint (class) whose name starts with `Test`.
`vibecheck "name":` blocks count too, in any .slay file.
Async (lowkey) tests run with asyncio. A test passes (W) if it returns,
and fails (L) if it raises; ongod (assert) is the usual way to check things.
"""

import asyncio
import importlib.util
import inspect
import os
import re
import sys
import time
import traceback

from .importer import SlayLoader, install
from .keywords import INLINE_TEST_WORD
from .vibes import vibe_for


_INLINE = re.compile(r"^[ \t]*" + INLINE_TEST_WORD + r"\s+[rRbBuUfF]*[\"']", re.M)
_INLINE_PREFIX = "test_vibecheck_"


def _is_test_file(name):
    return name.startswith("test_") or name.endswith("_test.slay")


def _has_inline_tests(path):
    try:
        with open(path, encoding="utf-8") as f:
            return bool(_INLINE.search(f.read()))
    except (OSError, UnicodeDecodeError):
        return False


def find_test_files(paths):
    """[(path, inline_only)]: test files, plus other files with vibecheck blocks."""
    found = []
    for path in paths or ["."]:
        if os.path.isfile(path):
            found.append((os.path.abspath(path), not _is_test_file(os.path.basename(path))))
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
            for name in sorted(files):
                if not name.endswith(".slay"):
                    continue
                full = os.path.abspath(os.path.join(root, name))
                if _is_test_file(name):
                    found.append((full, False))
                elif _has_inline_tests(full):
                    found.append((full, True))
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


def _label(name, func):
    if name.startswith(_INLINE_PREFIX) and func.__defaults__:
        return f"{INLINE_TEST_WORD} {func.__defaults__[0]!r}"
    return name


def _collect(module, inline_only=False):
    tests = []
    for name, obj in vars(module).items():
        if inline_only and not name.startswith(_INLINE_PREFIX):
            continue
        if name.startswith("test") and inspect.isfunction(obj) and obj.__module__ == module.__name__:
            tests.append((_label(name, obj), obj))
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
        out.write("no tests found (looking for test_*.slay, *_test.slay and vibecheck blocks)\n")
        return 5
    wins = losses = 0
    started = time.perf_counter()
    for path, inline_only in files:
        rel = _display_path(path)
        try:
            module = _load(path)
        except Exception as exc:  # noqa: BLE001 - a broken file is one L
            losses += 1
            out.write(f"L {rel}: couldn't load: {_short(exc)}\n")
            if verbose:
                out.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            continue
        for name, func in _collect(module, inline_only):
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

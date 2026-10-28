"""Project words: extra slang a project adds in its pyproject.toml.

    [tool.slaython.words]
    frfr = "if"          # a Python keyword or builtin...
    vibe = "doomscroll"  # ...or an existing Slaython word

The new words work alongside the built-in ones, in every .slay file under
the folder that holds that pyproject.toml. Code typed in the REPL or with
-c uses the pyproject.toml of the current folder (or a parent folder).
"""

import keyword
import os
import re

from .keywords import ALL_SLANG_WORDS, COMPOUND_SLANG, PY_TO_SLANG

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_cache = {}  # pyproject path -> (mtime, words)


def words_for(filename):
    """Project words for a source file: {new word: built-in Slaython word}."""
    path = find_pyproject(filename)
    if path is None:
        return {}
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return {}
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    words = load_words(path)
    _cache[path] = (mtime, words)
    return words


def find_pyproject(filename):
    if filename and not filename.startswith("<"):
        start = os.path.dirname(os.path.abspath(filename))
    else:
        start = os.getcwd()
    here = start
    while True:
        candidate = os.path.join(here, "pyproject.toml")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def load_words(path):
    with open(path, "rb") as f:
        raw = f.read()
    table = _read_words_table(raw.decode("utf-8"), path)
    words = {}
    for new, target in table.items():
        words[new] = _resolve(new, target, path)
    return words


def _resolve(new, target, path):
    def fail(why):
        return SyntaxError(f"[tool.slaython.words] {new} = {target!r}: {why}", (path, None, None, None))

    if not isinstance(target, str):
        raise fail("the value has to be a string")
    if not _IDENT.match(new):
        raise fail(f"{new!r} isn't a valid name")
    if keyword.iskeyword(new) or new in ALL_SLANG_WORDS:
        raise fail(f"{new!r} is already a word, pick a new one")
    target = " ".join(target.split())
    if target in ALL_SLANG_WORDS or tuple(target.split()) in COMPOUND_SLANG:
        return target
    if target in PY_TO_SLANG:
        return PY_TO_SLANG[target]
    raise fail("not a Slaython word or a Python keyword/builtin that Slaython knows")


def _read_words_table(text, path):
    """The [tool.slaython.words] table as a dict."""
    try:
        import tomllib
    except ImportError:  # Python 3.10
        return _simple_table(text, "tool.slaython.words", path)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise SyntaxError(f"can't read {path}: {exc}", (path, None, None, None)) from None
    return data.get("tool", {}).get("slaython", {}).get("words", {}) or {}


_LINE = re.compile(r'^(?:([A-Za-z0-9_-]+)|"([^"]*)")\s*=\s*"([^"]*)"\s*(?:#.*)?$')


def _simple_table(text, name, path="pyproject.toml"):
    """Read `key = "value"` lines from one TOML table (enough for this table)."""
    out, inside = {}, False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("["):
            inside = line.split("#", 1)[0].strip().strip("[] \t") == name
            continue
        if not inside or not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            raise SyntaxError(f"[{name}] line {number}: use `newword = \"target\"` lines",
                              (path, number, None, None))
        out[m.group(1) if m.group(1) is not None else m.group(2)] = m.group(3)
    return out

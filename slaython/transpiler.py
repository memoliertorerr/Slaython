"""Translate between Slaython and Python, one token at a time.

Only NAME tokens are touched, and each edit stays on its own line, so the
translated code keeps the original line numbers. That is what makes
tracebacks point at the right line of your .slay file.

Plain Python keywords keep working in Slaython, so any Python file is
already valid Slaython.
"""

import io
import tokenize
from typing import Dict, List, NamedTuple, Tuple

from .keywords import (
    ALL_SLANG_WORDS,
    COMPOUND_SLANG,
    PY_TO_SLANG,
    SLANG_TO_PY,
    SOFT_PY,
    SOFT_SLANG,
)

_IGNORED = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.INDENT, tokenize.DEDENT)
# After these, a soft keyword is not a keyword (e.g. `spill = 3`, `match.group`).
_SOFT_BLOCKERS = {"=", ".", ":", ",", ")", "]", "}", ";"}


class IncompleteSource(SyntaxError):
    """The source ends in the middle of a statement (open bracket or string)."""


class Edit(NamedTuple):
    row: int
    start: int
    end: int
    text: str


class Collision(NamedTuple):
    """A Python name that would turn into a keyword after slayify."""
    row: int
    col: int
    name: str


def _tokenize(source: str, filename: str) -> List[tokenize.TokenInfo]:
    try:
        return list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        msg = exc.args[0]
        lineno, col = exc.args[1] if len(exc.args) > 1 else (1, 0)
        cls = IncompleteSource if "EOF" in msg else SyntaxError
        raise cls(msg, (filename, lineno, col + 1, None)) from None


def _logical_lines(sig: List[tokenize.TokenInfo]) -> List[Tuple[int, int]]:
    """(first, last) index of significant tokens on each logical line."""
    spans, start = [], None
    for i, tok in enumerate(sig):
        if tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            if start is not None:
                spans.append((start, i - 1))
            start = None
        elif start is None:
            start = i
    if start is not None:
        spans.append((start, len(sig) - 1))
    return spans


def _plan(source, filename, table, soft, compounds):
    """Work out which tokens to rewrite.

    Returns (edits, names_left_alone). The second list holds NAME tokens in
    keyword-capable positions that were not rewritten (used to spot clashes).
    """
    sig = [t for t in _tokenize(source, filename) if t.type not in _IGNORED]
    line_of = {}
    for first, last in _logical_lines(sig):
        for i in range(first, last + 1):
            line_of[i] = (first, last)

    def is_op(i, *ops):
        return 0 <= i < len(sig) and sig[i].type == tokenize.OP and sig[i].string in ops

    def name_at(i):
        if 0 <= i < len(sig) and sig[i].type == tokenize.NAME:
            return sig[i].string
        return None

    def plain_name_position(i):
        # `obj.cap` is an attribute and `f(drop=1)` is a keyword argument:
        # neither can ever be a keyword, so leave the name alone.
        return is_op(i - 1, ".") or is_op(i + 1, "=")

    def soft_ok(i):
        # `spill x:` / `pov 1: ...` must start the line and have a ':' outside
        # any brackets later on the line.
        first, last = line_of.get(i, (None, None))
        if i != first or i + 1 > last:
            return False
        nxt = sig[i + 1]
        if nxt.type == tokenize.OP and nxt.string in _SOFT_BLOCKERS:
            return False
        depth = 0
        for tok in sig[i + 1:last + 1]:
            if tok.type != tokenize.OP:
                continue
            if tok.string in ("(", "[", "{"):
                depth += 1
            elif tok.string in (")", "]", "}"):
                depth -= 1
            elif tok.string == ":" and depth == 0:
                return True
        return False

    edits, untouched = [], []
    skip_next = False
    for i, tok in enumerate(sig):
        if skip_next:
            skip_next = False
            continue
        if tok.type != tokenize.NAME:
            continue
        word = tok.string
        nxt = name_at(i + 1)
        pair = (word, nxt)
        if (pair in compounds and sig[i + 1].start[0] == tok.end[0]
                and not plain_name_position(i) and not is_op(i + 2, "=")):
            edits.append(Edit(tok.start[0], tok.start[1], sig[i + 1].end[1], compounds[pair]))
            skip_next = True
            continue
        if plain_name_position(i):
            continue
        if word in table and (word not in soft or soft_ok(i)):
            edits.append(Edit(tok.start[0], tok.start[1], tok.end[1], table[word]))
            continue
        untouched.append(tok)
    return edits, untouched


def _apply(source: str, edits: List[Edit]) -> str:
    lines = io.StringIO(source).readlines()
    for e in sorted(edits, key=lambda e: (e.row, e.start), reverse=True):
        line = lines[e.row - 1]
        lines[e.row - 1] = line[:e.start] + e.text + line[e.end:]
    return "".join(lines)


def transpile(source: str, filename: str = "<slay>") -> str:
    """Turn Slaython source into Python source (same line numbers)."""
    return transpile_with_edits(source, filename)[0]


# filename -> edits made to it, so tracebacks can map columns back to slang.
EDITS_BY_FILE: Dict[str, List[Edit]] = {}


def transpile_with_edits(source: str, filename: str = "<slay>") -> Tuple[str, List[Edit]]:
    """Like transpile(), but also return the edits so columns can be mapped back."""
    edits, _ = _plan(source, filename, SLANG_TO_PY, SOFT_SLANG, COMPOUND_SLANG)
    EDITS_BY_FILE[filename] = edits
    return _apply(source, edits), edits


def python_col_to_slang(edits: List[Edit], row: int, col: int) -> int:
    """Map a 0-based column in translated Python back to the Slaython line."""
    shift = 0
    for e in sorted(e for e in edits if e.row == row):
        py_start = e.start + shift
        py_end = py_start + len(e.text)
        if col < py_start:
            break
        if col < py_end:  # inside a rewritten word: point at its start
            return e.start
        shift += len(e.text) - (e.end - e.start)
    return col - shift




def slayify_with_report(source: str, filename: str = "<python>") -> Tuple[str, List[Collision]]:
    """Turn Python source into Slaython and report names that would clash.

    A clash is a Python name that is also a Slaython keyword, such as a
    variable called ``drop``: it would be read back as ``yield``. Rename
    those before running the result.
    """
    edits, untouched = _plan(source, filename, PY_TO_SLANG, SOFT_PY, {})
    collisions = []
    for tok in untouched:
        if tok.string in ALL_SLANG_WORDS:
            collisions.append(Collision(tok.start[0], tok.start[1], tok.string))
    return _apply(source, edits), collisions


def slayify(source: str, filename: str = "<python>") -> str:
    """Turn Python source into Slaython source."""
    return slayify_with_report(source, filename)[0]

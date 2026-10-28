"""Translate between Slaython and Python, one token at a time.

Edits never add or remove line breaks, so the translated code keeps the
original line numbers. That is what makes tracebacks point at the right
line of your .slay file.

Plain Python keywords keep working in Slaython, so any Python file is
already valid Slaython.
"""

import io
import tokenize
from typing import Dict, List, NamedTuple, Tuple

from .keywords import (
    ALL_SLANG_WORDS,
    COMPOUND_SLANG,
    CONST_WORD,
    HELPERS,
    PY_TO_SLANG,
    REPEAT_WORD,
    SLANG_TO_PY,
    SOFT_PY,
    SOFT_SLANG,
    SUS_WORD,
)

_IGNORED = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.INDENT, tokenize.DEDENT)
# After these, a soft keyword is not a keyword (e.g. `spill = 3`, `match.group`).
_SOFT_BLOCKERS = {"=", ".", ":", ",", ")", "]", "}", ";"}
_ASSIGN_OPS = {"=", ":", "+=", "-=", "*=", "/=", "//=", "%=", "**=", ">>=", "<<=", "&=", "^=", "|=", "@="}
_FSTRING_START = getattr(tokenize, "FSTRING_START", None)
_FSTRING_END = getattr(tokenize, "FSTRING_END", None)


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


def _gap_end(tok, nxt):
    """End column of `tok` plus the spaces after it, if `nxt` is on the same line."""
    return nxt.start[1] if nxt.start[0] == tok.end[0] else tok.end[1]


def _syntax_error(msg, filename, tok, source):
    lines = io.StringIO(source).readlines()
    text = lines[tok.start[0] - 1] if tok.start[0] <= len(lines) else None
    return SyntaxError(msg, (filename, tok.start[0], tok.start[1] + 1, text))


def _plan(source, filename, table, soft, compounds, forward=False):
    """Work out which tokens to rewrite.

    Returns (edits, names_left_alone). The second list holds NAME tokens in
    keyword-capable positions that were not rewritten (used to spot clashes).
    `forward` turns on Slaython-only syntax (helpers, runitfoo, deadass,
    yeet "message").
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

    def statement_colon(i):
        """Index of the ':' that ends the statement starting at i, or None."""
        first, last = line_of.get(i, (None, None))
        if i != first:
            return None
        depth = 0
        for j in range(i + 1, last + 1):
            tok = sig[j]
            if tok.type != tokenize.OP:
                continue
            if tok.string in ("(", "[", "{"):
                depth += 1
            elif tok.string in (")", "]", "}"):
                depth -= 1
            elif tok.string == ":" and depth == 0:
                return j
        return None

    def closing_paren(i):
        """Index of the ')' matching the '(' at i."""
        depth = 0
        for j in range(i, len(sig)):
            if sig[j].type == tokenize.OP and sig[j].string in ("(", "[", "{"):
                depth += 1
            elif sig[j].type == tokenize.OP and sig[j].string in (")", "]", "}"):
                depth -= 1
                if depth == 0:
                    return j
        return None

    def string_run_end(i):
        """If sig[i:] starts with string literals, the index after them."""
        j = i
        while j < len(sig):
            if sig[j].type == tokenize.STRING:
                j += 1
            elif _FSTRING_START is not None and sig[j].type == _FSTRING_START:
                depth = 0
                while j < len(sig):
                    if sig[j].type == _FSTRING_START:
                        depth += 1
                    elif sig[j].type == _FSTRING_END:
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                j += 1
            else:
                break
        return j if j > i else None

    def source_text(start_tok, end_tok):
        lines = io.StringIO(source).readlines()
        (r1, c1), (r2, c2) = start_tok.start, end_tok.end
        if r1 == r2:
            text = lines[r1 - 1][c1:c2]
        else:
            text = lines[r1 - 1][c1:] + "".join(lines[r1:r2 - 1]) + lines[r2 - 1][:c2]
        return " ".join(text.split())

    edits, untouched = [], []
    constants = {}  # deadass name -> index of its declaration
    skip = set()
    for i, tok in enumerate(sig):
        if i in skip or tok.type != tokenize.NAME:
            continue
        word = tok.string
        nxt = name_at(i + 1)
        pair = (word, nxt)
        if (pair in compounds and sig[i + 1].start[0] == tok.end[0]
                and not plain_name_position(i) and not is_op(i + 2, "=")):
            edits.append(Edit(tok.start[0], tok.start[1], sig[i + 1].end[1], compounds[pair]))
            skip.add(i + 1)
            continue
        if plain_name_position(i):
            continue

        if forward:
            # runitfoo 3:  ->  for _ in range(3):
            if word == REPEAT_WORD:
                colon = statement_colon(i)
                if colon is not None and colon > i + 1:
                    edits.append(Edit(tok.start[0], tok.start[1], _gap_end(tok, sig[i + 1]),
                                      "for _ in range("))
                    c = sig[colon]
                    edits.append(Edit(c.start[0], c.start[1], c.start[1], ")"))
                    continue
            # deadass MAX = 10  ->  MAX = 10, and MAX can't be assigned again
            if word == CONST_WORD and line_of.get(i, (None,))[0] == i and nxt is not None:
                target = sig[i + 1]
                if not (is_op(i + 2, "=") or is_op(i + 2, ":")):
                    raise _syntax_error(f"{CONST_WORD} needs a name and a value, like "
                                        f"`{CONST_WORD} MAX = 10`", filename, tok, source)
                if nxt in constants:
                    raise _syntax_error(f"{nxt} is already {CONST_WORD}", filename, target, source)
                constants[nxt] = i + 1
                edits.append(Edit(tok.start[0], tok.start[1], _gap_end(tok, target), ""))
                continue
            # yeet "message"  ->  raise Exception("message")
            if word == "yeet":
                after = string_run_end(i + 1)
                if after is not None and (
                        after >= len(sig)
                        or sig[after].type in (tokenize.NEWLINE, tokenize.ENDMARKER)
                        or is_op(after, ";")
                        or name_at(after) in ("outta", "from")):
                    last = sig[after - 1]
                    edits.append(Edit(tok.start[0], tok.start[1], _gap_end(tok, sig[i + 1]),
                                      "raise Exception("))
                    edits.append(Edit(last.end[0], last.end[1], last.end[1], ")"))
                    continue
            # lowkeysus(x + 1)  ->  slaython._sus("x + 1", line, x + 1)
            if word == SUS_WORD and is_op(i + 1, "("):
                close = closing_paren(i + 1)
                if close is not None:
                    shown = source_text(sig[i + 2], sig[close - 1]) if close > i + 2 else ""
                    edits.append(Edit(tok.start[0], tok.start[1], tok.end[1], HELPERS[word]))
                    paren = sig[i + 1]
                    edits.append(Edit(paren.end[0], paren.end[1], paren.end[1],
                                      f"{shown!r}, {tok.start[0]}, "))
                    continue
            if word in HELPERS:
                edits.append(Edit(tok.start[0], tok.start[1], tok.end[1], HELPERS[word]))
                continue

        if word in table and (word not in soft or soft_ok(i)):
            edits.append(Edit(tok.start[0], tok.start[1], tok.end[1], table[word]))
            continue
        untouched.append(tok)

    if constants:
        _check_constants(sig, line_of, constants, filename, source, table)
    return edits, untouched


def _check_constants(sig, line_of, constants, filename, source, table):
    """Refuse any assignment to a deadass name outside its declaration."""
    starts = sorted({first for first, _ in line_of.values()})
    for first in starts:
        tok = sig[first]
        if tok.type != tokenize.NAME:
            continue
        if tok.string in constants and first != constants[tok.string]:
            nxt = sig[first + 1] if first + 1 < len(sig) else None
            if nxt is not None and nxt.type == tokenize.OP and nxt.string in _ASSIGN_OPS:
                raise _syntax_error(f"{tok.string} is {CONST_WORD} (a constant). "
                                    "you can't reassign it, that's cap", filename, tok, source)
        if table.get(tok.string) == "del" or tok.string == "del":
            for j in range(first + 1, len(sig)):
                t = sig[j]
                if t.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                    break
                if t.type == tokenize.NAME and t.string in constants and not (
                        sig[j - 1].type == tokenize.OP and sig[j - 1].string == "."):
                    raise _syntax_error(f"{t.string} is {CONST_WORD} (a constant). "
                                        "you can't cancel it", filename, t, source)


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
    edits, _ = _plan(source, filename, SLANG_TO_PY, SOFT_SLANG, COMPOUND_SLANG, forward=True)
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

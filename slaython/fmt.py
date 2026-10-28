"""`slaython fmt`: format .slay files.

    slaython fmt                  # every .slay file under this folder
    slaython fmt src/ app.slay    # specific files or folders
    slaython fmt --check          # change nothing, exit 1 if a file would change
    slaython fmt --diff           # print the changes instead of writing them
    slaython fmt -                # format stdin to stdout

It only changes whitespace: 4 spaces per indentation level, blank lines,
and the spaces between tokens. Strings and comments are kept as they are,
and so are the line breaks inside a statement (continuation lines move
with their statement, or stay lined up with an open bracket).

Before anything is written, the result is checked: it must have exactly
the same tokens as the original and still translate and compile. If not,
the file is left alone and reported.
"""

import argparse
import difflib
import io
import os
import sys
import tokenize
from typing import List, NamedTuple, Optional

from .compiler import compile_source

INDENT = "    "
_OPEN, _CLOSE = "([{", ")]}"
# Always one space on both sides.
_SPACED = {"==", "!=", "<", ">", "<=", ">=", "->", ":=", "|>",
           "+=", "-=", "*=", "/=", "//=", "%=", "**=", "@=", "&=", "|=", "^=", ">>=", "<<="}
_FUNC_WORDS = {"cook", "def"}
_DEF_WORDS = {"cook", "def", "blueprint", "class"}
_ASYNC_WORDS = {"lowkey", "async"}
_DATA_WORDS = {"lore", "gang"}  # definitions only as `lore Name:` / `gang Name(...)`
_LAMBDA_WORDS = {"nohead", "lambda"}
_STRING_GROUPS = {getattr(tokenize, a): getattr(tokenize, b) for a, b in
                  (("FSTRING_START", "FSTRING_END"), ("TSTRING_START", "TSTRING_END"))
                  if hasattr(tokenize, a)}
_SKIP_DIRS = {"__pycache__", "node_modules"}


class UnsafeFormat(Exception):
    """The formatted code failed a safety check, so it must not be used."""


class _Tok(NamedTuple):
    type: int
    string: str  # text to write (whole f-string for f-string groups)
    start: tuple
    end: tuple


class _Stmt(NamedTuple):
    toks: list
    depth: int
    stack: list  # original indentation column of each open block


class _Comment(NamedTuple):
    text: str
    col: int


class _Blank(NamedTuple):
    pass


def _tokenize(source, filename="<slay>"):
    try:
        return list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError) as exc:
        if isinstance(exc, SyntaxError):
            raise
        lineno, col = exc.args[1] if len(exc.args) > 1 else (1, 0)
        raise SyntaxError(exc.args[0], (filename, lineno, col + 1, None)) from None


def _vcol(text):
    # A tab counts as one level (4 spaces) when continuation lines are moved.
    return len(text.expandtabs(4))


# --- reading the file into statements, comments and blank lines ---------

def _collect(tokens, lines):
    items = []
    stack = [0]
    cur = None
    cur_stack = None
    last = None
    for tok in tokens:
        t = tok.type
        if t == tokenize.ENCODING:
            continue
        if t == tokenize.INDENT:
            stack.append(None)  # filled in by the next statement
        elif t == tokenize.DEDENT:
            stack.pop()
        elif cur is None:
            if t == tokenize.NL:
                if not (last is not None and last.type == tokenize.COMMENT
                        and last.start[0] == tok.start[0]):
                    items.append(_Blank())
            elif t == tokenize.COMMENT:
                row, col = tok.start
                items.append(_Comment(tok.string.rstrip(), _vcol(lines[row - 1][:col])))
            elif t not in (tokenize.NEWLINE, tokenize.ENDMARKER):
                if stack[-1] is None:
                    stack[-1] = _vcol(lines[tok.start[0] - 1][:tok.start[1]])
                cur, cur_stack = [tok], list(stack)
        elif t in (tokenize.NEWLINE, tokenize.ENDMARKER):
            items.append(_Stmt(cur, len(cur_stack) - 1, cur_stack))
            cur = None
        else:
            cur.append(tok)
        last = tok
    if cur is not None:
        items.append(_Stmt(cur, len(cur_stack) - 1, cur_stack))
    return items


def _comment_depths(items):
    """Pick a block depth for each comment line from its column and its neighbours."""
    depths = {}
    prev = None
    nxt = [None] * len(items)
    following = None
    for i in range(len(items) - 1, -1, -1):
        nxt[i] = following
        if isinstance(items[i], _Stmt):
            following = items[i]
    for i, it in enumerate(items):
        if isinstance(it, _Stmt):
            prev = it
        elif isinstance(it, _Comment):
            dp, sp = (prev.depth, prev.stack) if prev else (0, [0])
            dn, sn = (nxt[i].depth, nxt[i].stack) if nxt[i] else (0, [0])
            if dn > dp:  # between a block header and its body: belongs to the body
                depths[i] = dn
                continue
            stack = sp if len(sp) >= len(sn) else sn
            depth = dn
            for k in range(dn, dp + 1):
                if stack[k] <= it.col:
                    depth = k
            depths[i] = depth
    return depths


def _project_words(filename):
    """Extra words from the project's pyproject.toml ({new word: built-in word})."""
    try:
        from .dialect import words_for
        return dict(words_for(filename) or {})
    except Exception:  # noqa: BLE001  (no dialect support, or a bad table: the check reports it)
        return {}


def _def_kind(toks, words=None):
    """'decorator', 'def' (cook/blueprint/lore/gang and friends) or None."""
    words = words or {}
    first = [words.get(t.string, t.string) for t in toks[:3]]
    if first[0] == "@":
        return "decorator"
    if first[0] in _DEF_WORDS:
        return "def"
    if first[0] in _ASYNC_WORDS and len(first) > 1 and first[1] in _FUNC_WORDS:
        return "def"
    if (first[0] in _DATA_WORDS and len(toks) > 2 and toks[1].type == tokenize.NAME
            and first[2] in (":", "(")):
        return "def"
    return None


# --- one statement ----------------------------------------------------------

class _Bracket:
    __slots__ = ("char", "is_def", "annotated", "row", "first_col", "first_new")

    def __init__(self, char, is_def, row):
        self.char, self.is_def, self.row = char, is_def, row
        self.annotated = False
        self.first_col = None  # original column of the first token after it, same line
        self.first_new = None  # its new column
        # row is set to None once the first token has been seen


def _units(toks, source_at):
    """Join f-string pieces into one token and adjacent `|` `>` into `|>`."""
    out = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok.type in _STRING_GROUPS:
            depth, j = 0, i
            while j < len(toks):
                if toks[j].type == tok.type:
                    depth += 1
                elif toks[j].type == _STRING_GROUPS[tok.type]:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            end = toks[j].end
            out.append(_Tok(tokenize.STRING, source_at(tok.start, end), tok.start, end))
            i = j + 1
            continue
        if (tok.type == tokenize.OP and tok.string == "|" and i + 1 < len(toks)
                and toks[i + 1].string == ">" and toks[i + 1].start == tok.end):
            out.append(_Tok(tokenize.OP, "|>", tok.start, toks[i + 1].end))
            i += 2
            continue
        string = tok.string.rstrip() if tok.type == tokenize.COMMENT else tok.string
        out.append(_Tok(tok.type, string, tok.start, tok.end))
        i += 1
    return out


def _is_op(tok, *ops):
    return tok is not None and tok.type == tokenize.OP and tok.string in ops


def _gap(p, u, orig, inner, kwarg_eq):
    """Spaces between tokens p and u on one line."""
    keep = " " if orig > 0 else ""
    if u.type == tokenize.COMMENT:
        return " " * max(2, orig)
    if _is_op(p, *_OPEN) or _is_op(u, *_CLOSE) or _is_op(u, ",", ";"):
        return ""
    if _is_op(p, ",", ";"):
        return " "
    if _is_op(p, *_SPACED) or _is_op(u, *_SPACED):
        return " "
    if _is_op(p, "=") or _is_op(u, "="):
        return "" if kwarg_eq else " "
    if _is_op(u, ":"):
        return keep if inner == "[" else ""
    if _is_op(p, ":"):
        return keep if inner == "[" else " "
    return keep


def _render_stmt(stmt, lines, source_at, words):
    toks = _units(stmt.toks, source_at)
    first = toks[0]
    indent = INDENT * stmt.depth
    delta = len(indent) - _vcol(lines[first.start[0] - 1][:first.start[1]])
    out = indent
    brackets: List[_Bracket] = []
    lambdas = []  # bracket depth of each lambda whose parameters are open
    p: Optional[_Tok] = None
    pp: Optional[_Tok] = None
    newlines = 0
    for u in toks:
        if u.type == tokenize.NL:
            newlines += 1
            continue
        if p is not None and u.start[0] > p.end[0]:
            if newlines == 0:
                out += " \\"  # backslash continuation
            out += "\n" * (1 + min(max(newlines - 1, 0), 1))
            col = _vcol(lines[u.start[0] - 1][:u.start[1]])
            top = brackets[-1] if brackets else None
            if top is not None and top.first_col is not None and top.first_col == col:
                new = top.first_new  # lined up with the first item after the bracket
            else:
                new = max(0, col + delta)
            out += " " * new
        elif p is not None:
            inner = brackets[-1].char if brackets else None
            in_lambda = bool(lambdas) and lambdas[-1] == len(brackets)
            kwarg_eq = in_lambda or (inner == "(" and not (brackets[-1].is_def
                                                         and brackets[-1].annotated))
            orig = u.start[1] - p.end[1] if u.start[0] == p.end[0] else 1
            out += _gap(p, u, orig, inner, kwarg_eq)
        newlines = 0
        new_col = len(out) - (out.rfind("\n") + 1)
        if brackets and brackets[-1].row is not None:
            b = brackets[-1]
            if u.start[0] == b.row and u.type != tokenize.COMMENT:
                b.first_col = _vcol(lines[u.start[0] - 1][:u.start[1]])
                b.first_new = new_col
            b.row = None
        out += u.string

        # keep track of brackets, lambdas and annotations for the next gaps
        if u.type == tokenize.OP:
            if u.string in _OPEN:
                is_def = (u.string == "(" and p is not None and p.type == tokenize.NAME
                          and pp is not None and words.get(pp.string, pp.string) in _FUNC_WORDS)
                brackets.append(_Bracket(u.string, is_def, u.end[0]))
            elif u.string in _CLOSE:
                if brackets:
                    brackets.pop()
                while lambdas and lambdas[-1] > len(brackets):
                    lambdas.pop()
            elif u.string == ":":
                if lambdas and lambdas[-1] == len(brackets):
                    lambdas.pop()
                elif brackets and brackets[-1].is_def:
                    brackets[-1].annotated = True
            elif u.string == "," and brackets and brackets[-1].is_def:
                brackets[-1].annotated = False
        elif (u.type == tokenize.NAME and words.get(u.string, u.string) in _LAMBDA_WORDS
              and not _is_op(p, ".")):
            lambdas.append(len(brackets))
        if u.type not in (tokenize.COMMENT,):
            pp, p = p, u
        else:
            p = u
    return out


# --- the whole file -----------------------------------------------------------

def _format_tokens(tokens, source, words=None):
    lines = io.StringIO(source).readlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def source_at(a, b):
        return source[starts[a[0] - 1] + a[1]:starts[b[0] - 1] + b[1]]

    words = words or {}
    items = _collect(tokens, lines)
    depths = _comment_depths(items)
    units, blanks, pending = [], [], 0
    for i, it in enumerate(items):
        if isinstance(it, _Blank):
            pending += 1
            continue
        if isinstance(it, _Stmt):
            units.append(("stmt", it.depth, _def_kind(it.toks, words), it))
        else:
            units.append(("comment", depths[i], None, it))
        blanks.append(pending)
        pending = 0
    if not units:
        return ""

    n = len(units)
    b = [min(blanks[i], 2 if units[i][1] == 0 else 1) for i in range(n)]
    b[0] = 0
    for i in range(1, n):
        if units[i - 1][2] == "decorator":
            b[i] = 0
    # Two blank lines before top-level definitions (and the comments right above them)...
    for i, (kind, depth, defkind, _) in enumerate(units):
        if depth != 0 or defkind is None or (i > 0 and units[i - 1][2] == "decorator"):
            continue
        j = i
        while j > 0 and units[j - 1][0] == "comment" and units[j - 1][1] == 0 and b[j] == 0:
            j -= 1
        if j > 0 and units[j - 1][2] == "decorator":
            continue
        b[j] = 2 if j > 0 else 0
    # ...and after them, before the next top-level line.
    for i, (kind, depth, defkind, _) in enumerate(units):
        if depth == 0 and defkind == "def":
            k = i + 1
            while k < n and units[k][1] > 0:
                k += 1
            if k < n:
                b[k] = 2

    out = []
    for i, (kind, depth, _, it) in enumerate(units):
        out.append("\n" * b[i])
        if kind == "comment":
            out.append(INDENT * depth + it.text + "\n")
        else:
            out.append(_render_stmt(it, lines, source_at, words) + "\n")
    return "".join(out)


def _signature(source):
    """What must not change: every token (minus whitespace details), in order."""
    sig = []
    prev = None
    for tok in _tokenize(source):
        t = tok.type
        if t in (tokenize.ENCODING, tokenize.NL):
            continue
        if t in (tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.ENDMARKER):
            sig.append((t,))
            prev = None
            continue
        text = tok.string.rstrip() if t == tokenize.COMMENT else tok.string
        same_row = prev is not None and prev.end[0] == tok.start[0]
        glued = prev is not None and prev.string == "|" and text == ">" and prev.end == tok.start
        sig.append((t, text, same_row, glued))
        prev = tok
    return sig


def format_source(source, filename="<slay>"):
    """Return `source` formatted.

    Raises SyntaxError if the source doesn't translate and compile, and
    UnsafeFormat if the result fails the safety checks.
    """
    tokens = _tokenize(source, filename)
    compile_source(source, filename)
    words = _project_words(filename)
    result = _format_tokens(tokens, source, words)
    if result == source:
        return result
    if _signature(result) != _signature(source):
        raise UnsafeFormat("formatting would change the tokens")
    try:
        compile_source(result, filename)
    except SyntaxError as exc:
        raise UnsafeFormat(f"the formatted code doesn't translate ({exc.msg})") from None
    if _format_tokens(_tokenize(result, filename), result, words) != result:
        raise UnsafeFormat("formatting isn't stable for this file")
    return result


# --- the command ------------------------------------------------------------

def slay_files(paths):
    for path in paths or ["."]:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in _SKIP_DIRS)
            for name in sorted(files):
                if name.endswith(".slay"):
                    yield os.path.join(root, name)


def _read(path):
    """(text, encoding, newline) of a file, decoded the way Python reads source."""
    with open(path, "rb") as f:
        data = f.read()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    text = io.TextIOWrapper(io.BytesIO(data), encoding=encoding).read()
    first_end = data.find(b"\n")
    newline = "\r\n" if first_end > 0 and data[first_end - 1:first_end] == b"\r" else "\n"
    return text, encoding, newline


def _problem(path, exc):
    if isinstance(exc, SyntaxError):
        where = f"{path}:{exc.lineno}" if exc.lineno else path
        return f"{where}: can't format, {type(exc).__name__}: {exc.msg}"
    return f"{path}: can't format, {exc}"


def main(argv=None):
    p = argparse.ArgumentParser(prog="slaython fmt", description="Format .slay files.")
    p.add_argument("paths", nargs="*", help="files or folders (default: .), - for stdin")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="change nothing, exit 1 if any file would be reformatted")
    mode.add_argument("--diff", action="store_true", help="print a diff instead of writing")
    p.add_argument("-q", "--quiet", action="store_true", help="only print problems")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    say = (lambda msg: None) if args.quiet else print

    if args.paths == ["-"]:
        source = sys.stdin.read()
        try:
            result = format_source(source, "<stdin>")
        except (SyntaxError, UnsafeFormat) as exc:
            sys.stderr.write(_problem("<stdin>", exc) + "\n")
            sys.stdout.write(source)
            return 1
        if args.check:
            return int(result != source)
        if args.diff:
            sys.stdout.writelines(difflib.unified_diff(
                source.splitlines(keepends=True), result.splitlines(keepends=True),
                "<stdin>", "<stdin>"))
            return 0
        sys.stdout.write(result)
        return 0

    files = changed = failed = 0
    for path in slay_files(args.paths):
        files += 1
        try:
            source, encoding, newline = _read(path)
            result = format_source(source, path)
        except (OSError, UnicodeDecodeError, SyntaxError, UnsafeFormat) as exc:
            sys.stderr.write(_problem(path, exc) + "\n")
            failed += 1
            continue
        if result == source:
            continue
        changed += 1
        if args.check:
            say(f"would reformat {path}")
        elif args.diff:
            sys.stdout.writelines(difflib.unified_diff(
                source.splitlines(keepends=True), result.splitlines(keepends=True), path, path))
        else:
            with open(path, "w", encoding=encoding, newline=newline) as f:
                f.write(result)
            say(f"reformatted {path}")

    if files == 0:
        say("no .slay files found")
        return 0
    plural = lambda n: f"{n} file{'s' * (n != 1)}"  # noqa: E731
    if args.check:
        say(f"{plural(changed)} would be reformatted, {plural(files - changed - failed)} "
            "already formatted" if changed else f"{plural(files - failed)} already formatted")
    elif not args.diff:
        say(f"{plural(changed)} reformatted, {plural(files - changed - failed)} left unchanged")
    if failed:
        sys.stderr.write(f"{plural(failed)} could not be formatted\n")
    return 1 if failed or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())

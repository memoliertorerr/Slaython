"""Turn Slaython source into a Python code object.

Most of Slaython is word swaps (see transpiler.py). Two features need to
change the shape of the code, so they are finished on Python's syntax tree,
which keeps every original line number:

- `x |> f` becomes `f(x)`, and `x |> f(y)` becomes `f(x, y)`.
- `shoot n:` (try) becomes a loop that retries the block up to n times
  before its `fumble` (except) handler runs.
"""

import ast
import io

from .transpiler import Translation, python_col_to_slang, translate

_LOOP_EXITS = (ast.Break, ast.Continue)
_NEW_SCOPE = (ast.For, ast.AsyncFor, ast.While, ast.FunctionDef, ast.AsyncFunctionDef,
              ast.Lambda, ast.ClassDef)


def compile_source(source, filename="<slay>", mode="exec"):
    """Compile Slaython source. SyntaxErrors point at the Slaython line."""
    t = translate(source, filename)
    try:
        if t.needs_tree_pass:
            tree = _tree(t, source, filename, mode)
            return compile(tree, filename, mode, dont_inherit=True)
        return compile(t.python, filename, mode, dont_inherit=True)
    except SyntaxError as exc:
        point_at_slang(exc, source, t.edits)
        raise


def python_source(source, filename="<slay>"):
    """Python source for `slaython translate` and transpile()."""
    t = translate(source, filename)
    if not t.needs_tree_pass:
        return t.python
    try:
        tree = _tree(t, source, filename, "exec")
    except SyntaxError:
        return t.python  # unfinished code (e.g. in the REPL): let the compiler report it
    return ast.unparse(tree) + "\n"


def _tree(t: Translation, source, filename, mode):
    return finish_tree(ast.parse(t.python, filename, mode), t, source, filename)


def finish_tree(tree, t: Translation, source, filename):
    """Finish `|>` and `shoot n:` on a tree parsed from t.python."""
    if t.pipes:
        tree = _Pipes(set(t.pipes)).visit(tree)
    if t.retries:
        tree = _Retries(t.retries, source, filename).visit(tree)
    return ast.fix_missing_locations(tree)


class _Pipes(ast.NodeTransformer):
    """`a | f` nodes that came from `a |> f` become calls."""

    def __init__(self, pipes):
        self.pipes = pipes

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if not isinstance(node.op, ast.BitOr) or not self._is_pipe(node):
            return node
        target = node.right
        if isinstance(target, ast.Call):
            call = ast.Call(func=target.func, args=[node.left, *target.args], keywords=target.keywords)
        else:
            call = ast.Call(func=target, args=[node.left], keywords=[])
        return ast.copy_location(call, node)

    def _is_pipe(self, node):
        after_left = (node.left.end_lineno, node.left.end_col_offset)
        before_right = (node.right.lineno, node.right.col_offset)
        return any(after_left <= pos < before_right for pos in self.pipes)


class _Retries(ast.NodeTransformer):
    """Wrap each marked `try` in a loop that retries it."""

    def __init__(self, retries, source, filename):
        self.retries, self.source, self.filename = retries, source, filename

    def visit_Try(self, node):
        self.generic_visit(node)
        count_src = self.retries.get(node.lineno)
        if count_src is None:
            return node
        self._refuse_loop_exits(node)
        line = node.lineno
        attempt, last = f"__slay_attempt_{line}", f"__slay_last_{line}"
        handlers = node.handlers or [_at(ast.ExceptHandler(
            type=ast.Name("Exception", ast.Load()), name=None, body=[ast.Raise()]), node)]
        for h in handlers:
            retry_unless_last = ast.parse(f"if not {last}:\n    continue").body[0]
            h.body = [_at(retry_unless_last, h), *h.body]
        attempt_try = ast.Try(body=node.body, handlers=handlers, orelse=node.orelse, finalbody=[])
        counter = ast.parse(f'__import__("slaython")._attempts({count_src})', mode="eval").body
        loop = ast.For(
            target=ast.Tuple([ast.Name(attempt, ast.Store()), ast.Name(last, ast.Store())], ast.Store()),
            iter=counter, body=[ast.copy_location(attempt_try, node), ast.Break()], orelse=[])
        for n in (loop, counter, attempt_try):
            _at(n, node, deep=n is counter)
        if node.finalbody:
            outer = ast.Try(body=[loop], handlers=[], orelse=[], finalbody=node.finalbody)
            return ast.copy_location(outer, node)
        return loop

    def _refuse_loop_exits(self, node):
        """dip/anyways right inside `shoot n:` would hit the retry loop, so refuse them."""
        stack = [*node.body, *node.orelse, *[s for h in node.handlers for s in h.body]]
        while stack:
            n = stack.pop()
            if isinstance(n, _LOOP_EXITS):
                lines = io.StringIO(self.source).readlines()
                text = lines[n.lineno - 1] if n.lineno <= len(lines) else None
                raise SyntaxError("dip / anyways can't go straight inside `shoot n:`; "
                                  "put the retry inside the loop body instead",
                                  (self.filename, n.lineno, n.col_offset + 1, text))
            if not isinstance(n, _NEW_SCOPE):
                stack.extend(ast.iter_child_nodes(n))


def _at(node, ref, deep=True):
    """Give `node` (and, if deep, everything inside it) the position of `ref`."""
    for n in ast.walk(node) if deep else (node,):
        if "lineno" in n._attributes:
            n.lineno, n.col_offset = ref.lineno, ref.col_offset
            n.end_lineno, n.end_col_offset = ref.end_lineno, ref.end_col_offset
    return node


def point_at_slang(exc, source, edits):
    """Make a SyntaxError show the Slaython line, with the caret in the right spot."""
    if not exc.lineno:
        return
    # Split like the tokenizer does (on "\n" only) so line numbers agree.
    lines = io.StringIO(source).readlines()
    if not 0 < exc.lineno <= len(lines):
        return
    slang_line = lines[exc.lineno - 1].rstrip("\r\n") + "\n"
    if exc.text == slang_line:
        return  # already points at Slaython (raised by the translator itself)
    exc.text = slang_line
    if exc.offset:
        exc.offset = python_col_to_slang(edits, exc.lineno, exc.offset - 1) + 1
    end_lineno = getattr(exc, "end_lineno", None)
    if getattr(exc, "end_offset", None) and end_lineno == exc.lineno:
        exc.end_offset = python_col_to_slang(edits, end_lineno, exc.end_offset - 1) + 1

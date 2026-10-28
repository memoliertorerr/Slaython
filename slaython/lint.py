"""`slaython lint`: catch mistakes in .slay files before you run them.

    slaython lint                      # every .slay file under this folder
    slaython lint src/ app.slay        # specific files or folders
    slaython lint --select SL1,SL201   # only these checks (codes or prefixes)
    slaython lint --ignore SL103       # everything except these
    slaython lint --codes              # list every check

Each problem prints as ``path:line:col: CODE message``. Exit code 0 means
clean, 1 means problems were found, 2 means the command was used wrong.

Silence one line by ending it with ``# lint: ignore`` (every check) or
``# lint: ignore[SL101, SL103]`` (just those codes).

Checks:

    SL001  the file doesn't translate or compile (syntax error)
    SL101  undefined name, or a name used before it gets a value
    SL102  pullup (import) that is never used
    SL103  local variable that gets a value but is never used
    SL104  cook / blueprint defined again before the first one was used
    SL201  unreachable code after serve / yeet / dip / anyways / touchgrass()
    SL301  `literally` (is) compared with a literal like "text" or 3
    SL302  `== ghosted` / `!= ghosted` instead of `literally (nah) ghosted`
    SL303  bare fumble / fumble skillissue that swallows every error with chill
    SL304  mutable default argument, like `cook f(x=[])`
    SL305  ongod on a tuple, which is always nocap
    SL306  the same key twice in one dict literal
    SL307  yeet NotImplemented (you want NotImplementedError)
    SL308  method in a blueprint with no parameters at all (no mee)

The file goes through the normal Slaython pipeline (translation keeps the
line numbers), then the checks run on Python's syntax tree. Columns are
mapped back to the .slay file.
"""

import argparse
import ast
import builtins
import difflib
import io
import os
import re
import sys
import tokenize
import warnings
from typing import Dict, List, NamedTuple, Set

from .keywords import ALL_SLANG_WORDS, PY_TO_SLANG

CODES = {
    "SL001": "the file doesn't translate or compile",
    "SL101": "undefined name, or used before it gets a value",
    "SL102": "pullup that is never used",
    "SL103": "local variable that is never used",
    "SL104": "cook / blueprint redefined before it was used",
    "SL201": "unreachable code",
    "SL301": "literally compared with a literal",
    "SL302": "== ghosted / != ghosted",
    "SL303": "fumble that swallows every error with chill",
    "SL304": "mutable default argument",
    "SL305": "ongod on a tuple (always nocap)",
    "SL306": "duplicate key in a dict literal",
    "SL307": "yeet NotImplemented",
    "SL308": "method without mee",
}


def _w(py):
    """The Slaython word for a Python keyword/builtin (so messages follow keywords.py)."""
    return PY_TO_SLANG.get(py, py)


class Problem(NamedTuple):
    path: str
    line: int
    col: int  # 1-based, in the .slay file
    code: str
    message: str

    def __str__(self):
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"


# --- names that are always there ------------------------------------------

_BUILTINS = set(dir(builtins)) | {"__file__", "__builtins__", "__annotations__", "__path__",
                                   "WindowsError"}
_IMPLICIT = {"__module__", "__qualname__", "__class__", "__name__", "__doc__", "__spec__",
             "__loader__", "__package__", "__dict__"}
_EXITS = {"exit", "quit"}
_MUTABLE_CALLS = {"list", "dict", "set", "bytearray", "defaultdict", "deque", "OrderedDict", "Counter"}
_BROAD = {"Exception", "BaseException"}
_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}
_DYNAMIC = {"locals", "vars", "eval", "exec"}
# decorators that still pass the object/class as the first argument
_METHOD_DECORATORS = {"classmethod", "property", "cached_property", "abstractmethod",
                      "setter", "getter", "deleter"}
_CONTEXT = ("lenient", "in_annotation", "import_guard", "name_guard")
_IGNORE_RE = re.compile(r"#\s*lint:\s*ignore\b(?:\[([^\]]*)\])?")


# --- scopes -----------------------------------------------------------------

class _Binding:
    __slots__ = ("name", "kind", "node", "scope", "block", "pos", "stmt", "skip")

    def __init__(self, name, kind, node, scope, block, pos):
        self.name, self.kind, self.node, self.scope = name, kind, node, scope
        self.block, self.pos = block, pos
        self.stmt = None    # imports: the pullup statement
        self.skip = False   # imports that are fine unused (fallbacks, re-exports, __future__)


class _Scope:
    """kind: module, class, function (lambdas too) or comp (comprehensions)."""

    def __init__(self, kind, node, parent):
        self.kind, self.node, self.parent = kind, node, parent
        self.bindings: Dict[str, List[_Binding]] = {}
        self.used: Set[str] = set()
        self.use_pos: Dict[str, list] = {}
        self.globals: Set[str] = set()
        self.nonlocals: Set[str] = set()
        self.loop_depth = 0
        self.dynamic = False  # calls locals()/eval(), so unused locals can't be judged
        self.is_lambda = False


class _Use(NamedTuple):
    name: str
    pos: tuple            # (python line, python byte col)
    scope: _Scope
    skip_self: bool       # mutuals: look it up starting at the parent scope
    ordered: tuple        # module/class scopes this code runs in right away
    bound_now: tuple      # ...and the ones where the name already had a value
    in_loop: bool
    lenient: bool         # annotations: don't check order
    quiet: bool           # string annotation, or inside `shoot` + `fumble NameError`


def _is_literal(node):
    if isinstance(node, ast.Constant):
        return node.value is not None and not isinstance(node.value, bool) and node.value is not ...
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_literal(node.operand)
    return isinstance(node, (ast.JoinedStr, ast.List, ast.Tuple, ast.Dict, ast.Set,
                             ast.ListComp, ast.DictComp, ast.SetComp))


def _is_mutable(node):
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        return name in _MUTABLE_CALLS
    return False


def _dotted(node):
    """`a.b.c` -> "a.b.c"; anything else -> ""."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _short(node, limit=24):
    try:
        text = ast.unparse(node)
    except Exception:  # noqa: BLE001 - only used for messages
        return "that"
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _handler_names(handler_type):
    if handler_type is None:
        return set()
    elts = handler_type.elts if isinstance(handler_type, ast.Tuple) else [handler_type]
    return {_dotted(e).rsplit(".", 1)[-1] for e in elts}


class _Linter(ast.NodeVisitor):
    def __init__(self, tree, filename, report):
        self.report = report  # report((line, byte_col), code, message)
        self.filename = filename
        self.is_init = os.path.basename(filename).startswith("__init__.")
        self.module = _Scope("module", tree, None)
        self.scope = self.module
        self.functions: List[_Scope] = []
        self.uses: List[_Use] = []
        self.redefs = []
        self.all_names = []  # (name, node) from __all__
        self.extra_known: Set[str] = set()  # PEP 695 type parameters
        self.lenient = self.in_annotation = self.import_guard = 0
        self.name_guard = 0  # inside a shoot whose fumble catches NameError
        self.bind_kind = None
        self.star = False
        # id(statement) -> (id(parent), field): which block a statement sits in
        self.blocks = {}
        for parent in ast.walk(tree):
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.stmt):
                            self.blocks[id(item)] = (id(parent), field)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _pos(node):
        return (node.lineno, node.col_offset)

    def _bind(self, name, node, kind, pos=None):
        scope = self.scope
        if kind == "walrus":
            while scope.kind == "comp":
                scope = scope.parent
        if name in scope.nonlocals:
            return None  # the outer function's variable; the mutuals line counted as a use
        if name in scope.globals:
            scope = self.module
        b = _Binding(name, kind, node, scope, self.blocks.get(id(node)), pos or self._pos(node))
        scope.bindings.setdefault(name, []).append(b)
        return b

    def _use(self, name, node, skip_self=False, quiet=False, pos=None):
        ordered, bound, in_loop = [], [], False
        s = self.scope
        while s is not None and not self.lenient:
            in_loop = in_loop or s.loop_depth > 0
            if s.kind == "function":  # runs later, when called: order doesn't matter
                ordered, bound = [], []
                break
            if s.kind in ("module", "class"):
                ordered.append(s)
                if name in s.bindings:
                    bound.append(s)
            s = s.parent
        self.uses.append(_Use(name, pos or self._pos(node), self.scope, skip_self, tuple(ordered),
                              tuple(bound), in_loop, bool(self.lenient), quiet or self.name_guard > 0))

    def _target(self, node, kind):
        old, self.bind_kind = self.bind_kind, kind
        self.visit(node)
        self.bind_kind = old

    def _annotation(self, node):
        if node is None:
            return
        self.lenient += 1
        self.in_annotation += 1
        self.visit(node)
        self.lenient -= 1
        self.in_annotation -= 1

    def _nearest_function(self):
        s = self.scope
        while s is not None and s.kind == "comp":
            s = s.parent
        return s if s is not None and s.kind == "function" else None

    # -- names -----------------------------------------------------------

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self._bind(node.id, node, self.bind_kind or "assign")
        else:  # Load, or Del (cancel needs the name to exist)
            self._use(node.id, node)

    def visit_Constant(self, node):
        if self.in_annotation and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value.strip(), mode="eval")
            except SyntaxError:
                return
            for n in ast.walk(inner):
                if isinstance(n, ast.Name):
                    self._use(n.id, node, quiet=True)

    def visit_Global(self, node):
        self.scope.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.scope.nonlocals.update(node.names)
        for name in node.names:
            self._use(name, node, skip_self=True)

    # -- assignments -----------------------------------------------------

    def visit_Assign(self, node):
        self.visit(node.value)
        for t in node.targets:
            self._target(t, "assign" if isinstance(t, ast.Name) else "unpack")
        if self.scope is self.module and any(isinstance(t, ast.Name) and t.id == "__all__"
                                             for t in node.targets):
            self._collect_all(node.value)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            self._use(node.target.id, node.target)
            self._bind(node.target.id, node.target, "aug")
            if self.scope is self.module and node.target.id == "__all__":
                self._collect_all(node.value)
        else:
            self.visit(node.target)

    def visit_AnnAssign(self, node):
        self._annotation(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        if isinstance(node.target, ast.Name):
            if node.value is not None:
                self._bind(node.target.id, node.target, "assign")
        else:
            self.visit(node.target)

    def visit_NamedExpr(self, node):
        self.visit(node.value)
        self._bind(node.target.id, node.target, "walrus")

    def visit_TypeAlias(self, node):  # Python 3.12+: type X = ...
        for tp in node.type_params:
            self.extra_known.add(tp.name)
        self._bind(node.name.id, node.name, "def")
        self._annotation(node.value)

    def _collect_all(self, value):
        if isinstance(value, (ast.List, ast.Tuple)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    self.all_names.append((elt.value, elt))

    # -- loops, with, try --------------------------------------------------

    def visit_For(self, node):
        self.visit(node.iter)
        self._target(node.target, "for")
        self.scope.loop_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self.scope.loop_depth -= 1
        for stmt in node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.scope.loop_depth += 1
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.loop_depth -= 1
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_With(self, node):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._target(item.optional_vars, "with")
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncWith = visit_With

    def visit_Try(self, node):
        guard = any(h.type is None or _handler_names(h.type) & _IMPORT_ERRORS
                    for h in node.handlers)
        probe = any(_handler_names(h.type) & {"NameError", "UnboundLocalError"}
                    for h in node.handlers)
        self.import_guard += guard
        self.name_guard += probe
        for stmt in node.body:
            self.visit(stmt)
        self.name_guard -= probe
        for h in node.handlers:  # imports in a `fumble ImportError` are fallbacks too
            self.visit(h)
        self.import_guard -= guard
        for part in (node.orelse, node.finalbody):
            for n in part:
                self.visit(n)

    visit_TryStar = visit_Try

    def visit_ExceptHandler(self, node):
        if node.type is not None:
            self.visit(node.type)
        self._check_swallow(node)
        if node.name:
            self._bind(node.name, node, "except", pos=self._as_pos(node))
        for stmt in node.body:
            self.visit(stmt)

    def _as_pos(self, handler):
        """Position of the name after `aka` in a fumble line (falls back to the fumble)."""
        line = self.py_lines[handler.lineno - 1] if handler.lineno <= len(self.py_lines) else ""
        raw = line.encode("utf-8")
        m = re.compile(rb"\bas\s+(" + re.escape(handler.name.encode()) + rb")\b").search(
            raw, handler.col_offset)
        return (handler.lineno, m.start(1)) if m else self._pos(handler)

    # -- match / pov -----------------------------------------------------

    def visit_MatchAs(self, node):
        if node.pattern is not None:
            self.visit(node.pattern)
        if node.name:
            self._bind(node.name, node, "match")

    def visit_MatchStar(self, node):
        if node.name:
            self._bind(node.name, node, "match")

    def visit_MatchMapping(self, node):
        self.generic_visit(node)
        if node.rest:
            self._bind(node.rest, node, "match")

    # -- imports ---------------------------------------------------------

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            b = self._bind(name, alias, "import", pos=self._alias_pos(alias, node))
            if b is not None:
                b.stmt, b.skip = node, self.import_guard > 0 or alias.asname == alias.name

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == "*":
                self.star = True
                continue
            name = alias.asname or alias.name
            b = self._bind(name, alias, "import", pos=self._alias_pos(alias, node))
            if b is not None:
                b.stmt = node
                b.skip = (self.import_guard > 0 or alias.asname == alias.name
                          or node.module == "__future__")

    @staticmethod
    def _alias_pos(alias, stmt):
        return (alias.lineno, alias.col_offset) if hasattr(alias, "lineno") else (
            stmt.lineno, stmt.col_offset)

    # -- functions and blueprints -----------------------------------------

    def visit_FunctionDef(self, node):
        for d in node.decorator_list:
            self.visit(d)
        self._defaults(node.args)
        for tp in getattr(node, "type_params", ()):
            self.extra_known.add(tp.name)
        for a in self._all_args(node.args):
            self._annotation(a.annotation)
        self._annotation(node.returns)
        self._bind_def(node, "def")
        self._function_body(node, node.args, node.body)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self._defaults(node.args)
        self._function_body(node, node.args, [node.body], is_lambda=True)

    @staticmethod
    def _all_args(args):
        out = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        out += [a for a in (args.vararg, args.kwarg) if a is not None]
        return out

    def _defaults(self, args):
        for d in args.defaults:
            self.visit(d)
        for d in args.kw_defaults:
            if d is not None:
                self.visit(d)
        positional = [*args.posonlyargs, *args.args]
        pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
        pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
        for arg, default in pairs:
            if _is_mutable(default):
                self.report(self._pos(default), "SL304",
                            f"mutable default {arg.arg}={_short(default)} gets shared by every "
                            f"call. default to {_w('None')} and make a fresh one inside")

    def _function_body(self, node, args, body, is_lambda=False):
        scope = _Scope("function", node, self.scope)
        scope.is_lambda = is_lambda
        self.functions.append(scope)
        outer, self.scope = self.scope, scope
        # the body runs later, outside whatever annotation / shoot we're in now
        saved = {k: getattr(self, k) for k in _CONTEXT}
        for k in _CONTEXT:
            setattr(self, k, 0)
        for a in self._all_args(args):
            self._bind(a.arg, a, "param")
        for stmt in body:
            self.visit(stmt)
        self.scope = outer
        for k, v in saved.items():
            setattr(self, k, v)

    def visit_ClassDef(self, node):
        for d in node.decorator_list:
            self.visit(d)
        for tp in getattr(node, "type_params", ()):
            self.extra_known.add(tp.name)
        for b in node.bases:
            self.visit(b)
        for k in node.keywords:
            self.visit(k.value)
        scope = _Scope("class", node, self.scope)
        outer, self.scope = self.scope, scope
        for stmt in node.body:
            self.visit(stmt)
        self.scope = outer
        self._check_methods(node)
        self._bind_def(node, "class")

    def _bind_def(self, node, kind):
        target = self.module if node.name in self.scope.globals else self.scope
        before = target.bindings.get(node.name)
        prev = before[-1] if before else None
        b = self._bind(node.name, node, kind)
        if (b is not None and prev is not None and prev.kind in ("def", "class")
                and prev.block == b.block and not prev.node.decorator_list
                and not any(_dotted(d).endswith("overload") for d in node.decorator_list)):
            self.redefs.append((prev, b))

    def _check_methods(self, node):
        """Methods with no parameters at all, in a blueprint that has normal methods."""
        def plain(fn):
            # undecorated, or decorated with something that still passes mee/cls
            return all(_dotted(d.func if isinstance(d, ast.Call) else d).rsplit(".", 1)[-1]
                       in _METHOD_DECORATORS for d in fn.decorator_list)

        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        def takes_args(fn):
            return bool(fn.args.posonlyargs or fn.args.args or fn.args.vararg)

        bare = [m for m in methods if plain(m) and not takes_args(m)]
        # without any normal method that takes mee, it's a namespace called on the class itself
        if not bare or not any(takes_args(m) and not m.decorator_list for m in methods):
            return
        for m in bare:
            self.report(self._pos(m), "SL308",
                        f"method {m.name} has no parameters, but it gets the object as the first "
                        f"one. add {_w('self')} (or make it @staticmethod)")

    # -- comprehensions ----------------------------------------------------

    def _comprehension(self, node, results):
        gens = node.generators
        self.visit(gens[0].iter)  # runs in the enclosing scope
        scope = _Scope("comp", node, self.scope)
        outer, self.scope = self.scope, scope
        for i, gen in enumerate(gens):
            if i:
                self.visit(gen.iter)
            self._target(gen.target, "for")
            for cond in gen.ifs:
                self.visit(cond)
        for r in results:
            self.visit(r)
        self.scope = outer

    def visit_ListComp(self, node):
        self._comprehension(node, [node.elt])

    visit_SetComp = visit_GeneratorExp = visit_ListComp

    def visit_DictComp(self, node):
        self._comprehension(node, [node.key, node.value])

    # -- single-node checks ------------------------------------------------

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in _DYNAMIC | {"globals"}:
            fn = self._nearest_function()
            if fn is not None:
                fn.dynamic = True
            if node.func.id == "globals" or fn is None and node.func.id == "exec":
                self.star = True  # names appear at run time: can't judge undefined ones
        if (self.scope is self.module and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("extend", "append") and _dotted(node.func.value) == "__all__"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self.all_names.append((arg.value, arg))
                else:
                    self._collect_all(arg)
        self.generic_visit(node)

    def visit_Compare(self, node):
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Is, ast.IsNot)):
                lit = right if _is_literal(right) else left if _is_literal(left) else None
                if lit is not None:
                    word = _w("is") if isinstance(op, ast.Is) else f"{_w('is')} {_w('not')}"
                    fix = "==" if isinstance(op, ast.Is) else "!="
                    self.report(self._pos(node), "SL301",
                                f"`{word}` checks if it's the same object, not the same value. "
                                f"use {fix} to compare with {_short(lit)}")
            elif isinstance(op, (ast.Eq, ast.NotEq)):
                if any(isinstance(n, ast.Constant) and n.value is None for n in (left, right)):
                    bad = "==" if isinstance(op, ast.Eq) else "!="
                    good = _w("is") if isinstance(op, ast.Eq) else f"{_w('is')} {_w('not')}"
                    self.report(self._pos(node), "SL302",
                                f"use `{good} {_w('None')}` instead of `{bad} {_w('None')}`")
            left = right
        self.generic_visit(node)

    def visit_Assert(self, node):
        if isinstance(node.test, ast.Tuple) and node.test.elts:
            self.report(self._pos(node), "SL305",
                        f"{_w('assert')} on a tuple is always {_w('True')}, so it never fails. "
                        f"drop the parentheses: {_w('assert')} check, \"message\"")
        self.generic_visit(node)

    def visit_Dict(self, node):
        seen = {}
        for key in node.keys:
            if isinstance(key, ast.Constant):
                k = (type(key.value), key.value)
                if k in seen:
                    self.report(self._pos(key), "SL306",
                                f"key {_short(key)} shows up twice in this dict (first on line "
                                f"{seen[k]}), the first value gets overwritten")
                else:
                    seen[k] = key.lineno
        self.generic_visit(node)

    def visit_Raise(self, node):
        exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        if isinstance(exc, ast.Name) and exc.id == "NotImplemented":
            self.report(self._pos(node), "SL307",
                        f"NotImplemented isn't an error, {_w('raise')} NotImplementedError instead")
        self.generic_visit(node)

    def _check_swallow(self, handler):
        body = handler.body
        if not all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr)
                   and isinstance(s.value, ast.Constant) and s.value.value is ...) for s in body):
            return
        names = _handler_names(handler.type)
        if handler.type is None:
            what = f"bare `{_w('except')}:`"
        elif names & _BROAD:
            broad = sorted(names & _BROAD)[0]
            what = f"`{_w('except')} {_w(broad)}`"
        else:
            return
        self.report(self._pos(handler), "SL303",
                    f"{what} with just {_w('pass')} swallows every error and hides bugs. "
                    f"catch the error you expect, or at least {_w('print')} it")

    # -- after the walk ------------------------------------------------------

    def finish(self):
        for use in self.uses:
            self._resolve(use)
        self._report_redefs()
        self._report_all()
        self._report_unused_imports()
        self._report_unused_locals()

    def _resolve(self, use):
        name = use.name
        s = use.scope.parent if use.skip_self else use.scope
        first = not use.skip_self
        later = None  # a binding that exists, but only further down
        while s is not None:
            if s.kind == "class" and not first:
                s = s.parent  # blueprint bodies aren't visible inside methods
                continue
            if s.kind != "module" and name in s.globals:
                s, first = self.module, False
                continue
            if name in s.nonlocals:
                s, first = s.parent, False
                continue
            if name in s.bindings:
                if s in use.ordered and s not in use.bound_now and not use.in_loop:
                    later = later or s.bindings[name][0]
                    s, first = s.parent, False  # Python keeps looking further out
                    continue
                s.used.add(name)
                s.use_pos.setdefault(name, []).append(use.pos)
                return
            first = False
            s = s.parent
        if name in _BUILTINS or name in _IMPLICIT or name in self.extra_known:
            return
        if later is not None:
            later.scope.used.add(name)
            if use.quiet:
                return
            node = later.node
            if (later.kind == "class" and (node.lineno, node.col_offset) <= use.pos
                    and use.pos < (node.end_lineno, node.end_col_offset)):
                msg = f"{name} doesn't exist yet while its own {_w('class')} body runs"
            else:
                msg = f"{name} is used before it gets a value (that happens on line {later.pos[0]})"
            self.report(use.pos, "SL101", msg)
            return
        if self.star or use.quiet:
            return
        self.report(use.pos, "SL101", self._who(name, use.scope))

    def _who(self, name, scope):
        known = set(_BUILTINS) | {w for w in ALL_SLANG_WORDS}
        s = scope
        while s is not None:
            known.update(s.bindings)
            s = s.parent
        known.discard(name)
        close = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.8)
        hint = f"typo for {close[0]}?" if close else "typo?"
        return f"who is {name}? it's never defined ({hint})"

    def _report_redefs(self):
        for prev, new in self.redefs:
            end = (prev.node.end_lineno, prev.node.end_col_offset)
            uses = new.scope.use_pos.get(new.name, ())
            if any(end <= pos < new.pos for pos in uses):
                continue
            word = _w("def") if isinstance(new.node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                else _w("class")
            self.report(new.pos, "SL104",
                        f"{word} {new.name} again? the one on line {prev.pos[0]} never got used, "
                        "this one just replaces it")

    def _report_all(self):
        if self.star or self.is_init:
            return
        for name, node in self.all_names:
            if name not in self.module.bindings:
                self.report(self._pos(node), "SL101", f"{name} is in __all__ but never defined")

    def _report_unused_imports(self):
        exported = {name for name, _ in self.all_names}
        scopes = [] if self.is_init else [self.module]
        scopes += [f for f in self.functions if not f.is_lambda]
        for scope in scopes:
            for name, bindings in scope.bindings.items():
                if name in scope.used or (scope is self.module and name in exported):
                    continue
                if name.startswith("__") and name.endswith("__"):
                    continue  # __doc__, __all__, __version__: re-exported on purpose
                for b in bindings:
                    if b.kind != "import" or b.skip:
                        continue
                    alias, stmt = b.node, b.stmt
                    if isinstance(stmt, ast.ImportFrom):
                        src = "." * stmt.level + (stmt.module or "")
                        what = f"{_w('from')} {src} {_w('import')} {alias.name}"
                    else:
                        what = f"{_w('import')} {alias.name}"
                    if alias.asname:
                        what += f" {_w('as')} {alias.asname}"
                    self.report(b.pos, "SL102", f"{what}, but {name} never gets used")

    def _report_unused_locals(self):
        for scope in self.functions:
            if scope.is_lambda or scope.dynamic:
                continue
            for name, bindings in scope.bindings.items():
                if name.startswith("_") or name in scope.used:
                    continue
                if not all(b.kind in ("assign", "walrus", "except") for b in bindings):
                    continue
                b = bindings[0]
                if b.kind == "except":
                    msg = f"{name} is never used. drop the `{_w('as')} {name}`"
                else:
                    msg = f"{name} gets a value but is never used"
                self.report(b.pos, "SL103", msg)


# --- unreachable code -------------------------------------------------------

def _stop_word(stmt):
    """The slang for why `stmt` ends its block, or None if code after it can run."""
    if isinstance(stmt, ast.Return):
        return _w("return")
    if isinstance(stmt, ast.Raise):
        return _w("raise")
    if isinstance(stmt, ast.Break):
        return _w("break")
    if isinstance(stmt, ast.Continue):
        return _w("continue")
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        name = _dotted(stmt.value.func)
        if name in _EXITS or name in ("sys.exit", "os._exit"):
            return f"{_w(name) if name in _EXITS else name}()"
    if isinstance(stmt, ast.If) and stmt.orelse:
        if _block_stops(stmt.body) and _block_stops(stmt.orelse):
            return f"an {_w('if')} where every branch bails"
    return None


def _block_stops(stmts):
    return any(_stop_word(s) for s in stmts)


def _check_unreachable(tree, report):
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if not isinstance(stmts, list):
                continue
            for i, stmt in enumerate(stmts[:-1]):
                word = _stop_word(stmt)
                if word is None:
                    continue
                nxt = stmts[i + 1]
                # `serve` then `drop` is the classic "empty generator" trick
                if not (isinstance(nxt, ast.Expr) and isinstance(nxt.value, (ast.Yield, ast.YieldFrom))):
                    report((nxt.lineno, nxt.col_offset), "SL201",
                           f"this never runs, it comes after {word}")
                break


# --- running it -------------------------------------------------------------

def _syntax_problem(filename, exc):
    from .vibes import keyword_hint
    msg = exc.msg or "invalid syntax"
    hint = keyword_hint(msg)
    if hint:
        msg += f" ({hint})"
    return Problem(filename, exc.lineno or 1, exc.offset or 1, "SL001", f"syntax is not it: {msg}")


def _check(source, filename):
    from .compiler import compile_source
    from .transpiler import python_col_to_slang, translate

    try:
        t = translate(source, filename)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile_source(source, filename)
            tree = ast.parse(t.python, filename)
    except SyntaxError as exc:
        return [_syntax_problem(filename, exc)]
    except (ValueError, RecursionError) as exc:
        return [Problem(filename, 1, 1, "SL001", f"can't compile it: {exc}")]

    py_lines = io.StringIO(t.python).readlines()
    problems = []

    def report(pos, code, message):
        row, byte_col = pos
        line = py_lines[row - 1] if 0 < row <= len(py_lines) else ""
        col = len(line.encode("utf-8")[:byte_col].decode("utf-8", "ignore"))
        problems.append(Problem(filename, row, python_col_to_slang(t.edits, row, col) + 1,
                                code, message))

    linter = _Linter(tree, filename, report)
    linter.py_lines = py_lines
    try:
        linter.visit(tree)
        linter.finish()
        _check_unreachable(tree, report)
    except RecursionError:
        return [Problem(filename, 1, 1, "SL001", "too deeply nested to lint")]
    return problems


def _ignores(source):
    """line -> set of ignored codes (an empty set means every code)."""
    found = {}
    try:
        comments = [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(source).readline)
                    if t.type == tokenize.COMMENT]
    except (tokenize.TokenError, SyntaxError):
        comments = [(i, line[line.index("#"):]) for i, line in enumerate(source.splitlines(), 1)
                    if "#" in line]
    for row, text in comments:
        m = _IGNORE_RE.search(text)
        if m:
            codes = {c.strip().upper() for c in (m.group(1) or "").split(",") if c.strip()}
            found[row] = codes
    return found


def _matches(code, patterns):
    return any(code.startswith(p) for p in patterns)


def lint_source(source: str, filename: str = "<slay>", select=None, ignore=None) -> List[Problem]:
    """Lint Slaython source and return its problems, sorted by position.

    `select` / `ignore` are optional lists of codes or code prefixes ("SL1").
    `# lint: ignore` comments are honoured.
    """
    ignored = _ignores(source)
    out = set()
    for p in _check(source, filename):
        codes = ignored.get(p.line)
        if codes is not None and (not codes or p.code in codes):
            continue
        if select and not _matches(p.code, select):
            continue
        if ignore and _matches(p.code, ignore):
            continue
        out.add(p)
    return sorted(out, key=lambda p: (p.line, p.col, p.code, p.message))


def lint_file(path: str, select=None, ignore=None) -> List[Problem]:
    from .runner import read_source
    try:
        source = read_source(path)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        problem = Problem(path, 1, 1, "SL001", f"can't read this file: {exc}")
        if (select and not _matches("SL001", select)) or (ignore and _matches("SL001", ignore)):
            return []
        return [problem]
    return lint_source(source, "<stdin>" if path == "-" else path, select, ignore)


def slay_files(paths):
    """.slay files under `paths` (files are taken as they are)."""
    for path in paths:
        if path == "-" or os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
            for name in sorted(files):
                if name.endswith(".slay"):
                    yield os.path.join(root, name)


def _code_list(text):
    return [c.strip().upper() for c in text.split(",") if c.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="slaython lint",
        description="Catch mistakes in .slay files before running them.",
        epilog="silence a line with `# lint: ignore` or `# lint: ignore[SL101]` at its end")
    p.add_argument("paths", nargs="*", help="files or folders (default: this folder)")
    p.add_argument("--select", type=_code_list, default=[], metavar="CODES",
                   help="only these checks, comma separated (prefixes like SL1 work)")
    p.add_argument("--ignore", type=_code_list, default=[], metavar="CODES",
                   help="skip these checks, comma separated")
    p.add_argument("--codes", action="store_true", help="list every check and exit")
    try:
        args = p.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if args.codes:
        for code, what in CODES.items():
            print(f"{code}  {what}")
        return 0
    for code in args.select + args.ignore:
        if not any(known.startswith(code) for known in CODES):
            sys.stderr.write(f"slaython lint: unknown code {code!r} (see --codes)\n")
            return 2
    paths = args.paths or ["."]
    missing = [path for path in paths if path != "-" and not os.path.exists(path)]
    if missing:
        sys.stderr.write(f"slaython lint: can't find {', '.join(missing)}\n")
        return 2

    files = bad_files = total = 0
    for path in slay_files(paths):
        files += 1
        problems = lint_file(path, args.select, args.ignore)
        if problems:
            bad_files += 1
            total += len(problems)
            for problem in problems:
                print(problem)
    if files == 0:
        print("no .slay files found")
        return 0
    if total == 0:
        print("all clean, no cap")
        return 0
    print(f"{total} problem{'s' * (total != 1)} in {bad_files} file{'s' * (bad_files != 1)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

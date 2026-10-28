"""Jupyter kernel: notebooks where every cell is Slaython.

    pip install slaython[jupyter]
    slaython kernel install            # then pick "Slaython" in Jupyter

The kernel is IPython's kernel with one extra step: each cell is translated
from Slaython after IPython has handled its own syntax (%magics, !shell,
`?` help), so everything IPython can do still works. ipykernel is only
imported when the kernel actually starts.
"""

import argparse
import ast
import collections
import inspect
import io
import json
import linecache
import os
import re
import shutil
import sys
import tempfile
import types

from . import __version__
from .compiler import point_at_slang
from .keywords import ALL_SLANG_WORDS, SLANG, SLANG_TO_PY, keyword_table
from .runner import print_error
from .transpiler import EDITS_BY_FILE, IncompleteSource, translate

KERNEL_NAME = "slaython"
DISPLAY_NAME = "Slaython"
INSTALL_HINT = "the Slaython kernel needs Jupyter. install it with: pip install slaython[jupyter]"

BANNER = (
    f"Slaython {__version__} kernel on Python {sys.version.split()[0]}. no cap.\n"
    "Type slang for the keyword sheet. %magics, !shell and ? help work like in IPython."
)

LANGUAGE_INFO = {
    "name": "slaython",
    "version": __version__,
    "mimetype": "text/x-slaython",
    "file_extension": ".slay",
    "pygments_lexer": "python",
    "codemirror_mode": {"name": "ipython", "version": 3},
}

_CHECK_FILE = "<slay-check>"
_CELL_FILE = "<slay-cell>"
_WORD_AT_END = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_FILE_LINE = re.compile(r'File "([^"]+)", line')
_IMPORT_LINE = re.compile(r"\s*(import|from|pullup|outta)\s")

# Words for tab completion, with the completion type Jupyter shows.
_SLANG_KINDS = {}
for _s in SLANG:
    for _w in _s.slang.split():
        if _w.isidentifier():
            _SLANG_KINDS.setdefault(_w, "function" if _s.kind in ("builtin", "helper") else "keyword")
COMPLETION_WORDS = sorted(w for w in ALL_SLANG_WORDS if w.isidentifier())


# --- translation ------------------------------------------------------------

# Translated cell (Python) -> (Slaython source, Translation). The compiler
# looks cells up here to finish `|>` / `shoot n:` and to point syntax errors
# at the Slaython line.
_TRANSLATED = collections.OrderedDict()
_KEEP = 64


def translate_lines(lines):
    """Input transformer: Slaython lines -> Python lines, same line numbers."""
    source = "".join(lines)
    try:
        t = translate(source, _CELL_FILE)
    except IncompleteSource as exc:
        # Show it as the plain SyntaxError it is.
        raise SyntaxError(exc.msg, (exc.filename, exc.lineno, exc.offset, exc.text)) from None
    if t.python != source or t.needs_tree_pass:
        _TRANSLATED[t.python] = (source, t)
        _TRANSLATED.move_to_end(t.python)
        while len(_TRANSLATED) > _KEEP:
            _TRANSLATED.popitem(last=False)
    return t.python.splitlines(keepends=True)


def _finish_tree(tree, slang, t, filename):
    """Turn `a | f` from `|>` into calls and wrap `shoot n:` in its retry loop."""
    from .compiler import finish_tree
    return finish_tree(tree, t, slang, filename)


def check_source(code):
    """Python to hand to IPython's is_complete check for a Slaython cell."""
    try:
        return translate(code, _CHECK_FILE).python
    except SyntaxError:
        return code  # unclosed bracket and the like: IPython spots those itself


# --- help and completion ------------------------------------------------------

def slang_info(word):
    """Explain a slang word (None if it isn't one)."""
    if not word or word not in _SLANG_KINDS:
        return None
    exact = [s for s in SLANG if s.slang == word]
    other = [s for s in SLANG if s.slang != word and word in s.slang.split()]
    lines = []
    for s in exact + other:
        lines.append(f"{s.slang}  ->  {s.python}")
        lines.append(f"    slang: {s.meaning}")
        lines.append(f"    why:   {s.why}")
    return "\n".join(lines)


def _python_builtin(word):
    """`print` for `yap`: the Python name to show docs for, if any."""
    py = SLANG_TO_PY.get(word)
    if py and py.isidentifier() and _SLANG_KINDS.get(word) == "function":
        return py
    return None


def add_slang_completions(reply, code, cursor_pos):
    """Put matching slang words in front of IPython's completions."""
    if cursor_pos is None:
        cursor_pos = len(code)
    before = code[:cursor_pos]
    m = _WORD_AT_END.search(before)
    if not m or (m.start() > 0 and code[m.start() - 1] == "."):
        return reply
    if _IMPORT_LINE.match(before[before.rfind("\n") + 1:]):
        return reply  # module names only
    start, prefix = m.start(), m.group()
    words = [w for w in COMPLETION_WORDS if w.startswith(prefix)]
    if not words or reply.get("status") != "ok":
        return reply
    matches = reply.get("matches") or []
    if matches and (reply.get("cursor_start"), reply.get("cursor_end")) != (start, cursor_pos):
        return reply  # IPython is completing something else (a path, a key, ...)
    new = [w for w in words if w not in matches]
    reply["matches"] = new + list(matches)
    reply["cursor_start"], reply["cursor_end"] = start, cursor_pos
    meta = reply.setdefault("metadata", {})
    types = meta.get("_jupyter_types_experimental")
    if types is not None:
        meta["_jupyter_types_experimental"] = [
            {"start": start, "end": cursor_pos, "text": w, "type": _SLANG_KINDS.get(w, "keyword"),
             "signature": ""} for w in new] + list(types)
    return reply


def import_line_for_completion(code):
    """`pullup o` -> `import o` (same length), so IPython completes module names."""
    lines = code.split("\n")
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("pullup ", "outta ")):
            line = re.sub(r"\boutta\b", "from ", line, count=1)
            lines[i] = re.sub(r"\bpullup\b", "import", line)
    return "\n".join(lines)


def _user_frames(tb, internal_dirs):
    """A copy of traceback `tb` without the kernel's own frames.

    Internal frames at the very end stay, so an error raised inside IPython
    still shows where it came from.
    """
    frames = []
    while tb is not None:
        frames.append(tb)
        tb = tb.tb_next
    internal = [os.path.abspath(t.tb_frame.f_code.co_filename).startswith(internal_dirs)
                for t in frames]
    while internal and internal[-1]:
        internal.pop()
    keep = [t for i, t in enumerate(frames) if i >= len(internal) or not internal[i]]
    new = None
    for t in reversed(keep):
        new = types.TracebackType(new, t.tb_frame, t.tb_lasti, t.tb_lineno)
    return new


def _then(result, fn):
    """fn(result), also when ipykernel hands back a coroutine."""
    if inspect.isawaitable(result):
        async def chain():
            return fn(await result)
        return chain()
    return fn(result)


class _SlangSheet:
    """`slang` in a cell shows the keyword sheet."""

    def __repr__(self):
        return keyword_table()

    def __call__(self):
        print(keyword_table())


# --- the kernel (needs ipykernel) ----------------------------------------------

_KERNEL_CLASS = None


def have_ipykernel():
    try:
        import ipykernel.ipkernel  # noqa: F401
    except ImportError:
        return False
    return True


def kernel_class():
    """The SlaythonKernel class. Imports ipykernel, so only call it when needed."""
    global _KERNEL_CLASS
    if _KERNEL_CLASS is None:
        _KERNEL_CLASS = _build_kernel_class()
    return _KERNEL_CLASS


def __getattr__(name):
    if name == "SlaythonKernel":
        return kernel_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _build_kernel_class():
    import IPython
    import ipykernel
    from IPython.utils.tokenutil import token_at_cursor
    from ipykernel.compiler import XCachingCompiler
    from ipykernel.ipkernel import IPythonKernel
    from ipykernel.zmqshell import ZMQInteractiveShell
    from traitlets import List, Type

    internal_dirs = tuple(os.path.dirname(os.path.abspath(m.__file__)) + os.sep
                          for m in (IPython, ipykernel, sys.modules[__package__]))

    class SlaythonCompiler(XCachingCompiler):
        """Finishes translated cells and keeps their Slaython lines for tracebacks."""

        def ast_parse(self, source, filename="<unknown>", symbol="exec"):
            entry = _TRANSLATED.get(source)
            try:
                tree = super().ast_parse(source, filename, symbol)
                if entry and entry[1].needs_tree_pass:
                    tree = _finish_tree(tree, entry[0], entry[1], filename)
            except SyntaxError as exc:
                if entry:
                    point_at_slang(exc, entry[0], entry[1].edits)
                raise
            if entry and filename != "<unknown>":
                EDITS_BY_FILE[filename] = entry[1].edits  # traceback carets
            return tree

        def cache(self, transformed_code, number=0, raw_code=None):
            name = super().cache(transformed_code, number, raw_code)
            if raw_code is not None and raw_code != transformed_code:
                # Tracebacks and inspect show the Slaython the user wrote.
                lines = [line + "\n" for line in raw_code.splitlines()]
                linecache.cache[name] = (len(raw_code), None, lines, name)
            return name

    class SlaythonShell(ZMQInteractiveShell):
        def slay_transform(self, lines):
            try:
                return translate_lines(lines)
            except SyntaxError as exc:
                exc.filename = f"<Cell In[{self.execution_count}]>"
                raise

        def _showtraceback(self, etype, evalue, stb):
            try:
                stb = self._slay_traceback(evalue, stb) or stb
            except Exception:  # noqa: BLE001 - never lose the error itself
                pass
            super()._showtraceback(etype, evalue, stb)

        def _slay_traceback(self, evalue, stb):
            if (not isinstance(evalue, BaseException) or isinstance(evalue, SystemExit)
                    or hasattr(evalue, "_render_traceback_")
                    or (stb and str(stb[0]).startswith("An exception has occurred"))):
                return None
            saved, buf = evalue.__traceback__, io.StringIO()
            try:
                evalue.__traceback__ = _user_frames(saved, internal_dirs)
                print_error(evalue, buf)
            finally:
                evalue.__traceback__ = saved
            text = _FILE_LINE.sub(self._cell_label, buf.getvalue())
            return text.rstrip("\n").split("\n")

        def _cell_label(self, m):
            name = m.group(1)
            label = self.compile.format_code_name(name)
            if label:
                return f"{label[0]} {label[1]}, line"
            if name.startswith("<Cell ") and name.endswith(">"):
                return f"{name[1:-1]}, line"
            return m.group(0)

        def _inspect(self, meth, oname, namespaces=None, **kw):
            info = slang_info(oname)
            if info is None:
                return super()._inspect(meth, oname, namespaces, **kw)
            print(info)
            py = _python_builtin(oname)
            if py:
                print()
                return super()._inspect(meth, py, namespaces, **kw)
            return None

    class SlaythonKernel(IPythonKernel):
        """IPython's kernel, with every cell translated from Slaython first."""

        implementation = "slaython"
        implementation_version = __version__
        language_info = LANGUAGE_INFO
        shell_class = Type(SlaythonShell)
        compiler_class = Type(SlaythonCompiler)
        help_links = List([
            {"text": "Slaython", "url": "https://github.com/memoliertorerr/Slaython"},
            {"text": "Python Reference",
             "url": "https://docs.python.org/%i.%i" % sys.version_info[:2]},
            {"text": "IPython Reference", "url": "https://ipython.readthedocs.io/en/stable/"},
        ]).tag(config=True)

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.shell.input_transformers_post.append(self.shell.slay_transform)
            self.shell.push({"slang": _SlangSheet()}, interactive=False)

        @property
        def banner(self):
            return BANNER

        def do_is_complete(self, code):
            return super().do_is_complete(check_source(code))

        def do_complete(self, code, cursor_pos):
            return _then(super().do_complete(import_line_for_completion(code), cursor_pos),
                         lambda reply: add_slang_completions(reply, code, cursor_pos))

        def do_inspect(self, code, cursor_pos, detail_level=0, omit_sections=()):
            if cursor_pos is None:
                cursor_pos = len(code)
            word = token_at_cursor(code, cursor_pos)
            info = slang_info(word)
            if info is None:
                return super().do_inspect(code, cursor_pos, detail_level, omit_sections)
            reply = {"status": "ok", "found": True, "data": {"text/plain": info}, "metadata": {}}
            py = _python_builtin(word)
            if not py:
                return reply

            def merge(inner):
                if inner.get("found"):
                    reply["data"]["text/plain"] = info + "\n\n" + inner["data"]["text/plain"]
                return reply
            return _then(super().do_inspect(py, len(py), detail_level, omit_sections), merge)

    return SlaythonKernel


def launch(argv=None):
    """Start the kernel (what `python -m slaython.kernel -f FILE` runs)."""
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(argv=argv, kernel_class=kernel_class())


# --- slaython kernel install / remove / list ----------------------------------

def kernel_json(display_name=DISPLAY_NAME):
    return {
        "argv": [sys.executable, "-m", "slaython.kernel", "-f", "{connection_file}"],
        "display_name": display_name,
        "language": "slaython",
    }


def _default_prefix():
    """Install into the active virtualenv/conda env, else into the user's folder."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    in_conda = os.environ.get("CONDA_PREFIX") == sys.prefix
    return sys.prefix if in_venv or in_conda else None


def _install(args):
    from jupyter_client.kernelspec import KernelSpecManager
    user, prefix = args.user, args.prefix
    if args.sys_prefix:
        prefix = sys.prefix
    if not user and prefix is None:
        prefix = _default_prefix()
        user = prefix is None
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "kernel.json"), "w", encoding="utf-8") as f:
            json.dump(kernel_json(args.display_name), f, indent=1)
            f.write("\n")
        try:
            dest = KernelSpecManager().install_kernel_spec(
                tmp, args.name, user=user, prefix=None if user else prefix)
        except ValueError as exc:
            sys.stderr.write(f"slaython kernel: {exc}\n")
            return 2
        except PermissionError as exc:
            sys.stderr.write(f"slaython kernel: no permission to write {exc.filename}. "
                             "try --user\n")
            return 1
    print(f"Installed the {args.display_name} kernel in {dest}")
    print(f'Pick "{args.display_name}" as the kernel in Jupyter. slay.')
    return 0


def _slaython_specs():
    """{name: resource_dir} of installed kernels whose language is Slaython."""
    from jupyter_client.kernelspec import KernelSpecManager
    found = {}
    for name, info in KernelSpecManager().get_all_specs().items():
        if info.get("spec", {}).get("language") == "slaython":
            found[name] = info["resource_dir"]
    return found


def _remove(args):
    if args.prefix:
        path = os.path.join(args.prefix, "share", "jupyter", "kernels", args.name)
        dirs = [path] if os.path.isdir(path) else []
    else:
        dirs = [d for n, d in _slaython_specs().items() if n == args.name]
    if not dirs:
        sys.stderr.write(f"slaython kernel: no Slaython kernel named {args.name!r} found\n")
        return 1
    for d in dirs:
        try:
            with open(os.path.join(d, "kernel.json"), encoding="utf-8") as f:
                language = json.load(f).get("language")
        except (OSError, ValueError):
            language = None
        if language != "slaython":
            sys.stderr.write(f"slaython kernel: {d} is not a Slaython kernel, leaving it alone\n")
            return 1
        try:
            shutil.rmtree(d)
        except PermissionError:
            sys.stderr.write(f"slaython kernel: no permission to remove {d}\n")
            return 1
        print(f"Removed {d}")
    return 0


def _list(args):
    specs = _slaython_specs()
    if not specs:
        print("No Slaython kernel installed. Run: slaython kernel install")
        return 0
    width = max(len(n) for n in specs)
    for name, path in sorted(specs.items()):
        print(f"{name.ljust(width)}  {path}")
    return 0


def main(argv=None):
    """`slaython kernel install|remove|list`. Returns an exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="slaython kernel",
                                description="Jupyter kernel for Slaython notebooks.")
    sub = p.add_subparsers(dest="command", metavar="install|remove|list")
    i = sub.add_parser("install", help="install the kernel so Jupyter can find it")
    where = i.add_mutually_exclusive_group()
    where.add_argument("--user", action="store_true", help="install for this user only")
    where.add_argument("--sys-prefix", action="store_true",
                       help="install into this Python's environment (sys.prefix)")
    where.add_argument("--prefix", metavar="PATH", help="install under PATH/share/jupyter/kernels")
    i.add_argument("--name", default=KERNEL_NAME, help=f"kernel name (default: {KERNEL_NAME})")
    i.add_argument("--display-name", default=DISPLAY_NAME,
                   help=f"name shown in Jupyter (default: {DISPLAY_NAME})")
    r = sub.add_parser("remove", aliases=["uninstall"], help="remove an installed kernel")
    r.add_argument("--name", default=KERNEL_NAME, help=f"kernel name (default: {KERNEL_NAME})")
    r.add_argument("--prefix", metavar="PATH", help="remove it from under PATH")
    sub.add_parser("list", help="show installed Slaython kernels")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.command is None:
        p.print_help()
        return 2
    if not have_ipykernel():
        sys.stderr.write(INSTALL_HINT + "\n")
        return 1
    if args.command == "install":
        return _install(args)
    if args.command in ("remove", "uninstall"):
        return _remove(args)
    return _list(args)


def _module_main(argv):
    """`python -m slaython.kernel`: start the kernel, or install/remove/list it."""
    if argv[:1] and argv[0] in ("install", "remove", "uninstall", "list", "-h", "--help"):
        return main(argv)
    if not have_ipykernel():
        sys.stderr.write(INSTALL_HINT + "\n")
        return 1
    launch(argv)
    return 0


if __name__ == "__main__":
    from slaython.kernel import _module_main as _run  # the importable copy, not __main__
    sys.exit(_run(sys.argv[1:]))

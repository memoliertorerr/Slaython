"""Jupyter / IPython support: `%load_ext slaython`, then `%%slay` cells.

    %load_ext slaython

    %%slay
    doomscroll x in range(3):
        yap(x)

`%slay <code>` runs one line, and its value is returned like any expression.
"""

import itertools

from .importer import install
from .runner import compile_slay

_cells = itertools.count(1)


def load_ipython_extension(ipython):
    install()

    def slay_magic(line, cell=None):
        ns = ipython.user_ns
        if cell is None:  # %slay <expression or statement>
            source = line.strip()
            if not source:
                return None
            name = f"<slay-cell-{next(_cells)}>"
            try:
                code = compile_slay(source, name, "eval")
            except SyntaxError:
                exec(compile_slay(source, name, "exec"), ns)
                return None
            return eval(code, ns)
        exec(compile_slay(cell, f"<slay-cell-{next(_cells)}>", "exec"), ns)
        return None

    ipython.register_magic_function(slay_magic, magic_kind="line_cell", magic_name="slay")


def unload_ipython_extension(ipython):
    ipython.magics_manager.magics["cell"].pop("slay", None)
    ipython.magics_manager.magics["line"].pop("slay", None)

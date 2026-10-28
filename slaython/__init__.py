"""Slaython: Python, but the keywords are gen-z slang.

Importing this package lets Python import .slay files directly:

    import slaython
    import my_module          # loads my_module.slay

Handy functions:

    slaython.transpile(src)   # Slaython -> Python source
    slaython.slayify(src)     # Python -> Slaython source
    slaython.slay(src)        # run Slaython code right here
    slaython.slay_eval(expr)  # evaluate a Slaython expression

In Jupyter or IPython: `%load_ext slaython`, then `%%slay` cells.
"""

__version__ = "0.2.0"

from .helpers import _sus, bedrot  # noqa: E402,F401
from .importer import install, uninstall  # noqa: E402
from .keywords import SLANG, keyword_table  # noqa: E402
from .runner import compile_slay, run_file, slay, slay_eval  # noqa: E402
from .transpiler import slayify, slayify_with_report, transpile  # noqa: E402

install()


def load_ipython_extension(ipython):
    """`%load_ext slaython` in Jupyter/IPython adds the %%slay cell magic."""
    from .ipython import load_ipython_extension as load
    load(ipython)


def unload_ipython_extension(ipython):
    from .ipython import unload_ipython_extension as unload
    unload(ipython)


__all__ = [
    "SLANG", "bedrot", "compile_slay", "install", "keyword_table", "run_file", "slay",
    "slay_eval", "slayify", "slayify_with_report", "transpile", "uninstall",
]

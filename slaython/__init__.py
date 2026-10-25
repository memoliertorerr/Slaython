"""Slaython: Python, but the keywords are gen-z slang.

Importing this package lets Python import .slay files directly:

    import slaython
    import my_module          # loads my_module.slay

Handy functions:

    slaython.transpile(src)   # Slaython -> Python source
    slaython.slayify(src)     # Python -> Slaython source
    slaython.slay(src)        # run Slaython code right here
    slaython.slay_eval(expr)  # evaluate a Slaython expression
"""

__version__ = "0.1.0"

from .importer import install, uninstall  # noqa: E402
from .keywords import SLANG, keyword_table  # noqa: E402
from .runner import compile_slay, run_file, slay, slay_eval  # noqa: E402
from .transpiler import slayify, slayify_with_report, transpile  # noqa: E402

install()

__all__ = [
    "SLANG", "compile_slay", "install", "keyword_table", "run_file", "slay",
    "slay_eval", "slayify", "slayify_with_report", "transpile", "uninstall",
]

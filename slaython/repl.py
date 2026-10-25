"""Interactive Slaython prompt."""

import code
import sys

from . import __version__
from .importer import install
from .keywords import keyword_table
from .transpiler import IncompleteSource, transpile
from .vibes import vibe_for


class SlayConsole(code.InteractiveConsole):
    def runsource(self, source, filename="<slay>", symbol="single"):
        try:
            python = transpile(source, filename)
        except IncompleteSource:
            return True  # wait for more lines
        except SyntaxError:
            self.showsyntaxerror(filename)
            return False
        return super().runsource(python, filename, symbol)

    def showsyntaxerror(self, filename=None, **kwargs):
        super().showsyntaxerror(filename, **kwargs)
        self.write(vibe_for(sys.last_value) + "\n")

    def showtraceback(self):
        super().showtraceback()
        self.write(vibe_for(sys.last_value) + "\n")


class _Slang:
    def __repr__(self):
        return keyword_table()

    def __call__(self):
        print(keyword_table())


BANNER = (
    f"Slaython {__version__} on Python {sys.version.split()[0]}. no cap.\n"
    "Type slang for the keyword sheet, exit() or Ctrl-D to dip."
)


def interact():
    install()
    try:
        import readline  # noqa: F401 - arrow keys and history
    except ImportError:
        pass
    sys.ps1, sys.ps2 = "slay> ", "  ... "
    console = SlayConsole(locals={"__name__": "__main__", "slang": _Slang()})
    console.interact(banner=BANNER, exitmsg="ight, dipping. stay slaying ✌️")

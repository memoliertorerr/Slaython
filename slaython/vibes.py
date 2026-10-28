"""Gen-z explanations printed under a normal Python traceback.

Turn them off with `slaython --no-vibes ...` or SLAYTHON_VIBES=0.
"""

import os
import re

from .keywords import PY_TO_SLANG

_VIBES = {
    "ZeroDivisionError": "bro really tried to divide by zero",
    "ModuleNotFoundError": "couldn't pullup that module. is it installed? check the spelling fr",
    "ImportError": "the pullup failed. that name isn't in the module",
    "NameError": "who? never heard of them. typo, or you forgot to define/pullup it",
    "UnboundLocalError": "you used it before giving it a value. viral or mutuals might help",
    "TypeError": "these types are not vibing with each other",
    "ValueError": "right type, but that value is not it",
    "KeyError": "that key got ghosted. it's not in the dict",
    "IndexError": "that index is out of range. touch grass and count again",
    "AttributeError": "that attribute isn't canon. it doesn't exist on this object",
    "RecursionError": "infinite recursion. you're stuck like doomscrolling at 3am",
    "AssertionError": "ongod check failed. that was cap",
    "IndentationError": "the indentation is mid. line your blocks up",
    "TabError": "tabs and spaces in one file? pick a side",
    "SyntaxError": "syntax is not it. check your slang",
    "FileNotFoundError": "that file ghosted you. it's not there",
    "PermissionError": "not allowed. you're not on the guest list",
    "NotImplementedError": "this part hasn't been cooked yet",
    "StopIteration": "nothing left to doomscroll",
    "OverflowError": "that number is too big. it's giving infinity",
    "MemoryError": "ran out of memory. absolutely cooked",
    "RuntimeError": "something crashed out while running",
    "TimeoutError": "took too long. it ghosted you",
    "UnicodeError": "those characters are not decoding. unicode said nah",
    "KeyboardInterrupt": "ight, you dipped",
}

_QUOTED = re.compile(r"'([A-Za-z_]+)'")


def vibes_enabled() -> bool:
    return os.environ.get("SLAYTHON_VIBES", "1").strip().lower() not in ("0", "false", "no", "off")


def vibe_for(exc: BaseException) -> str:
    """One-line gen-z explanation for an exception ("" when vibes are off)."""
    if not vibes_enabled():
        return ""
    for cls in type(exc).__mro__:
        if cls.__name__ in _VIBES:
            line = _VIBES[cls.__name__]
            break
    else:
        line = "that's an L. it crashed out"
    if isinstance(exc, SyntaxError) and exc.msg:
        hint = keyword_hint(exc.msg)
        if hint:
            line += f" ({hint})"
    return f"💀 {line}"


def keyword_hint(message: str) -> str:
    """Translate Python keywords quoted in an error message to slang."""
    found = []
    for word in _QUOTED.findall(message):
        if word in PY_TO_SLANG and word not in found:
            found.append(word)
    return ", ".join(f"'{w}' is '{PY_TO_SLANG[w]}' in Slaython" for w in found)

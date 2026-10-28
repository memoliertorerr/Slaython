"""Runtime helpers that Slaython code calls (lowkeysus, bedrot)."""

import sys
from time import sleep as bedrot  # noqa: F401  (bedrot(seconds) = time.sleep)

from .keywords import SUS_WORD

_NOTHING = object()


def _sus(source, line, *values):
    """Print `lowkeysus line N: <expression> = <value>` and return the value.

    Slaython calls this with the expression's source text and line number
    filled in, so `lowkeysus(total * 2)` shows exactly what you wrote.
    """
    if not values:
        print(f"{SUS_WORD} line {line}: (nothing to show)", file=sys.stderr)
        return None
    value = values[0] if len(values) == 1 else values
    print(f"{SUS_WORD} line {line}: {source} = {value!r}", file=sys.stderr)
    return value

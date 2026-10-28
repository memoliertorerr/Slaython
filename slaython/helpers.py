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


def headzortailz():
    """Flip a coin: nocap or cap."""
    import random
    return random.random() < 0.5


def pickone(items):
    """A random item from a sequence."""
    import random
    return random.choice(items)


class _speedrun:
    """`speedrun:` block timer. Prints `speedrun line N: 0.042s` to stderr."""

    def __init__(self, line, label=None):
        self.line, self.label = line, label

    def __enter__(self):
        import time
        self.started = time.perf_counter()
        return self

    def __exit__(self, *exc):
        import time
        took = time.perf_counter() - self.started
        where = f" {self.label}" if self.label is not None else f" line {self.line}"
        print(f"speedrun{where}: {took:.3f}s", file=sys.stderr)
        return False


class Lore:
    """Base for `lore` blueprints: every subclass becomes a dataclass.

    Options go in the header, like `lore Point(frozen=nocap):`.
    """

    def __init_subclass__(cls, **options):
        import dataclasses
        if options.get("slots"):
            raise TypeError("lore doesn't support slots=True")
        super().__init_subclass__()
        dataclasses.dataclass(cls, **options)


def _gang_values(count):
    """enum.auto() values for a `gang` line naming `count` members."""
    import enum
    if count == 1:
        return enum.auto()
    return tuple(enum.auto() for _ in range(count))


def _attempts(count):
    """Drives `shoot n:` retries: yields (attempt number, is last attempt)."""
    count = int(count)
    if count < 1:
        raise ValueError(f"shoot needs at least 1 try, got {count}")
    for attempt in range(1, count + 1):
        yield attempt, attempt == count

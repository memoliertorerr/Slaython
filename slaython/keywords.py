"""The Slaython slang sheet: every gen-z word and the Python it stands for.

Each entry records what the slang means and why it maps to its Python
keyword, so the table doubles as documentation (see ``slaython keywords``).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Slang:
    slang: str    # what you write in Slaython
    python: str   # what it becomes in Python
    meaning: str  # what the slang means in real life
    why: str      # why it maps to this keyword
    # keyword  - always a keyword
    # soft     - a keyword only at the start of a `...:` statement (match/case)
    # builtin  - another name for a Python builtin (yap = print)
    # compound - a two-word keyword (ornah fr = elif)
    # helper   - a Slaython runtime helper (bedrot = time.sleep)
    # syntax   - new syntax that Python doesn't have (runitfoo, deadass)
    # operator - a new operator (|>)
    kind: str = "keyword"


SLANG = [
    # --- values -------------------------------------------------------
    Slang("nocap", "True", "no lie, for real", "no cap = it's true"),
    Slang("cap", "False", "a lie", "cap = it's false"),
    Slang("ghosted", "None", "someone vanished on you", "nothing is there anymore"),
    # --- logic (`and` and `in` stay plain Python) -------------------------
    Slang("orr", "or", "or, stretched out", "this orr that"),
    Slang("nah", "not", "no", "flips it to the opposite"),
    Slang("literally", "is", "actually, for real (identity)", "x literally ghosted = x is None"),
    # --- control flow ---------------------------------------------------
    Slang("fr", "if", "for real?", "fr x > 5: = is x > 5, for real?"),
    Slang("ornah fr", "elif", "or nah... but for real?", "the else branch that checks again",
          kind="compound"),
    Slang("ornah", "else", "...or not", "what happens if it's a nah"),
    Slang("doomscroll", "for", "scrolling through post after post", "goes through items one by one"),
    Slang("lockedin", "while", "focused and not stopping", "stays locked in while the condition holds"),
    Slang("dip", "break", "leave, bounce", "dip out of the loop"),
    Slang("anyways", "continue", "moving on (after an awkward moment)", "skip the rest, on to the next"),
    Slang("chill", "pass", "relax, do nothing", "do nothing on purpose"),
    # --- functions & classes -------------------------------------------
    Slang("cook", "def", "make something great (let him cook)", "cook up a function"),
    Slang("serve", "return", "deliver, serve it up", "serve what you cooked"),
    Slang("nohead", "lambda", "no head, no name", "a function with no name"),
    Slang("drop", "yield", "release (a new drop)", "drops values one at a time"),
    Slang("blueprint", "class", "the original everyone copies", "objects are copies of the blueprint"),
    # --- errors ---------------------------------------------------------
    Slang("shoot", "try", "shoot your shot", "take a shot at something risky"),
    Slang("fumble", "except", "mess up a chance (fumble the bag)", "what runs when the code fumbles"),
    Slang("periodt", "finally", "end of discussion, final word", "always gets the last word"),
    Slang("yeet", "raise", "throw something hard", "yeet an error"),
    Slang("ongod", "assert", "on god, I swear", "swear this is true or it fails"),
    # --- modules --------------------------------------------------------
    Slang("pullup", "import", "come over", "pull up a module"),
    Slang("outta", "from", "out of", "outta math pullup sqrt"),
    Slang("aka", "as", "also known as", "gives something another name"),
    # --- scope & context ----------------------------------------------
    Slang("linkup", "with", "meet up", "link up with a resource, then part ways"),
    Slang("cancel", "del", "cancel someone", "remove it"),
    Slang("viral", "global", "known by everyone", "visible everywhere"),
    Slang("mutuals", "nonlocal", "people who follow each other", "shared with the outer function"),
    # --- async ------------------------------------------------------------
    Slang("lowkey", "async", "quietly, in the background", "runs lowkey in the background"),
    Slang("holdup", "await", "wait a minute", "hold up until it's done"),
    # --- pattern matching (soft keywords) -------------------------------
    Slang("spill", "match", "spill the tea, tell everything", "spill what's in the value", kind="soft"),
    Slang("pov", "case", "POV: a scenario", "each case is a POV scenario", kind="soft"),
    # --- builtins -------------------------------------------------------
    Slang("yap", "print", "talk a lot", "yap to the console", kind="builtin"),
    Slang("hmu", "input", "hit me up", "ask the user to hit you up with an answer", kind="builtin"),
    Slang("og", "super", "the original", "call the parent (OG) class", kind="builtin"),
    Slang("goat", "max", "greatest of all time", "the biggest item", kind="builtin"),
    Slang("flop", "min", "a fail, the worst one", "the smallest item", kind="builtin"),
    Slang("tierlist", "sorted", "ranking things best to worst", "rank everything", kind="builtin"),
    Slang("whoisyou", "type", "who even are you?", "asks a value what type it is", kind="builtin"),
    Slang("giving", "isinstance", "it's giving (resembles)", "giving(x, int) = it's giving int",
          kind="builtin"),
    Slang("skillissue", "Exception", "your own fault", "the base error type", kind="builtin"),
    Slang("touchgrass", "exit", "go outside, get offline", "quit the program", kind="builtin"),
    Slang("mee", "self", "me, myself", "the object talking about itself", kind="builtin"),
    Slang("howlongisit", "len", "how long is it?", "how many items something has", kind="builtin"),
    Slang("bruh", "breakpoint", "bruh... what is going on", "stop here and open the debugger",
          kind="builtin"),
    # --- helpers --------------------------------------------------------
    Slang("lowkeysus", "slaython.sus", "kinda suspicious", "prints an expression and its value",
          kind="helper"),
    Slang("bedrot", "time.sleep", "staying in bed doing nothing", "pause for some seconds",
          kind="helper"),
    Slang("headzortailz", "random coin flip", "heads or tails", "nocap or cap at random",
          kind="helper"),
    Slang("pickone", "random.choice", "just pick one", "a random item from a list", kind="helper"),
    Slang("corememory", "functools.cache", "a memory that stuck for good",
          "@corememory makes a function remember its answers", kind="helper"),
    Slang("squad", "asyncio.gather", "the whole crew", "run lowkey tasks together and wait for all",
          kind="helper"),
    # --- new syntax -----------------------------------------------------
    Slang("runitfoo", "for _ in range(n)", "run it back", "runitfoo 3: repeats a block 3 times",
          kind="syntax"),
    Slang("deadass", "constant", "dead serious", "deadass X = 1 can never be reassigned",
          kind="syntax"),
    Slang("maincharacter", 'if __name__ == "__main__"', "the main character",
          "runs only when the file is run directly", kind="syntax"),
    Slang("lore", "@dataclass class", "the backstory, just the facts",
          "a blueprint that only holds data", kind="syntax"),
    Slang("gang", "Enum class", "a fixed crew", "a fixed set of named values", kind="syntax"),
    Slang("speedrun", "timer block", "doing it as fast as possible",
          "times the block and prints how long it took", kind="syntax"),
    Slang("vibecheck", "inline test", "checking the vibe",
          "a test block that only slaython test runs", kind="syntax"),
    Slang("idc", "contextlib.suppress", "I don't care", "idc ValueError: runs a block and ignores that error",
          kind="syntax"),
    Slang("|>", "pipe: x |> f = f(x)", "pass it on", "feeds a value into the next function",
          kind="operator"),
]

# Python keywords that deliberately have no slang: write them as in Python.
KEPT_PYTHON = ("and", "in")

# Single-word slang -> Python, for word-for-word swaps.
SLANG_TO_PY = {s.slang: s.python for s in SLANG if s.kind in ("keyword", "soft", "builtin")}
# Python -> slang (for slayify).
PY_TO_SLANG = {s.python: s.slang for s in SLANG if s.kind in ("keyword", "soft", "builtin", "compound")}
# Words that only act as keywords at the start of a statement ending in ':'.
SOFT_SLANG = {s.slang for s in SLANG if s.kind == "soft"}
SOFT_PY = {s.python for s in SLANG if s.kind == "soft"}
# Two-word slang keywords: (first, second) -> Python.
COMPOUND_SLANG = {tuple(s.slang.split()): s.python for s in SLANG if s.kind == "compound"}
# Helpers become calls into the slaython package at run time.
HELPERS = {
    "lowkeysus": '__import__("slaython")._sus',
    "bedrot": '__import__("slaython").bedrot',
    "headzortailz": '__import__("slaython").headzortailz',
    "pickone": '__import__("slaython").pickone',
    "corememory": '__import__("functools").cache',
    "squad": '__import__("asyncio").gather',
}
SUS_WORD = "lowkeysus"
REPEAT_WORD = "runitfoo"
CONST_WORD = "deadass"
MAIN_WORD = "maincharacter"
DATACLASS_WORD = "lore"
ENUM_WORD = "gang"
TIMER_WORD = "speedrun"
INLINE_TEST_WORD = "vibecheck"
IGNORE_WORD = "idc"
PIPE = "|>"

ALL_SLANG_WORDS = (
    set(SLANG_TO_PY) | set(HELPERS)
    | {s.slang for s in SLANG if s.kind == "syntax"}
    | {w for pair in COMPOUND_SLANG for w in pair}
)


def keyword_table():
    """Return the slang sheet as aligned text."""
    width = max(len(s.slang) for s in SLANG)
    pywidth = max(len(s.python) for s in SLANG)
    lines = [f"{'slaython'.ljust(width)}  {'python'.ljust(pywidth)}  why"]
    lines.append(f"{'-' * width}  {'-' * pywidth}  {'-' * 40}")
    for s in SLANG:
        lines.append(f"{s.slang.ljust(width)}  {s.python.ljust(pywidth)}  {s.why}")
    for py in KEPT_PYTHON:
        lines.append(f"{py.ljust(width)}  {py.ljust(pywidth)}  plain Python, no slang")
    return "\n".join(lines)

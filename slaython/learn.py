"""`slaython learn`: a short interactive tutorial with tiny exercises.

Lessons are plain data (see LESSONS at the bottom). To add one, append a
Lesson with a unique key; progress is stored by key, so the order can
change without losing anyone's progress.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import re
import sys
import tokenize
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from .runner import compile_slay, print_error
from .transpiler import IncompleteSource, transpile

PROGRESS_ENV = "SLAYTHON_LEARN_FILE"
DEFAULT_PROGRESS = os.path.join("~", ".slaython_learn.json")
CODE_FILENAME = "<learn>"
MAX_STEPS = 1_000_000  # line events before a run counts as an infinite loop
PS1, PS2 = "slay> ", "  ... "

COMMANDS = {
    "hint": "hint", "solution": "solution", "skip": "skip", "back": "back",
    "quit": "quit", "exit": "quit", "quit()": "quit", "exit()": "quit",
    "touchgrass()": "quit", "help": "help",
}
COMMAND_LINE = "commands: hint, solution, skip, back, quit"
WINS = ("ate that.", "no cap, that's right.", "slay, you got it.", "W. clean.")

USAGE = """\
usage: slaython learn [N] [--list] [--reset]

  slaython learn          pick up where you left off
  slaython learn N        jump to lesson N
  slaython learn --list   show every lesson and what you finished
  slaython learn --reset  forget your progress and start over

Progress lives in ~/.slaython_learn.json (set SLAYTHON_LEARN_FILE to move it).
"""


# --- lessons as data -------------------------------------------------------

@dataclass(frozen=True)
class Check:
    """How to grade an answer: exact output, a predicate, or both."""
    output: Optional[str] = None
    # predicate(output, namespace) -> bool; raising counts as a fail
    predicate: Optional[Callable[[str, dict], bool]] = None
    wants: str = ""  # plain words for what the predicate wants, shown on a fail


def output_is(text: str, predicate=None, wants: str = "") -> Check:
    return Check(output=text, predicate=predicate, wants=wants)


def passes(predicate, wants: str) -> Check:
    return Check(predicate=predicate, wants=wants)


@dataclass(frozen=True)
class Lesson:
    key: str          # stable id saved in the progress file
    title: str
    explanation: str
    example: str
    task: str
    check: Check
    hint: str
    solution: str     # no blank lines: a blank line submits
    uses: Tuple[str, ...] = field(default=())  # words the answer must use


@dataclass
class Result:
    output: str = ""
    namespace: dict = field(default_factory=dict)
    error: Optional[BaseException] = None
    too_long: bool = False


@dataclass
class Verdict:
    ok: bool
    message: str = ""
    expected: Optional[str] = None
    got: Optional[str] = None


# --- running code ---------------------------------------------------------

class _TooLong(BaseException):
    """Raised by the step limit. BaseException so `fumble skillissue` can't eat it."""


@contextlib.contextmanager
def _step_limit(limit):
    previous = sys.gettrace()
    if previous is not None:  # a debugger or coverage is running: leave it alone
        yield
        return
    steps = 0

    def tracer(frame, event, arg):
        nonlocal steps
        if event == "line":
            steps += 1
            if steps > limit:
                raise _TooLong
        return tracer

    sys.settrace(tracer)
    try:
        yield
    finally:
        sys.settrace(previous)


def run_code(source: str, limit: int = MAX_STEPS) -> Result:
    """Run Slaython code in a fresh namespace.

    stdout and stderr are captured together. stdin is empty, so hmu() can't
    eat the learner's next answer.
    """
    result = Result(namespace={"__name__": "__main__", "__builtins__": builtins})
    buf = io.StringIO()
    try:
        code = compile_slay(source, CODE_FILENAME)
    except SyntaxError as exc:
        result.error = exc
        return result
    real_stdin = sys.stdin
    sys.stdin = io.StringIO("")
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            with _step_limit(limit):
                exec(code, result.namespace)
        except _TooLong:
            result.too_long = True
        except SystemExit:
            pass  # touchgrass() just ends the run
        except KeyboardInterrupt as exc:
            result.error = exc
        except BaseException as exc:  # noqa: BLE001 - show the learner every error
            result.error = exc
        finally:
            sys.stdin = real_stdin
    result.output = buf.getvalue()
    return result


def _clean(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _names_used(source: str):
    try:
        return {tok.string for tok in tokenize.generate_tokens(io.StringIO(source).readline)
                if tok.type == tokenize.NAME}
    except (tokenize.TokenError, SyntaxError):
        return set(re.findall(r"[A-Za-z_]\w*", source))


def grade(lesson: Lesson, source: str, result: Result) -> Verdict:
    """Decide whether a finished run solves the lesson."""
    check = lesson.check
    if result.too_long:
        return Verdict(False, "that ran way too long. infinite loop? make sure it can end "
                              "(dip, or a condition that turns cap).")
    if isinstance(result.error, EOFError):
        return Verdict(False, "no hmu() in these lessons, put the value in a variable instead")
    if result.error is not None:
        return Verdict(False, "that one errored, so it doesn't count yet")
    got = _clean(result.output)
    if check.output is not None and got != _clean(check.output):
        return Verdict(False, "the output isn't quite right", _clean(check.output), got)
    if check.predicate is not None:
        try:
            ok = bool(check.predicate(result.output, result.namespace))
        except Exception:  # noqa: BLE001 - a missing name etc. is just a fail
            ok = False
        if not ok:
            return Verdict(False, f"not quite. wanted: {check.wants}", got=got)
    missing = [w for w in lesson.uses if w not in _names_used(source)]
    if missing:
        words = ", ".join(missing)
        return Verdict(False, f"right result, but use {words} for this one, that's the point")
    return Verdict(True)


# --- progress -------------------------------------------------------------

def progress_path() -> str:
    return os.path.expanduser(os.environ.get(PROGRESS_ENV) or DEFAULT_PROGRESS)


def load_progress() -> dict:
    try:
        with open(progress_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"done": [], "at": None}
    if not isinstance(data, dict):
        return {"done": [], "at": None}
    done = [k for k in data.get("done", []) if isinstance(k, str)]
    at = data.get("at") if isinstance(data.get("at"), str) else None
    return {"done": done, "at": at}


def save_progress(progress: dict) -> bool:
    path = progress_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "done": progress["done"], "at": progress["at"]}, f,
                      indent=2)
            f.write("\n")
    except OSError as exc:
        print(f"(couldn't save progress to {path}: {exc.strerror or exc})")
        return False
    return True


# --- terminal output -------------------------------------------------------

def _use_color() -> bool:
    try:
        return sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    except (AttributeError, ValueError):
        return False


def _style(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _use_color() else text


def bold(text):
    return _style(text, "1")


def dim(text):
    return _style(text, "2")


def green(text):
    return _style(text, "32")


def red(text):
    return _style(text, "31")


def _indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _shown(text: str) -> str:
    return _indent(text) if text else "    (nothing)"


def show_lesson(lessons, index):
    lesson = lessons[index]
    print()
    print(bold(f"Lesson {index + 1}/{len(lessons)}: {lesson.title}"))
    print()
    print(lesson.explanation.strip())
    print()
    print(dim("example:"))
    print(_indent(lesson.example.strip()))
    result = run_code(lesson.example)
    if result.output:
        print(dim("output:"))
        print(_indent(result.output.rstrip("\n")))
    if result.error is not None:  # only happens if the language changed under us
        print_error(result.error, file=sys.stdout)
    print()
    print(bold("your turn:"))
    print(lesson.task.strip())
    print(dim(f"(an empty line runs your code. {COMMAND_LINE})"))


# --- reading answers -------------------------------------------------------

def _incomplete(source: str) -> bool:
    try:
        transpile(source, CODE_FILENAME)
    except IncompleteSource:
        return True
    except SyntaxError:
        return False
    return False


def read_answer():
    """Return ("code", text), ("cmd", name) or ("eof", None)."""
    lines = []
    while True:
        try:
            line = input(PS2 if lines else PS1)
        except EOFError:
            if lines:
                print()
                return "code", "\n".join(lines) + "\n"
            return "eof", None
        except KeyboardInterrupt:
            print()
            return "cmd", "quit"
        if not lines:
            word = line.strip().lower()
            if word in COMMANDS:
                return "cmd", COMMANDS[word]
            if not word:
                continue
        if not line.strip():
            source = "\n".join(lines) + "\n"
            if _incomplete(source):
                lines.append(line)
                continue
            return "code", source
        lines.append(line)


# --- the session -----------------------------------------------------------

def _first_unfinished(lessons, done):
    for i, lesson in enumerate(lessons):
        if lesson.key not in done:
            return i
    return None


def _start_index(lessons, progress):
    keys = [lesson.key for lesson in lessons]
    if progress["at"] in keys:
        return keys.index(progress["at"])
    return _first_unfinished(lessons, set(progress["done"]))


def _report_attempt(lesson, source, result):
    """Show what the code printed and how it went. Returns True on success."""
    if result.output:
        print(result.output.rstrip("\n"))
    if result.error is not None:
        print_error(result.error, file=sys.stdout)
    verdict = grade(lesson, source, result)
    if verdict.ok:
        return True
    print(red(verdict.message))
    if verdict.expected is not None:
        print(dim("expected:"))
        print(_shown(verdict.expected))
        print(dim("got:"))
        print(_shown(verdict.got or ""))
    print(dim("try again, or type hint."))
    return False


def _finish(lessons, progress):
    print()
    skipped = [i + 1 for i, lesson in enumerate(lessons) if lesson.key not in progress["done"]]
    if skipped:
        nums = ", ".join(str(n) for n in skipped)
        print(bold("that's the last lesson."))
        print(f"you still skipped some: {nums}. run `slaython learn N` to go back to one.")
    else:
        print(bold("you finished every lesson. that's the whole language, periodt."))
        print("next up: run `slaython` for the REPL, or write a .slay file and "
              "run `slaython file.slay`.")


def run_session(lessons, index, progress) -> int:
    wins = 0
    while 0 <= index < len(lessons):
        lesson = lessons[index]
        progress["at"] = lesson.key
        save_progress(progress)
        show_lesson(lessons, index)
        move = None
        while move is None:
            kind, value = read_answer()
            if kind == "eof" or value == "quit":
                print("progress saved. run `slaython learn` to pick up where you left off.")
                return 0
            if kind == "cmd":
                if value == "hint":
                    print(lesson.hint.strip())
                elif value == "solution":
                    print(dim("one way to do it (type it in yourself to finish the lesson):"))
                    print(_indent(lesson.solution.strip()))
                elif value == "skip":
                    print("skipped. you can come back with `back` or `slaython learn "
                          f"{index + 1}`.")
                    move = 1
                elif value == "back":
                    if index == 0:
                        print("this is the first lesson, nothing before it.")
                    else:
                        move = -1
                elif value == "help":
                    print(f"type code, then an empty line to run it. {COMMAND_LINE}")
                continue
            result = run_code(value)
            if _report_attempt(lesson, value, result):
                if lesson.key not in progress["done"]:
                    progress["done"].append(lesson.key)
                print(green(WINS[wins % len(WINS)]) + dim(" progress saved."))
                wins += 1
                move = 1
        index += move
    progress["at"] = None
    save_progress(progress)
    _finish(lessons, progress)
    return 0


def list_lessons(lessons, progress):
    done = set(progress["done"])
    current = _start_index(lessons, progress)
    for i, lesson in enumerate(lessons):
        mark = "x" if lesson.key in done else " "
        here = "  <- you are here" if i == current else ""
        print(f"[{mark}] {i + 1:>2}. {lesson.title}{here}")
    print(f"{len(done & {l.key for l in lessons})}/{len(lessons)} done")


def main(argv=None, lessons=None) -> int:
    """Entry point for `slaython learn [N] [--list] [--reset]`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    lessons = LESSONS if lessons is None else lessons
    jump = None
    for arg in argv:
        if arg in ("-h", "--help"):
            sys.stdout.write(USAGE)
            return 0
        if arg == "--reset":
            try:
                os.remove(progress_path())
            except FileNotFoundError:
                pass
            except OSError as exc:
                sys.stderr.write(f"slaython learn: couldn't reset: {exc.strerror or exc}\n")
                return 1
            print("progress wiped. fresh start, bestie.")
            return 0
        if arg == "--list":
            list_lessons(lessons, load_progress())
            return 0
        if arg.isdigit() and jump is None:
            jump = int(arg)
            if not 1 <= jump <= len(lessons):
                sys.stderr.write(f"slaython learn: there are lessons 1 to {len(lessons)}, "
                                 f"not {jump}\n")
                return 2
            continue
        sys.stderr.write(f"slaython learn: don't know {arg!r}\n{USAGE}")
        return 2

    progress = load_progress()
    if jump is not None:
        index = jump - 1
    else:
        index = _start_index(lessons, progress)
        if index is None:
            print("you already finished every lesson. `slaython learn N` replays one, "
                  "`slaython learn --reset` starts over.")
            return 0
    if sys.stdin.isatty():
        try:
            import readline  # noqa: F401 - arrow keys and history
        except ImportError:
            pass
    if index == 0 and not progress["done"]:
        print(bold("welcome to slaython learn."))
        print("Slaython is Python with slang keywords. each lesson shows an example, "
              "then you write a little code.")
        print("type your code, then press Enter on an empty line to run it.")
    return run_session(lessons, index, progress)


# --- the lessons -----------------------------------------------------------

def _lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _raises(fn, *args) -> bool:
    try:
        fn(*args)
    except Exception:  # noqa: BLE001
        return True
    return False


LESSONS = [
    Lesson(
        key="yap",
        title="yap and values",
        explanation="""
yap() prints things, it's Python's print(). Text goes in quotes, numbers
don't. The three special values are nocap (True), cap (False) and
ghosted (None). Comments start with #, like in Python.
""",
        example="""\
yap("hi bestie")
yap(2 + 3)
yap(nocap, cap, ghosted)
""",
        task="yap the text slay, then on the next line yap nocap.",
        check=output_is("slay\nTrue"),
        hint='Two lines: yap("slay") and then yap(nocap). Then an empty line to run it.',
        solution='yap("slay")\nyap(nocap)\n',
        uses=("yap", "nocap"),
    ),
    Lesson(
        key="fr",
        title="variables, fr, ornah fr, ornah",
        explanation="""
Variables work like Python: name = value. fr is if, ornah fr is elif,
and ornah is else. Combine checks with and, orr and nah (not).
x literally ghosted means x is None.
""",
        example="""\
vibe = 7
fr vibe > 8:
    yap("immaculate")
ornah fr vibe > 5 and nah vibe literally ghosted:
    yap("decent")
ornah:
    yap("mid")
""",
        task="""\
set likes = 120. fr likes is over 100, yap viral. ornah fr it's over 10,
yap mid. ornah, yap flop era.""",
        check=output_is("viral"),
        hint="Start with likes = 120, then fr likes > 100: and indent the yap under it. "
             "ornah fr and ornah lines go back to the left.",
        solution="""\
likes = 120
fr likes > 100:
    yap("viral")
ornah fr likes > 10:
    yap("mid")
ornah:
    yap("flop era")
""",
        uses=("fr", "ornah"),
    ),
    Lesson(
        key="loops",
        title="doomscroll, range and runitfoo",
        explanation="""
doomscroll is a for loop: it goes through items one by one.
range(a, b) counts from a up to (not including) b. runitfoo n: is
Slaython-only, it just repeats a block n times.
""",
        example="""\
doomscroll app in ["tok", "gram", "snap"]:
    yap(app)
runitfoo 2:
    yap("run it back")
""",
        task="""\
doomscroll over range to yap the numbers 1 to 5, one per line. Then use
runitfoo to yap slay 3 times.""",
        check=output_is("1\n2\n3\n4\n5\nslay\nslay\nslay"),
        hint="range(1, 6) gives 1 to 5. doomscroll n in range(1, 6): then yap(n) "
             "indented. After that, runitfoo 3: with yap(\"slay\") indented.",
        solution="""\
doomscroll n in range(1, 6):
    yap(n)
runitfoo 3:
    yap("slay")
""",
        uses=("doomscroll", "runitfoo"),
    ),
    Lesson(
        key="lockedin",
        title="lockedin, dip and anyways",
        explanation="""
lockedin is a while loop: it keeps going while the condition holds.
dip (break) leaves the loop right away. anyways (continue) skips the rest
of this round and goes to the next one. If a loop never ends, Ctrl-C
stops it.
""",
        example="""\
n = 0
lockedin n < 10:
    n += 1
    fr n % 2 == 0:
        anyways
    fr n > 7:
        dip
    yap(n)
""",
        task="""\
start with n = 0 and loop with lockedin nocap:. Each round add 1 to n.
dip once n is over 10, use anyways to skip multiples of 3, and yap
every n that's left.""",
        check=output_is("1\n2\n4\n5\n7\n8\n10"),
        hint="Inside the loop: n += 1, then fr n > 10: dip, then fr n % 3 == 0: "
             "anyways, then yap(n).",
        solution="""\
n = 0
lockedin nocap:
    n += 1
    fr n > 10:
        dip
    fr n % 3 == 0:
        anyways
    yap(n)
""",
        uses=("lockedin", "dip", "anyways"),
    ),
    Lesson(
        key="cook",
        title="cook, serve and nohead",
        explanation="""
cook makes a function (def) and serve hands back a value (return).
nohead makes a tiny function with no name (lambda): nohead x: x + 1.
chill (pass) is a line that does nothing, handy for empty blocks.
""",
        example="""\
cook hype(name, times=1):
    serve name + "!" * times
yap(hype("bestie", 3))
louder = nohead s: s.upper()
yap(louder("ok"))
""",
        task="""\
cook ratio(a, b) that serves a divided by b. Make double with nohead so it
doubles a number. Then yap(ratio(10, 4)) and yap(double(21)).""",
        check=output_is(
            "2.5\n42",
            lambda out, ns: (ns["ratio"](1, 2) == 0.5 and ns["double"](4) == 8
                             and ns["double"].__name__ == "<lambda>"),
            "ratio(a, b) that divides, and double made with nohead"),
        hint="cook ratio(a, b): then serve a / b indented. "
             "double = nohead x: x * 2 on its own line.",
        solution="""\
cook ratio(a, b):
    serve a / b
double = nohead x: x * 2
yap(ratio(10, 4))
yap(double(21))
""",
        uses=("cook", "serve", "nohead"),
    ),
    Lesson(
        key="blueprint",
        title="blueprint, mee and og",
        explanation="""
blueprint makes a class. Inside it, mee is self: the object talking
about itself. A blueprint can build on another one, and og() is super():
it calls the original version of a method from the parent.
""",
        example="""\
blueprint Pet:
    cook __init__(mee, name):
        mee.name = name
    cook speak(mee):
        serve mee.name + " makes a sound"
blueprint Cat(Pet):
    cook speak(mee):
        serve og().speak() + ", meow"
yap(Cat("mochi").speak())
""",
        task="""\
make a blueprint Bestie with __init__(mee, name) that stores name, and a
method hype(mee) that serves the name + " ate". Then make Twin(Bestie)
whose hype serves og().hype() + " twice". yap(Twin("kai").hype()).""",
        check=output_is(
            "kai ate twice",
            lambda out, ns: (issubclass(ns["Twin"], ns["Bestie"])
                             and ns["Bestie"]("mia").hype() == "mia ate"),
            "a Bestie blueprint and a Twin blueprint built on it"),
        hint="Copy the shape of the example: Pet becomes Bestie, speak becomes hype, "
             "and Cat becomes Twin(Bestie).",
        solution="""\
blueprint Bestie:
    cook __init__(mee, name):
        mee.name = name
    cook hype(mee):
        serve mee.name + " ate"
blueprint Twin(Bestie):
    cook hype(mee):
        serve og().hype() + " twice"
yap(Twin("kai").hype())
""",
        uses=("blueprint", "mee", "og"),
    ),
    Lesson(
        key="errors",
        title="shoot, fumble, periodt, yeet, ongod",
        explanation="""
shoot is try, fumble is except, periodt is finally (it always runs).
yeet raises an error: yeet ValueError("nope"), or just yeet "nope" to
get a plain skillissue (Exception). ongod is assert: ongod x > 0 fails
loudly if it's cap.
""",
        example="""\
shoot:
    yap(10 / 0)
fumble ZeroDivisionError:
    yap("can't split the bill by zero")
periodt:
    yap("this always runs")
shoot:
    yeet "that's cap"
fumble skillissue aka e:
    yap("caught:", e)
ongod 2 + 2 == 4
""",
        task="""\
cook check(likes): fr likes < 0, yeet "likes can't be negative", otherwise
serve likes. Then shoot check(-5), fumble skillissue aka e and yap(e),
periodt yap("checked"). Finish with ongod check(3) == 3.""",
        check=output_is(
            "likes can't be negative\nchecked",
            lambda out, ns: ns["check"](3) == 3 and _raises(ns["check"], -1),
            "check(likes) that yeets for negative likes"),
        hint="Inside check: fr likes < 0: yeet \"likes can't be negative\", then serve "
             "likes. The shoot / fumble skillissue aka e / periodt blocks come after.",
        solution="""\
cook check(likes):
    fr likes < 0:
        yeet "likes can't be negative"
    serve likes
shoot:
    check(-5)
fumble skillissue aka e:
    yap(e)
periodt:
    yap("checked")
ongod check(3) == 3
""",
        uses=("shoot", "fumble", "periodt", "yeet", "ongod"),
    ),
    Lesson(
        key="builtins",
        title="goat, flop, tierlist, howlongisit, giving",
        explanation="""
Some builtins got renamed too. goat is max, flop is min, tierlist is
sorted, howlongisit is len, giving is isinstance (giving(x, int): it's
giving int), and whoisyou is type. Modules work like Python, with
pullup (import), outta (from) and aka (as): outta math pullup sqrt.
""",
        example="""\
scores = [7, 10, 3]
yap(goat(scores), flop(scores))
yap(tierlist(scores, reverse=nocap))
yap(howlongisit(scores), whoisyou(scores))
yap(giving(3, int))
""",
        task="""\
start with fits = [8, 3, 10, 6]. On separate lines, yap the goat, the flop,
the list ranked with tierlist, how long it is, and whether fits is giving
list.""",
        check=output_is("10\n3\n[3, 6, 8, 10]\n4\nTrue"),
        hint="Five yap lines: goat(fits), flop(fits), tierlist(fits), "
             "howlongisit(fits), giving(fits, list).",
        solution="""\
fits = [8, 3, 10, 6]
yap(goat(fits))
yap(flop(fits))
yap(tierlist(fits))
yap(howlongisit(fits))
yap(giving(fits, list))
""",
        uses=("goat", "flop", "tierlist", "howlongisit", "giving"),
    ),
    Lesson(
        key="deadass",
        title="deadass and lowkeysus",
        explanation="""
deadass NAME = value makes a constant. Assigning NAME again anywhere in
the file is an error before anything even runs. lowkeysus(x) is a quick
debug print: it shows the line, the code you wrote and its value, then
hands the value back. (bedrot(2) pauses for 2 seconds, if you ever need
a nap.)
""",
        example="""\
deadass MAX_LIKES = 100
likes = 40
lowkeysus(likes * 2)
yap(MAX_LIKES - likes)
""",
        task="""\
make deadass MAX_FITS = 3 and set fits = 5. Use lowkeysus to peek at
fits - MAX_FITS, then yap too many if fits is over MAX_FITS.""",
        check=passes(
            lambda out, ns: (ns["MAX_FITS"] == 3
                             and re.search(r"^lowkeysus line \d+: .+ = 2$", out, re.M)
                             and _lines(out)[-1] == "too many"),
            "a lowkeysus line that shows 2, then too many"),
        hint="lowkeysus(fits - MAX_FITS) on its own line, then fr fits > MAX_FITS: "
             "with yap(\"too many\") under it.",
        solution="""\
deadass MAX_FITS = 3
fits = 5
lowkeysus(fits - MAX_FITS)
fr fits > MAX_FITS:
    yap("too many")
""",
        uses=("deadass", "lowkeysus"),
    ),
    Lesson(
        key="project",
        title="mini project: rate the squad",
        explanation="""
Time to put it together. You'll use cook, fr, blueprint, doomscroll and
a slang builtin or two. Take it slow, and remember: no empty lines
inside your code, the empty line is what runs it.
""",
        example="""\
squad = {"mia": 9, "kai": 4}
doomscroll name in tierlist(squad):
    yap(name, squad[name])
yap(goat(squad, key=squad.get))
""",
        task="""\
1) cook rate(score): serve "ate" for 8 and up, "mid" for 5 and up,
   otherwise "flop".
2) blueprint Squad with __init__(mee, scores) storing a dict of
   name -> score, and best(mee) serving the name with the goat score.
3) make s = Squad({"mia": 9, "kai": 4, "zoe": 6}), doomscroll the names
   in tierlist order and yap(name, rate(score)) for each, then
   yap("best:", s.best()).""",
        check=output_is(
            "kai flop\nmia ate\nzoe mid\nbest: mia",
            lambda out, ns: ([ns["rate"](x) for x in (8, 7.9, 5, 4.9)]
                             == ["ate", "mid", "mid", "flop"]
                             and ns["Squad"]({"a": 1, "b": 3}).best() == "b"),
            "rate() with the right cutoffs and a Squad blueprint whose best() works"),
        hint="best can serve goat(mee.scores, key=mee.scores.get). For the loop: "
             "doomscroll name in tierlist(s.scores): then yap(name, rate(s.scores[name])).",
        solution="""\
cook rate(score):
    fr score >= 8:
        serve "ate"
    ornah fr score >= 5:
        serve "mid"
    serve "flop"
blueprint Squad:
    cook __init__(mee, scores):
        mee.scores = scores
    cook best(mee):
        serve goat(mee.scores, key=mee.scores.get)
s = Squad({"mia": 9, "kai": 4, "zoe": 6})
doomscroll name in tierlist(s.scores):
    yap(name, rate(s.scores[name]))
yap("best:", s.best())
""",
        uses=("cook", "fr", "blueprint", "doomscroll"),
    ),
]


if __name__ == "__main__":
    sys.exit(main())

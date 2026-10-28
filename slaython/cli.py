"""Command line: `slaython file.slay`, `slaython translate`, `slaython slayify`, ..."""

import argparse
import os
import sys

from . import __version__
from .keywords import keyword_table
from .runner import read_source, run_file
from .transpiler import slayify_with_report, transpile

USAGE = """\
slaython [--no-vibes] [file.slay [args...]]   run a file (no file: start the REPL)
slaython run file.slay [args...]      run a file
slaython -c "code" [args...]          run a snippet
slaython - [args...]                  run code piped in on stdin
slaython translate file.slay [-o out.py]   Slaython -> Python
slaython slayify file.py [-o out.slay]     Python -> Slaython
slaython test [paths...] [-v]         run test_*.slay / *_test.slay tests
slaython glowup [paths] [--check|--diff]   swap leftover Python keywords for slang
slaython learn [lesson] [--list|--reset]   interactive tutorial
slaython lint [paths] [--select/--ignore CODES]   catch mistakes before running
slaython kernel install|remove|list   Jupyter kernel for Slaython notebooks
slaython autoimport on|off|status     let plain python import .slay files
slaython keywords                     print the slang sheet
slaython version

--no-vibes (or SLAYTHON_VIBES=0) turns off the slang error explanations.
"""


def _write(text, out):
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def _convert(argv, to_python):
    name = "translate" if to_python else "slayify"
    p = argparse.ArgumentParser(prog=f"slaython {name}")
    p.add_argument("file")
    p.add_argument("-o", "--output", help="write here instead of stdout")
    args = p.parse_args(argv)
    source = read_source(args.file)
    if to_python:
        _write(transpile(source, args.file), args.output)
        return 0
    result, collisions = slayify_with_report(source, args.file)
    _write(result, args.output)
    for c in collisions:
        sys.stderr.write(
            f"{args.file}:{c.row}:{c.col + 1}: heads up: '{c.name}' is a Slaython keyword, "
            "rename it or it won't mean the same thing\n")
    return 0


def _run_snippet(argv):
    from .importer import install
    from .runner import compile_slay, print_error
    import types
    if not argv:
        sys.stderr.write("slaython -c needs some code\n")
        return 2
    install()
    main = types.ModuleType("__main__")
    sys.modules["__main__"] = main
    sys.argv = ["-c", *argv[1:]]
    sys.path.insert(0, "")
    try:
        exec(compile_slay(argv[0], "<string>"), main.__dict__)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        print_error(exc)
        return 1
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    while argv and argv[0] in ("--no-vibes", "--vibes"):
        os.environ["SLAYTHON_VIBES"] = "0" if argv.pop(0) == "--no-vibes" else "1"
    if not argv:
        from .repl import interact
        interact()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    if cmd in ("version", "--version", "-V"):
        print(f"Slaython {__version__} (Python {sys.version.split()[0]})")
        return 0
    if cmd == "keywords":
        print(keyword_table())
        return 0
    if cmd == "repl":
        from .repl import interact
        interact()
        return 0
    if cmd == "test":
        from .testing import run_tests
        verbose = "-v" in rest or "--verbose" in rest
        return run_tests([a for a in rest if a not in ("-v", "--verbose")], verbose=verbose)
    if cmd == "glowup":
        from .glowup import main as glowup_main
        return glowup_main(rest)
    if cmd == "learn":
        from .learn import main as learn_main
        return learn_main(rest)
    if cmd == "lint":
        from .lint import main as lint_main
        return lint_main(rest)
    if cmd == "kernel":
        from .kernel import main as kernel_main
        return kernel_main(rest)
    if cmd == "autoimport":
        from .autoimport import main as autoimport_main
        return autoimport_main(rest)
    if cmd == "translate":
        return _convert(rest, to_python=True)
    if cmd == "slayify":
        return _convert(rest, to_python=False)
    if cmd == "-c":
        return _run_snippet(rest)
    if cmd == "run":
        if not rest:
            sys.stderr.write("slaython run needs a file\n")
            return 2
        cmd, rest = rest[0], rest[1:]
    return run_file(cmd, rest)


if __name__ == "__main__":
    sys.exit(main())

"""`slaython glowup`: swap plain Python left in .slay files for slang.

    slaython glowup                 # every .slay file under this folder
    slaython glowup src/ app.slay   # specific files or folders
    slaython glowup --check         # list files that need it, change nothing (exit 1 if any)
    slaython glowup --diff          # show the changes, change nothing
"""

import argparse
import difflib
import os
import sys

from .runner import read_source
from .transpiler import slayify_count


def slay_files(paths):
    for path in paths or ["."]:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
            for name in sorted(files):
                if name.endswith(".slay"):
                    yield os.path.join(root, name)


def main(argv):
    p = argparse.ArgumentParser(prog="slaython glowup",
                                description="Swap plain Python keywords in .slay files for slang.")
    p.add_argument("paths", nargs="*")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only report files that need it")
    mode.add_argument("--diff", action="store_true", help="print a diff instead of writing")
    args = p.parse_args(argv)

    files = changed = words = 0
    for path in slay_files(args.paths):
        files += 1
        try:
            source = read_source(path)
            new, count = slayify_count(source, path)
        except (OSError, SyntaxError) as exc:
            sys.stderr.write(f"{path}: skipped, {exc}\n")
            continue
        if not count or new == source:
            continue
        changed += 1
        words += count
        if args.check:
            print(f"{path}: {count} word{'s' * (count != 1)} to glow up")
        elif args.diff:
            sys.stdout.writelines(difflib.unified_diff(
                source.splitlines(keepends=True), new.splitlines(keepends=True), path, path))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print(f"{path}: glowed up {count} word{'s' * (count != 1)}")

    if files == 0:
        print("no .slay files found")
        return 0
    if changed == 0:
        print(f"{files} file{'s' * (files != 1)} checked, already slaying")
        return 0
    if args.check:
        print(f"{changed} of {files} files need a glowup")
        return 1
    if not args.diff:
        print(f"glowed up {words} words in {changed} file{'s' * (changed != 1)}")
    return 0

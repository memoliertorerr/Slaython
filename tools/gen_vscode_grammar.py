"""Generate the VS Code extension in editors/vscode from slaython/keywords.py.

    python tools/gen_vscode_grammar.py          # write the files
    python tools/gen_vscode_grammar.py --check  # fail if they are out of date
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slaython import __version__  # noqa: E402
from slaython.keywords import SLANG  # noqa: E402

OUT = os.path.join(ROOT, "editors", "vscode")

GROUPS = {
    "constant.language.slaython": {"True", "False", "None"},
    "keyword.operator.logical.slaython": {"and", "or", "not", "is", "in"},
    "storage.type.slaython": {"def", "class", "lambda", "async"},
    "support.function.builtin.slaython": {"print", "input", "super"},
}


def scope_for(python):
    for scope, words in GROUPS.items():
        if python in words:
            return scope
    return "keyword.control.slaython"


def words_regex(words):
    words = sorted(words, key=len, reverse=True)
    return r"\b(" + "|".join(w.replace(" ", r"\s+") for w in words) + r")\b"


def grammar():
    by_scope = {}
    for s in SLANG:
        by_scope.setdefault(scope_for(s.python), []).append(s.slang)
    keyword_patterns = [
        {"name": scope, "match": r"(?<!\.)" + words_regex(words)}
        for scope, words in sorted(by_scope.items())
    ]

    def string(name, quote, multiline):
        return {
            "name": name,
            "begin": r"(?i)\b[rbuf]{0,2}" + quote,
            "end": quote if multiline else quote + r"|$",
            "patterns": [{"match": r"\\.", "name": "constant.character.escape.slaython"}],
        }

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "Slaython",
        "scopeName": "source.slaython",
        "fileTypes": ["slay"],
        "patterns": [
            {"name": "comment.line.number-sign.slaython", "match": "#.*$"},
            string("string.quoted.triple.slaython", '"""', True),
            string("string.quoted.triple.slaython", "'''", True),
            string("string.quoted.double.slaython", '"', False),
            string("string.quoted.single.slaython", "'", False),
            {
                "match": r"\b(cook)\s+([A-Za-z_]\w*)",
                "captures": {"1": {"name": "storage.type.function.slaython"},
                             "2": {"name": "entity.name.function.slaython"}},
            },
            {
                "match": r"\b(blueprint)\s+([A-Za-z_]\w*)",
                "captures": {"1": {"name": "storage.type.class.slaython"},
                             "2": {"name": "entity.name.type.class.slaython"}},
            },
            *keyword_patterns,
            {"name": "constant.numeric.slaython",
             "match": r"\b(0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(\.[\d_]*)?([eE][+-]?\d+)?j?)\b"},
            {"name": "variable.language.self.slaython", "match": r"\b(self|cls)\b"},
            {"name": "entity.name.function.decorator.slaython", "match": r"^\s*@[\w.]+"},
        ],
    }


def files():
    package = {
        "name": "slaython",
        "displayName": "Slaython",
        "description": "Syntax highlighting for Slaython (.slay), Python with gen-z slang keywords",
        "version": __version__,
        "engines": {"vscode": "^1.75.0"},
        "categories": ["Programming Languages"],
        "contributes": {
            "languages": [{
                "id": "slaython",
                "aliases": ["Slaython", "slaython"],
                "extensions": [".slay"],
                "configuration": "./language-configuration.json",
            }],
            "grammars": [{
                "language": "slaython",
                "scopeName": "source.slaython",
                "path": "./syntaxes/slaython.tmLanguage.json",
            }],
        },
    }
    config = {
        "comments": {"lineComment": "#"},
        "brackets": [["{", "}"], ["[", "]"], ["(", ")"]],
        "autoClosingPairs": [
            {"open": "{", "close": "}"}, {"open": "[", "close": "]"}, {"open": "(", "close": ")"},
            {"open": "\"", "close": "\"", "notIn": ["string"]},
            {"open": "'", "close": "'", "notIn": ["string", "comment"]},
        ],
        "onEnterRules": [{"beforeText": r"^\s*.*:\s*(#.*)?$", "action": {"indent": "indent"}}],
        "indentationRules": {"increaseIndentPattern": r"^\s*.*:\s*(#.*)?$", "decreaseIndentPattern": r"^\s*(ornah|crashout|periodt)\b.*:"},
    }
    return {
        "package.json": package,
        "language-configuration.json": config,
        os.path.join("syntaxes", "slaython.tmLanguage.json"): grammar(),
    }


def main():
    check = "--check" in sys.argv
    stale = []
    for rel, data in files().items():
        path = os.path.join(OUT, rel)
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if current == text:
            continue
        if check:
            stale.append(rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote", os.path.relpath(path, ROOT))
    if stale:
        print("out of date, run python tools/gen_vscode_grammar.py:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Generate the VS Code extension data in editors/vscode from slaython/keywords.py.

    python tools/gen_vscode_grammar.py          # write the files
    python tools/gen_vscode_grammar.py --check  # fail if they are out of date

Generated: package.json, language-configuration.json, the TextMate grammar,
data/keywords.json (hover data) and snippets/slaython.json. The hand-written
extension.js and lib/ read the generated data, so no word is hardcoded there.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from slaython import __version__  # noqa: E402
from slaython.keywords import (  # noqa: E402
    CONST_WORD, DATACLASS_WORD, ENUM_WORD, INLINE_TEST_WORD, KEPT_PYTHON, MAIN_WORD, PIPE,
    REPEAT_WORD, SLANG, TIMER_WORD,
)

OUT = os.path.join(ROOT, "editors", "vscode")
REPO = "https://github.com/memoliertorerr/Slaython"
LANG = "slaython"
IDENT = r"[A-Za-z_]\w*"

GROUPS = {
    "constant.language.slaython": {"True", "False", "None"},
    "keyword.operator.logical.slaython": {"or", "not", "is"},
    "storage.type.slaython": {"def", "class", "lambda", "async"},
    "variable.language.self.slaython": {"self"},
}
KIND_SCOPES = {
    "builtin": "support.function.builtin.slaython",
    "helper": "support.function.builtin.slaython",
    "syntax": "keyword.control.slaython",
    "operator": "keyword.operator.pipe.slaython",
}


def w(python):
    """The slang for a Python keyword or builtin, e.g. w("def") == "cook"."""
    for s in SLANG:
        if s.python == python and s.kind != "operator":
            return s.slang
    raise KeyError(f"no slang for {python!r} in slaython/keywords.py")


def scope_for(entry):
    for scope, words in GROUPS.items():
        if entry.python in words:
            return scope
    return KIND_SCOPES.get(entry.kind, "keyword.control.slaython")


def words_regex(words):
    words = sorted(words, key=len, reverse=True)
    alts = "|".join(r"\s+".join(re.escape(part) for part in word.split()) for word in words)
    # (?!\s*=(?!=)) skips keyword arguments like reset_index(drop=nocap).
    return r"(?<!\.)\b(" + alts + r")\b(?!\s*=(?!=))"


def ops_regex(ops):
    return "(" + "|".join(re.escape(op) for op in sorted(ops, key=len, reverse=True)) + ")"


def named(keyword_words, keyword_scope, name_scope, name=IDENT):
    """`<keyword> Name` with the name captured, e.g. `cook rate` or `lowkey cook rate`."""
    return {
        "match": r"(?<!\.)\b(" + r"\s+".join(re.escape(x) for x in keyword_words.split())
                 + r")\s+(" + name + ")",
        "captures": {"1": {"name": keyword_scope}, "2": {"name": name_scope}},
    }


def grammar():
    words, ops = {}, {}
    for s in SLANG:
        target = ops if s.kind == "operator" else words
        target.setdefault(scope_for(s), []).append(s.slang)
    keyword_patterns = [{"name": scope, "match": words_regex(ws)} for scope, ws in sorted(words.items())]
    operator_patterns = [{"name": scope, "match": ops_regex(os_)} for scope, os_ in sorted(ops.items())]

    def string(name, quote, multiline):
        return {
            "name": name,
            "begin": r"(?i)(?:\b[rbuf]{1,2})?" + quote,
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
            named(w("def"), "storage.type.function.slaython", "entity.name.function.slaython"),
            named(w("class"), "storage.type.class.slaython", "entity.name.type.class.slaython"),
            named(DATACLASS_WORD, "storage.type.class.slaython", "entity.name.type.class.slaython"),
            named(ENUM_WORD, "storage.type.class.slaython", "entity.name.type.class.slaython"),
            named(CONST_WORD, "keyword.control.slaython", "variable.other.constant.slaython"),
            *keyword_patterns,
            *operator_patterns,
            {"name": "constant.numeric.slaython",
             "match": r"\b(0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(\.[\d_]*)?([eE][+-]?\d+)?j?)\b"},
            {"name": "keyword.operator.logical.slaython",
             "match": r"\b(" + "|".join(KEPT_PYTHON) + r")\b"},
            {"name": "variable.language.self.slaython", "match": r"\b(self|cls)\b"},
            {"name": "entity.name.function.decorator.slaython", "match": r"^\s*@[\w.]+"},
        ],
    }


def keywords_data():
    """Hover data for extension.js: every entry of the slang sheet."""
    return {
        "version": __version__,
        "words": [
            {"slang": s.slang, "python": s.python, "meaning": s.meaning, "why": s.why, "kind": s.kind}
            for s in SLANG
        ],
        "kept": list(KEPT_PYTHON),
    }


def snippets():
    """Snippets for the block constructs, built from the current words."""
    if_, elif_, else_ = w("if"), w("elif"), w("else")
    pass_, self_ = w("pass"), w("self")
    def_, async_, await_ = w("def"), w("async"), w("await")
    try_, except_, finally_, as_ = w("try"), w("except"), w("finally"), w("as")
    exc, print_ = w("Exception"), w("print")
    true, assert_ = w("True"), w("assert")
    block = "\t${%d:" + pass_ + "}"

    def snip(prefix, description, *lines, python=None):
        prefixes = [prefix.replace(" ", "")]
        if python and python not in prefixes:
            prefixes.append(python)
        return prefixes, description, list(lines)

    table = {
        "function": snip(def_, "function (def)",
                         def_ + " ${1:name}(${2}):", block % 3, python="def"),
        "async function": snip(f"{async_} {def_}", "async function (async def)",
                               f"{async_} {def_} ${{1:name}}(${{2}}):",
                               f"\t${{3:{await_} ${{4:thing()}}}}"),
        "class": snip(w("class"), "class with __init__ (class)",
                      w("class") + " ${1:Name}:",
                      f"\t{def_} __init__({self_}${{2:, name}}):",
                      f"\t\t${{3:{self_}.name = name}}", python="class"),
        "dataclass": snip(DATACLASS_WORD, "data-only class (@dataclass class)",
                          DATACLASS_WORD + " ${1:Name}:",
                          "\t${2:name}: ${3:str}",
                          "\t${4:likes}: ${5:int} = ${6:0}"),
        "enum": snip(ENUM_WORD, "fixed set of named values (Enum class)",
                     ENUM_WORD + " ${1:Name}: ${2:A, B, C}"),
        "if": snip(if_, "if", if_ + " ${1:condition}:", block % 2, python="if"),
        "elif": snip(elif_, "elif", elif_ + " ${1:condition}:", block % 2, python="elif"),
        "else": snip(else_, "else", else_ + ":", block % 1, python="else"),
        "if / elif / else": snip(f"{if_}{else_}", "if / elif / else chain",
                                 if_ + " ${1:condition}:", block % 2,
                                 elif_ + " ${3:condition}:", block % 4,
                                 else_ + ":", block % 5),
        "for": snip(w("for"), "for loop", w("for") + " ${1:item} in ${2:items}:", block % 3,
                    python="for"),
        "while": snip(w("while"), "while loop", w("while") + " ${1:condition}:", block % 2,
                      python="while"),
        "repeat": snip(REPEAT_WORD, "repeat a block n times (for _ in range(n))",
                       REPEAT_WORD + " ${1:3}:", block % 2),
        "try": snip(try_, "try / except", try_ + ":", block % 1,
                    f"{except_} ${{2:{exc}}} {as_} ${{3:e}}:", f"\t${{4:{print_}(e)}}",
                    python="try"),
        "try / finally": snip(f"{try_}{finally_}", "try / except / finally",
                              try_ + ":", block % 1,
                              f"{except_} ${{2:{exc}}} {as_} ${{3:e}}:", f"\t${{4:{print_}(e)}}",
                              finally_ + ":", block % 5),
        "except": snip(except_, "except", f"{except_} ${{1:{exc}}} {as_} ${{2:e}}:", block % 3,
                       python="except"),
        "match": snip(w("match"), "match / case",
                      w("match") + " ${1:value}:",
                      "\t" + w("case") + " ${2:pattern}:", "\t" + block % 3,
                      "\t" + w("case") + " _:", "\t" + block % 4, python="match"),
        "case": snip(w("case"), "case", w("case") + " ${1:pattern}:", block % 2, python="case"),
        "with": snip(w("with"), "with (context manager)",
                     w("with") + " ${1:open(${2:path})} " + as_ + " ${3:f}:", block % 4,
                     python="with"),
        "main": snip(MAIN_WORD, 'if __name__ == "__main__"', MAIN_WORD + ":", "\t${1:main()}"),
        "timer": snip(TIMER_WORD, "time a block", TIMER_WORD + ":", block % 1),
        "inline test": snip(INLINE_TEST_WORD, "inline test, run by slaython test",
                            INLINE_TEST_WORD + ' "${1:it works}":', f"\t{assert_} ${{2:{true}}}"),
        "constant": snip(CONST_WORD, "constant that can never be reassigned",
                         CONST_WORD + " ${1:NAME} = ${2:value}"),
        "import from": snip(f"{w('from')} {w('import')}", "from ... import ...",
                            f"{w('from')} ${{1:module}} {w('import')} ${{2:name}}"),
    }
    out = {}
    for name, (prefixes, description, body) in table.items():
        out[f"{prefixes[0]}: {name}"] = {
            "prefix": prefixes if len(prefixes) > 1 else prefixes[0],
            "body": body,
            "description": description,
        }
    return out


def package():
    cmd_when = f"editorLangId == {LANG}"
    return {
        "name": "slaython",
        "displayName": "Slaython",
        "description": "Slaython (.slay) support: Python with gen-z slang keywords. "
                       "Highlighting, hovers, snippets and run commands.",
        "version": __version__,
        "publisher": "memoliertorerr",
        "license": "MIT",
        "repository": {"type": "git", "url": REPO},
        "homepage": REPO + "#readme",
        "bugs": {"url": REPO + "/issues"},
        "engines": {"vscode": "^1.75.0"},
        "categories": ["Programming Languages", "Snippets"],
        "keywords": ["slaython", "slay", "python", "slang", "gen-z", "transpiler", "esolang"],
        "main": "./extension.js",
        "activationEvents": [f"onLanguage:{LANG}"],
        "capabilities": {
            "untrustedWorkspaces": {
                "supported": "limited",
                "description": "slaython.command is only read from user settings in untrusted workspaces.",
                "restrictedConfigurations": ["slaython.command"],
            },
        },
        "contributes": {
            "languages": [{
                "id": LANG,
                "aliases": ["Slaython", "slaython"],
                "extensions": [".slay"],
                "configuration": "./language-configuration.json",
            }],
            "grammars": [{
                "language": LANG,
                "scopeName": "source.slaython",
                "path": "./syntaxes/slaython.tmLanguage.json",
            }],
            "snippets": [{"language": LANG, "path": "./snippets/slaython.json"}],
            "commands": [
                {"command": "slaython.runFile", "title": "Run File", "category": "Slaython",
                 "icon": "$(play)"},
                {"command": "slaython.showPython", "title": "Show Python", "category": "Slaython",
                 "icon": "$(file-code)"},
                {"command": "slaython.runTests", "title": "Run Tests", "category": "Slaython",
                 "icon": "$(beaker)"},
            ],
            "menus": {
                "editor/title": [
                    {"command": "slaython.runFile", "when": cmd_when, "group": "navigation"},
                    {"command": "slaython.showPython", "when": cmd_when, "group": "1_slaython"},
                ],
                "commandPalette": [
                    {"command": "slaython.runFile", "when": cmd_when},
                    {"command": "slaython.showPython", "when": cmd_when},
                ],
            },
            "configuration": {
                "title": "Slaython",
                "properties": {
                    "slaython.command": {
                        "type": "string",
                        "default": "slaython",
                        "scope": "machine-overridable",
                        "markdownDescription":
                            "Command that runs Slaython, for example `slaython` or "
                            "`python -m slaython`. Split on spaces; quote parts that contain spaces.",
                    },
                },
            },
        },
    }


def language_config():
    dedent = sorted({w("else"), w("except"), w("finally"), w("elif").split()[0]})
    outdent = sorted({w("return"), w("break"), w("continue"), w("pass"), w("raise")})
    return {
        "comments": {"lineComment": "#"},
        "brackets": [["{", "}"], ["[", "]"], ["(", ")"]],
        "autoClosingPairs": [
            {"open": "{", "close": "}"}, {"open": "[", "close": "]"}, {"open": "(", "close": ")"},
            {"open": "\"", "close": "\"", "notIn": ["string"]},
            {"open": "'", "close": "'", "notIn": ["string", "comment"]},
        ],
        "surroundingPairs": [["{", "}"], ["[", "]"], ["(", ")"], ["\"", "\""], ["'", "'"]],
        "folding": {"offSide": True,
                    "markers": {"start": r"^\s*#\s*region\b", "end": r"^\s*#\s*endregion\b"}},
        "onEnterRules": [
            {"beforeText": r"^\s*.*:\s*(#.*)?$", "action": {"indent": "indent"}},
            {"beforeText": r"^\s+(" + "|".join(outdent) + r")\b.*$", "action": {"indent": "outdent"}},
        ],
        "indentationRules": {
            "increaseIndentPattern": r"^\s*.*:\s*(#.*)?$",
            "decreaseIndentPattern": r"^\s*(" + "|".join(dedent) + r")\b.*:",
        },
    }


def files():
    return {
        "package.json": package(),
        "language-configuration.json": language_config(),
        os.path.join("syntaxes", "slaython.tmLanguage.json"): grammar(),
        os.path.join("data", "keywords.json"): keywords_data(),
        os.path.join("snippets", "slaython.json"): snippets(),
    }


def main():
    check = "--check" in sys.argv
    stale = []
    outputs = {rel: json.dumps(data, indent=2, ensure_ascii=False) + "\n" for rel, data in files().items()}
    # vsce looks for the license next to package.json, so keep a copy there.
    with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
        outputs["LICENSE"] = f.read()
    for rel, text in outputs.items():
        path = os.path.join(OUT, rel)
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

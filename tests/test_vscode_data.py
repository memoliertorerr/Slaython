import json
import os
import re
import shutil
import subprocess
import sys
import unittest

from slaython.keywords import SLANG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "editors", "vscode")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import gen_vscode_grammar as gen  # noqa: E402


def regexes(pattern):
    for key in ("match", "begin", "end"):
        if key in pattern:
            yield pattern[key]
    for sub in pattern.get("patterns", []):
        yield from regexes(sub)


class VSCodeData(unittest.TestCase):
    def test_grammar_regexes_compile(self):
        for rx in regexes(gen.grammar()):
            re.compile(rx)

    def test_every_word_is_highlighted(self):
        grammar = gen.grammar()
        rules = [re.compile(rx) for rx in regexes(grammar)]
        for s in SLANG:
            line = f"x {s.slang} y"
            self.assertTrue(any(r.search(line) and s.slang.split()[0] in r.search(line).group(0)
                                for r in rules), s.slang)

    def test_hover_data_covers_the_sheet(self):
        data = gen.keywords_data()
        self.assertEqual([w["slang"] for w in data["words"]], [s.slang for s in SLANG])
        for w in data["words"]:
            self.assertTrue(w["python"] and w["why"] and w["kind"])

    def test_snippets_use_known_words(self):
        known = {part for s in SLANG for part in s.slang.split()}
        for name, snip in gen.snippets().items():
            first = re.split(r"[\s:(]", snip["body"][0])[0]
            self.assertIn(first, known, name)

    def test_package_version(self):
        import slaython
        self.assertEqual(gen.package()["version"], slaython.__version__)

    def test_generated_files_up_to_date(self):
        for rel, data in gen.files().items():
            with open(os.path.join(EXT, rel), encoding="utf-8") as f:
                self.assertEqual(json.load(f), data, f"{rel} is stale, run tools/gen_vscode_grammar.py")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_node_lookup_tests(self):
        r = subprocess.run(["node", os.path.join("test", "lookup.test.js")], cwd=EXT,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

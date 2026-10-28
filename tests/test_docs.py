"""The docs site: every example compiles (and runs), the keyword reference is
complete, and the build writes every page with no broken links."""

import base64
import contextlib
import html.parser
import io
import os
import re
import sys
import tempfile
import tokenize
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

from slaython import compile_slay
from slaython.keywords import KEPT_PYTHON, SLANG

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "tools"))

import build_docs  # noqa: E402
import build_playground  # noqa: E402

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^`]*?)\s*$")


def code_blocks():
    """(page, line, lang, flags, code) for every fenced block in docs/*.md."""
    blocks = []
    for path in sorted(DOCS.glob("*.md")):
        lines = path.read_text(encoding="utf-8").split("\n")
        i = 0
        while i < len(lines):
            m = FENCE.match(lines[i])
            if not m:
                i += 1
                continue
            fence, start = m.group(1), i + 1
            indent = len(lines[i]) - len(lines[i].lstrip(" "))
            closing = re.compile(r"^ {0,3}%s{%d,}\s*$" % (re.escape(fence[0]), len(fence)))
            lang, flags = build_docs.parse_fence_info(m.group(2))
            body = []
            i += 1
            while i < len(lines) and not closing.match(lines[i]):
                line = lines[i]
                body.append(line[min(indent, len(line) - len(line.lstrip(" "))):])
                i += 1
            blocks.append((path.name, start, lang, flags, "\n".join(body)))
            i += 1
    return blocks


def slay_blocks(runnable_only=False):
    out = []
    for page, line, lang, flags, code in code_blocks():
        if lang != "slay":
            continue
        if runnable_only and "norun" in flags:
            continue
        out.append((page, line, flags, code))
    return out


@contextlib.contextmanager
def sandbox(stdin_text="bestie\n" * 5):
    """Run example code with fake stdin, captured output and a temp cwd."""
    saved = sys.stdin, sys.stdout, sys.stderr, os.getcwd()
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as tmp:
        sys.stdin, sys.stdout, sys.stderr = io.StringIO(stdin_text), out, err
        os.chdir(tmp)
        try:
            yield out, err
        finally:
            sys.stdin, sys.stdout, sys.stderr = saved[:3]
            os.chdir(saved[3])


class Examples(unittest.TestCase):
    def test_there_are_examples(self):
        self.assertGreater(len(slay_blocks()), 30)

    def test_every_slay_block_compiles(self):
        for page, line, flags, code in slay_blocks():
            with self.subTest(f"docs/{page}:{line}"):
                try:
                    compile_slay(code, f"<docs/{page}:{line}>")
                except SyntaxError as exc:
                    self.fail(f"docs/{page}:{line}: {exc}")

    def test_runnable_blocks_run(self):
        for page, line, flags, code in slay_blocks(runnable_only=True):
            with self.subTest(f"docs/{page}:{line}"):
                ns = {"__name__": "__main__"}
                raised = None
                with sandbox() as (out, err):
                    try:
                        exec(compile_slay(code, f"<docs/{page}:{line}>"), ns)
                    except SystemExit:
                        pass
                    except Exception as exc:  # noqa: BLE001
                        raised = exc
                if "raises" in flags:
                    self.assertIsNotNone(raised, f"docs/{page}:{line} should raise")
                else:
                    self.assertIsNone(raised, f"docs/{page}:{line} raised {raised!r}")

    def test_fences_are_known(self):
        known = {"slay", "slay-fragment", "python", "sh", "text", "toml", "yaml"}
        for page, line, lang, flags, code in code_blocks():
            with self.subTest(f"docs/{page}:{line}"):
                self.assertIn(lang, known)
                self.assertLessEqual(flags, {"norun", "raises"})


class LinkTarget(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links = set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key) is not None:
                self.links.append(attrs[key])


def parse(path):
    p = LinkTarget()
    p.feed(path.read_text(encoding="utf-8"))
    return p


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tmp.name) / "site"
        with contextlib.redirect_stdout(io.StringIO()):
            build_playground.build(cls.site)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_page_is_built(self):
        stems = {p.stem for p in DOCS.glob("*.md")}
        self.assertEqual(stems, {stem for stem, _ in build_docs.NAV})
        for stem in stems:
            page = self.site / "docs" / f"{stem}.html"
            self.assertTrue(page.is_file(), page)
            text = page.read_text(encoding="utf-8")
            for other in stems:   # the nav links to every page
                self.assertIn(f'href="{other}.html"', text)
        self.assertTrue((self.site / "docs" / "docs.css").is_file())
        self.assertTrue((self.site / "index.html").is_file())

    def test_playground_links_to_docs(self):
        self.assertIn('href="docs/"', (self.site / "index.html").read_text(encoding="utf-8"))

    def test_keyword_reference_covers_every_word(self):
        page = (self.site / "docs" / "keywords.html").read_text(encoding="utf-8")
        ids = parse(self.site / "docs" / "keywords.html").ids
        for s in SLANG:
            with self.subTest(s.slang):
                self.assertIn(build_docs.word_id(s.slang), ids)
                self.assertIn(f'<code class="slang">{build_docs.esc(s.slang)}</code>', page)
                self.assertIn(f"<code>{build_docs.esc(s.python)}</code>", page)
                self.assertIn(build_docs.esc(s.meaning), page)
                self.assertIn(build_docs.esc(s.why), page)
        for word in KEPT_PYTHON:
            self.assertIn(build_docs.word_id(word), ids)

    def test_no_broken_internal_links(self):
        pages = sorted((self.site / "docs").glob("*.html"))
        targets = {}
        for page in pages:
            for link in parse(page).links:
                parts = urlsplit(link)
                if parts.scheme or link.startswith("//"):
                    continue
                path = (page.parent / unquote(parts.path)).resolve() if parts.path else page
                if path.is_dir():
                    path = path / "index.html"
                with self.subTest(f"{page.name} -> {link}"):
                    self.assertTrue(path.is_file(), f"{page.name}: broken link {link}")
                    frag = parts.fragment
                    if frag and not frag.startswith("code=") and path.suffix == ".html":
                        if path not in targets:
                            targets[path] = parse(path).ids
                        self.assertIn(frag, targets[path], f"{page.name}: no #{frag} in {path.name}")

    def test_run_links_carry_the_example(self):
        runnable = {code + "\n" for _, _, flags, code in slay_blocks(runnable_only=True)}
        found = set()
        for page in sorted((self.site / "docs").glob("*.html")):
            for link in parse(page).links:
                m = re.fullmatch(r"\.\./#code=([A-Za-z0-9_-]*)", link)
                if m:
                    data = m.group(1)
                    code = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8")
                    found.add(code)
        self.assertEqual(found, runnable)


class Converter(unittest.TestCase):
    def render(self, text):
        return build_docs.Markdown(build_docs.DIRECTIVES, build_docs.rewrite_link).render(text)

    def test_html_is_escaped(self):
        out = self.render('<script>alert("x")</script> and `<b>`  &')
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<code>&lt;b&gt;</code>", out)
        code = self.render("```slay\nyap('<b>')\n```")
        self.assertIn("&lt;b&gt;", code)

    def test_blocks(self):
        out = self.render("# Title\n\n## A `b` c\n\n- one\n- two\n  - nested\n\n1. x\n2. y\n\n"
                          "> quote **bold** *it*\n\n| a | b |\n|---|---|\n| `x \\| y` | [l](guide.md#z) |\n")
        self.assertIn('<h2 id="a-b-c">A <code>b</code> c', out)
        self.assertIn("<li>one</li>", out)
        self.assertIn("<ul>\n<li>nested</li>\n</ul>", out)
        self.assertIn("<ol>", out)
        self.assertIn("<blockquote>\n<p>quote <strong>bold</strong> <em>it</em></p>", out)
        self.assertIn("<code>x | y</code>", out)
        self.assertIn('<a href="guide.html#z">l</a>', out)

    def test_playground_link_matches_share_encoding(self):
        # app.js: base64url of the UTF-8 text, '=' padding removed
        link = build_docs.playground_link('yap("é")\n')
        self.assertTrue(link.startswith("../#code="))
        self.assertNotIn("=", link[len("../#code="):])
        data = link[len("../#code="):]
        self.assertEqual(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(), 'yap("é")\n')

    def test_highlight_matches_playground_rules(self):
        out = build_docs.highlight("fr x.drop(drop=nocap):\n    y = spill\n")
        self.assertIn('<span class="t-slang">fr</span>', out)
        self.assertIn('<span class="t-const">nocap</span>', out)
        self.assertNotIn('<span class="t-slang">drop</span>', out)
        self.assertNotIn('<span class="t-slang">spill</span>', out)


if __name__ == "__main__":
    unittest.main()

"""Build the documentation site from docs/*.md.

    python tools/build_docs.py              # writes _site/docs/
    python tools/build_docs.py --out DIR    # writes DIR/docs/

tools/build_playground.py calls build() too, so one command builds the
playground and the docs:

    python tools/build_playground.py && python -m http.server -d _site

Pages are Markdown. The small converter below handles what the docs use:
headings (with anchors), paragraphs, lists, tables, block quotes, code
fences, links, inline code, bold and italic. Fences:

    ```slay            Slaython; compiled by tests/test_docs.py, gets a
                       "Run in playground" link and runs in the tests
    ```slay norun      compiled, but no link and not run (needs files, a
                       network or a package the playground doesn't have)
    ```slay raises     like slay, but the tests expect it to raise an error
    ```slay-fragment   highlighted only (partial code, or code that fails)
    ```python          highlighted as plain Python
    ```sh / ```text    shown as is

A line `::: keyword-reference` inserts the keyword tables, generated from
slaython/keywords.py.
"""

import argparse
import base64
import hashlib
import html
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slaython import __version__  # noqa: E402
from slaython.keywords import KEPT_PYTHON, SLANG  # noqa: E402

DOCS_DIR = ROOT / "docs"
PLAYGROUND_CSS = ROOT / "playground" / "style.css"
DEFAULT_REPO = "https://github.com/memoliertorerr/Slaython"
SITE_NAME = "Slaython docs"

# Page order in the sidebar: (file stem, label). Every docs/*.md must be here.
NAV = [
    ("index", "Overview"),
    ("getting-started", "Getting started"),
    ("guide", "Language guide"),
    ("keywords", "Keyword reference"),
    ("python", "Working with Python"),
    ("tools", "Tools"),
    ("faq", "FAQ and limits"),
]


def esc(text):
    return html.escape(text, quote=True)


def playground_link(code):
    """Relative link that opens the playground with `code` in the editor.

    Same encoding as the playground's Share button (playground/app.js):
    #code= plus base64url of the UTF-8 text, without padding.
    """
    data = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii").rstrip("=")
    return f"../#code={data}"


def parse_fence_info(info):
    """'slay norun' -> ('slay', {'norun'})."""
    parts = info.split()
    return (parts[0].lower() if parts else ""), set(parts[1:])


# ---------------------------------------------------------------------------
# Highlighting: a port of highlight() in playground/app.js, so code looks the
# same on both pages.

_PY_KEYWORDS = set(
    "False None True and as assert async await break class continue def del elif else except "
    "finally for from global if import in is lambda nonlocal not or pass raise return try while "
    "with yield match case".split())
_CONSTS = {"True", "False", "None"}
_IDENT = re.compile(r"^[^\W\d]\w*$")


def _slang_classes():
    words = {}
    for s in SLANG:
        if s.kind == "operator":
            continue
        cls = ("t-builtin" if s.kind in ("builtin", "helper")
               else "t-const" if s.python in _CONSTS else "t-slang")
        soft = s.kind == "soft" or s.slang == "runitfoo"
        for w in s.slang.split():
            if _IDENT.match(w) and w not in words:
                words[w] = (cls, soft)
    return words


_SLANG_CLASSES = _slang_classes()

_TOKEN = re.compile(
    r"(#[^\n]*)"                                                         # 1 comment
    r"|((?:[rRbBuUfF]{1,2})?(?:'''[\s\S]*?(?:'''|$)|\"\"\"[\s\S]*?(?:\"\"\"|$)"
    r"|'(?:\\.|[^'\\\n])*'?|\"(?:\\.|[^\"\\\n])*\"?))"                     # 2 string
    r"|([^\W\d]\w*)"                                                     # 3 name
    r"|(\d[\d_]*(?:\.[\d_]*)?(?:[eE][+-]?\d+)?[jJ]?|\.\d[\d_]*)"         # 4 number
    r"|(\|>)"                                                            # 5 pipe
    r"|([(\[{])|([)\]}])"                                                # 6 open, 7 close
    r"|(\n)"                                                             # 8 newline
    r"|([^\S\n]+)"                                                       # 9 spaces
    r"|([\s\S])")                                                        # 10 anything else


def highlight(src, slang_mode=True):
    """Highlighted HTML for Slaython (or, with slang_mode=False, Python) code."""
    out = []
    depth = 0
    line_start = True
    prev = ""
    for m in _TOKEN.finditer(src):
        t = m.group(0)
        if m.group(9) is not None:
            out.append(t)
            continue
        if m.group(8) is not None:
            out.append(t)
            if depth == 0:
                line_start = True
            continue
        at_start = line_start
        line_start = False
        cls = ""
        if m.group(1) is not None:
            cls = "t-com"
            line_start = at_start
        elif m.group(2) is not None:
            cls = "t-str"
        elif m.group(4) is not None:
            cls = "t-num"
        elif m.group(5) is not None:
            cls = "t-op" if slang_mode else ""
        elif m.group(6) is not None:
            depth += 1
        elif m.group(7) is not None:
            depth = max(0, depth - 1)
        elif m.group(3) is not None:
            cls = _name_class(src, m, prev, at_start, depth, slang_mode)
        if m.group(1) is None:
            prev = t
        out.append(f'<span class="{cls}">{esc(t)}</span>' if cls else esc(t))
    return "".join(out)


def _name_class(src, m, prev, at_start, depth, slang_mode):
    word = m.group(0)
    if prev == ".":
        return ""
    if slang_mode and word in _SLANG_CLASSES:
        cls, soft = _SLANG_CLASSES[word]
        if soft and not at_start:
            return ""
        if depth > 0 and re.match(r"[^\S\n]*=(?!=)", src[m.end():]):
            return ""   # keyword argument: f(drop=nocap)
        return cls
    if word in _PY_KEYWORDS:
        return "t-const" if word in _CONSTS else "t-pykw"
    return ""


def highlight_shell(src):
    out = []
    for line in src.split("\n"):
        m = re.match(r"^(.*?)((?:^|\s)#.*)?$", line)
        body, comment = m.group(1), m.group(2) or ""
        out.append(esc(body) + (f'<span class="t-com">{esc(comment)}</span>' if comment else ""))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Markdown

_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*([^`]*?)\s*$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
_HEADING_ID = re.compile(r"\s*\{#([\w-]+)\}$")
_HR = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_QUOTE = re.compile(r"^ {0,3}> ?(.*)$")
_LIST = re.compile(r"^( *)([-*+]|\d{1,9}[.)])( +|$)(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
_DIRECTIVE = re.compile(r"^:::\s*([\w-]+)\s*$")
_TAG = re.compile(r"<[^>]+>")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def plain_text(fragment):
    """Text of an HTML fragment, without tags."""
    return html.unescape(_TAG.sub("", fragment))


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-") or "section"


class Markdown:
    """Markdown to HTML for one page."""

    def __init__(self, directives=None, link=None):
        self.directives = directives or {}
        self.link = link or (lambda url: url)
        self.ids = set()
        self.headings = []       # (level, id, html)
        self.code_blocks = []    # (lang, flags, code)

    # --- blocks ---

    def render(self, text):
        lines = text.replace("\r\n", "\n").replace("\t", "    ").split("\n")
        return self.blocks(lines)

    def starts_block(self, line):
        return bool(_FENCE.match(line) or _HEADING.match(line) or _QUOTE.match(line)
                    or _HR.match(line) or _LIST.match(line) or _DIRECTIVE.match(line))

    def blocks(self, lines, tight=False):
        out = []
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            m = _FENCE.match(line)
            if m:
                i = self.fence(lines, i, m, out)
                continue
            m = _HEADING.match(line)
            if m:
                out.append(self.heading(len(m.group(1)), m.group(2)))
                i += 1
                continue
            m = _DIRECTIVE.match(line)
            if m:
                name = m.group(1)
                if name not in self.directives:
                    raise ValueError(f"unknown directive ::: {name}")
                out.append(self.directives[name](self))
                i += 1
                continue
            if _HR.match(line):
                out.append("<hr>")
                i += 1
                continue
            if _QUOTE.match(line):
                body = []
                while i < n and _QUOTE.match(lines[i]):
                    body.append(_QUOTE.match(lines[i]).group(1))
                    i += 1
                out.append(f"<blockquote>\n{self.blocks(body)}\n</blockquote>")
                continue
            if "|" in line and i + 1 < n and "-" in lines[i + 1] and _TABLE_SEP.match(lines[i + 1]):
                i = self.table(lines, i, out)
                continue
            if _LIST.match(line) and _LIST.match(line).group(4).strip():
                i = self.list(lines, i, out)
                continue
            para = [line.strip()]
            i += 1
            while i < n and lines[i].strip() and not self.starts_block(lines[i]):
                para.append(lines[i].strip())
                i += 1
            body = self.inline("\n".join(para))
            out.append(body if tight else f"<p>{body}</p>")
        return "\n".join(out)

    def fence(self, lines, i, m, out):
        indent, fence, info = len(m.group(1)), m.group(2), m.group(3)
        closing = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$")
        body = []
        i += 1
        while i < len(lines) and not closing.match(lines[i]):
            line = lines[i]
            body.append(line[min(indent, _indent(line)):])
            i += 1
        lang, flags = parse_fence_info(info)
        code = "\n".join(body)
        self.code_blocks.append((lang, flags, code))
        out.append(self.code_block(lang, flags, code))
        return i + 1

    def code_block(self, lang, flags, code):
        if lang.startswith("slay"):
            body = highlight(code, True)
        elif lang in ("python", "py"):
            body = highlight(code, False)
        elif lang in ("sh", "shell", "bash", "console", "toml"):
            body = highlight_shell(code)
        else:
            body = esc(code)
        cls = f' class="language-{esc(lang)}"' if lang else ""
        pre = f"<pre><code{cls}>{body}</code></pre>"
        if lang == "slay" and "norun" not in flags:
            link = esc(playground_link(code + "\n"))
            return (f'<div class="codeblock runnable"><div class="code-bar"><span class="lang">slaython</span>'
                    f'<a class="run" href="{link}">Run in playground</a></div>{pre}</div>')
        return f'<div class="codeblock">{pre}</div>'

    def heading(self, level, text):
        m = _HEADING_ID.search(text)
        wanted = None
        if m:
            wanted, text = m.group(1), text[:m.start()]
        body = self.inline(text)
        hid = self.unique_id(wanted or slugify(plain_text(body)))
        self.headings.append((level, hid, body))
        if level == 1:
            return f'<h1 id="{hid}">{body}</h1>'
        return (f'<h{level} id="{hid}">{body}'
                f'<a class="anchor" href="#{hid}" aria-label="Link to this section">#</a></h{level}>')

    def unique_id(self, base):
        hid, k = base, 2
        while hid in self.ids:
            hid = f"{base}-{k}"
            k += 1
        self.ids.add(hid)
        return hid

    def table(self, lines, i, out):
        def cells(row):
            row = row.strip()
            if row.startswith("|"):
                row = row[1:]
            if row.endswith("|") and not row.endswith("\\|"):
                row = row[:-1]
            return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]

        head = cells(lines[i])
        aligns = []
        for spec in cells(lines[i + 1]):
            left, right = spec.startswith(":"), spec.endswith(":")
            aligns.append("center" if left and right else "right" if right else "left" if left else "")
        i += 2
        rows = []
        while i < len(lines) and lines[i].strip() and "|" in lines[i]:
            rows.append(cells(lines[i]))
            i += 1
        labels = [plain_text(self.inline(h)) for h in head]

        def style(k):
            a = aligns[k] if k < len(aligns) else ""
            return f' style="text-align:{a}"' if a else ""

        parts = ['<div class="table-wrap"><table class="stack">', "<thead><tr>"]
        parts += [f'<th scope="col"{style(k)}>{self.inline(h)}</th>' for k, h in enumerate(head)]
        parts.append("</tr></thead><tbody>")
        for row in rows:
            row = (row + [""] * len(head))[:len(head)]
            parts.append("<tr>" + "".join(
                f'<td data-label="{esc(labels[k])}"{style(k)}>{self.inline(c)}</td>'
                for k, c in enumerate(row)) + "</tr>")
        parts.append("</tbody></table></div>")
        out.append("".join(parts))
        return i

    def list(self, lines, i, out):
        first = _LIST.match(lines[i])
        base = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        start = int(first.group(2)[:-1]) if ordered else 1
        items, loose, n = [], False, len(lines)

        def same_list(m):
            return m and len(m.group(1)) == base and m.group(2)[0].isdigit() == ordered

        while i < n:
            m = _LIST.match(lines[i])
            if not same_list(m):
                break
            content = base + len(m.group(2)) + max(1, len(m.group(3)))
            item = [m.group(4)]
            i += 1
            while i < n:
                line = lines[i]
                if not line.strip():
                    j = i
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and _indent(lines[j]) >= content:
                        item.extend([""] * (j - i))
                        i = j
                        loose = True
                        continue
                    break
                if _indent(line) >= content:
                    item.append(line[content:])
                    i += 1
                    continue
                if self.starts_block(line) or not item[-1].strip():
                    break
                item.append(line.strip())   # lazy continuation of the paragraph
                i += 1
            items.append(item)
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j > i:
                if j < n and same_list(_LIST.match(lines[j])):
                    loose = True
                    i = j
                    continue
                break
        tag = "ol" if ordered else "ul"
        attr = f' start="{start}"' if ordered and start != 1 else ""
        body = "\n".join(f"<li>{self.blocks(item, tight=not loose)}</li>" for item in items)
        out.append(f"<{tag}{attr}>\n{body}\n</{tag}>")
        return i

    # --- inline ---

    def inline(self, text):
        stash = []

        def keep(fragment):
            stash.append(fragment)
            return f"\x00{len(stash) - 1}\x00"

        def code(m):
            s = m.group(2)
            if len(s) >= 2 and s[0] == s[-1] == " " and s.strip():
                s = s[1:-1]
            return keep(f"<code>{esc(s)}</code>")

        text = re.sub(r"(`+)(.+?)(?<!`)\1(?!`)", code, text, flags=re.S)
        text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>~])", lambda m: keep(esc(m.group(1))), text)
        text = esc(text)

        def link(m):
            label, url = m.group(1), html.unescape(m.group(2))
            return keep(f'<a href="{esc(self.link(url))}">{self.emphasis(label)}</a>')

        text = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", link, text)
        text = re.sub(r"&lt;(https?://[^\s<>&]+)&gt;",
                      lambda m: keep(f'<a href="{m.group(1)}">{m.group(1)}</a>'), text)
        text = self.emphasis(text)
        while "\x00" in text:
            text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
        return text

    @staticmethod
    def emphasis(text):
        text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.S)
        text = re.sub(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])", r"<em>\1</em>", text, flags=re.S)
        text = re.sub(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])", r"<em>\1</em>", text, flags=re.S)
        return text


def rewrite_link(url):
    """docs-relative `page.md#x` links become `page.html#x`."""
    if re.match(r"^[a-z][a-z0-9+.-]*:|^/|^#", url, re.I):
        return url
    path, sep, frag = url.partition("#")
    if path.endswith(".md"):
        path = path[:-3] + ".html"
    return path + sep + frag


# ---------------------------------------------------------------------------
# The keyword reference, generated from slaython/keywords.py

KIND_GROUPS = [
    ("keywords", "Keywords", ("keyword", "compound"),
     "Each one stands for a Python keyword. They work anywhere the Python keyword would."),
    ("soft-keywords", "Soft keywords", ("soft",),
     "Keywords only at the start of a line that ends in `:`. Anywhere else they are normal names, "
     "so `spill = 3` still works."),
    ("builtins", "Builtins", ("builtin",),
     "Other names for Python builtins. `yap` is `print`, so `yap(\"hi\", end=\"\")` works."),
    ("helpers", "Helpers", ("helper",),
     "Small functions that come with Slaython. They only count when you call them or use them as "
     "a decorator, so a variable with the same name stays a variable."),
    ("new-syntax", "New syntax", ("syntax",),
     "Things Python doesn't have. See [Slaython-only syntax](guide.md#slaython-only-syntax) "
     "in the language guide."),
    ("operators", "Operators", ("operator",),
     "New operators. See [pipes](guide.md#pipes)."),
]


def word_id(word):
    return "word-" + ({"|>": "pipe"}.get(word) or slugify(word))


def keyword_reference(md):
    """HTML for `::: keyword-reference`: every word in SLANG, grouped by kind."""
    known = {k for group in KIND_GROUPS for k in group[2]}
    groups = list(KIND_GROUPS)
    others = [s for s in SLANG if s.kind not in known]
    if others:
        groups.append(("other", "Other", tuple(sorted({s.kind for s in others})), ""))
    parts = []
    for gid, title, kinds, intro in groups:
        words = [s for s in SLANG if s.kind in kinds]
        if not words:
            continue
        parts.append(md.heading(2, f"{title} {{#{gid}}}"))
        if intro:
            parts.append(f"<p>{md.inline(intro)}</p>")
        parts.append('<div class="table-wrap"><table class="stack words"><thead><tr>'
                     '<th scope="col">Slaython</th><th scope="col">Python</th>'
                     '<th scope="col">Meaning</th><th scope="col">Why</th></tr></thead><tbody>')
        for s in words:
            wid = md.unique_id(word_id(s.slang))
            parts.append(
                f'<tr id="{wid}"><td data-label="Slaython"><code class="slang">{esc(s.slang)}</code></td>'
                f'<td data-label="Python"><code>{esc(s.python)}</code></td>'
                f'<td data-label="Meaning">{esc(s.meaning)}</td>'
                f'<td data-label="Why">{esc(s.why)}</td></tr>')
        parts.append("</tbody></table></div>")
    if KEPT_PYTHON:
        parts.append(md.heading(2, "Plain Python {#plain-python}"))
        parts.append("<p>These Python keywords have no slang. Write them as in Python.</p>")
        parts.append('<div class="table-wrap"><table class="stack words"><thead><tr>'
                     '<th scope="col">Slaython</th><th scope="col">Python</th></tr></thead><tbody>')
        for w in KEPT_PYTHON:
            wid = md.unique_id(word_id(w))
            parts.append(f'<tr id="{wid}"><td data-label="Slaython"><code class="slang">{esc(w)}</code></td>'
                         f'<td data-label="Python"><code>{esc(w)}</code></td></tr>')
        parts.append("</tbody></table></div>")
    return "\n".join(parts)


DIRECTIVES = {"keyword-reference": keyword_reference}


# ---------------------------------------------------------------------------
# Pages

FONTS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;"
         "12..96,800&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600"
         "&display=swap")


def _repo_url():
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return DEFAULT_REPO
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}"


def page_files():
    """{stem: path} for every docs/*.md, checked against NAV."""
    found = {p.stem: p for p in sorted(DOCS_DIR.glob("*.md"))}
    listed = [stem for stem, _ in NAV]
    missing = [s for s in listed if s not in found]
    extra = [s for s in found if s not in listed]
    if missing:
        sys.exit(f"build_docs: NAV lists docs/{missing[0]}.md, which doesn't exist")
    if extra:
        sys.exit(f"build_docs: docs/{extra[0]}.md is not in NAV in tools/build_docs.py; add it there")
    return found


def render_page(stem, source):
    """(title, body html, Markdown object) for one page."""
    md = Markdown(DIRECTIVES, rewrite_link)
    body = md.render(source)
    titles = [h for h in md.headings if h[0] == 1]
    title = plain_text(titles[0][2]) if titles else dict(NAV)[stem]
    return title, body, md


def _description(body):
    m = re.search(r"<p>(.*?)</p>", body, re.S)
    text = " ".join(plain_text(m.group(1)).split()) if m else ""
    return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + "..."


def _nav_html(current, headings):
    items = []
    for stem, label in NAV:
        here = stem == current
        attr = ' aria-current="page"' if here else ""
        toc = ""
        if here:
            subs = [(hid, h) for level, hid, h in headings if level == 2]
            if subs:
                toc = '<ul class="toc">' + "".join(
                    f'<li><a href="#{hid}">{esc(plain_text(h))}</a></li>' for hid, h in subs) + "</ul>"
        items.append(f'<li><a href="{stem}.html"{attr}>{esc(label)}</a>{toc}</li>')
    return "\n".join(items)


def _pager(current):
    stems = [s for s, _ in NAV]
    labels = dict(NAV)
    k = stems.index(current)
    parts = []
    if k > 0:
        s = stems[k - 1]
        parts.append(f'<a class="prev" href="{s}.html"><span>Previous</span>{esc(labels[s])}</a>')
    if k + 1 < len(stems):
        s = stems[k + 1]
        parts.append(f'<a class="next" href="{s}.html"><span>Next</span>{esc(labels[s])}</a>')
    return f'<nav class="pager" aria-label="Pages">{"".join(parts)}</nav>'


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{fonts}">
<link rel="stylesheet" href="../style.css?v={build}">
<link rel="stylesheet" href="docs.css?v={build}">
</head>
<body class="docs-site">
<a class="skip" href="#content">Skip to content</a>
<header class="top">
  <div class="brand">
    <p class="brand-name"><a href="index.html"><span class="word">Slaython</span> <span class="tag">docs</span></a></p>
  </div>
  <nav class="links" aria-label="Site">
    <a href="../">Playground</a>
    <a href="{repo}">Source</a>
    <span class="chip">v{version}</span>
  </nav>
</header>
<div class="docs">
  <nav class="side" aria-label="Docs pages">
    <ul>
{nav}
    </ul>
  </nav>
  <main id="content" class="prose">
{body}
{pager}
    <p class="edit"><a href="{edit}">Edit this page</a></p>
  </main>
</div>
<footer class="foot">
  <p>Slaython is Python with gen-z slang keywords. <a href="../">Try it in the playground</a>, or install it with <code>pip install slaython</code>.</p>
</footer>
</body>
</html>
"""


def build(out, build_id=None):
    """Write <out>/docs/*.html (plus docs.css and other assets). Returns the page paths."""
    out = Path(out).resolve()
    docs_out = out / "docs"
    if docs_out == DOCS_DIR or out == ROOT or ROOT.is_relative_to(out) or DOCS_DIR.is_relative_to(docs_out):
        sys.exit(f"build_docs: refusing to build into {out}")
    pages = page_files()
    assets = [p for p in sorted(DOCS_DIR.rglob("*"))
              if p.is_file() and p.suffix != ".md" and not p.name.startswith(".")]
    if build_id is None:
        digest = hashlib.sha256()
        for path in [*pages.values(), *assets, PLAYGROUND_CSS]:
            digest.update(path.read_bytes())
        build_id = digest.hexdigest()[:12]

    if docs_out.exists():
        shutil.rmtree(docs_out)
    docs_out.mkdir(parents=True)
    for path in assets:
        dest = docs_out / path.relative_to(DOCS_DIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    repo = _repo_url()
    written = []
    for stem, _ in NAV:
        title, body, md = render_page(stem, pages[stem].read_text(encoding="utf-8"))
        full_title = SITE_NAME if stem == "index" else f"{title} - {SITE_NAME}"
        page = PAGE.format(
            title=esc(full_title), description=esc(_description(body)), fonts=esc(FONTS),
            build=build_id, repo=esc(repo), version=esc(__version__),
            nav=_nav_html(stem, md.headings), body=body, pager=_pager(stem),
            edit=esc(f"{repo}/edit/main/docs/{stem}.md"))
        dest = docs_out / f"{stem}.html"
        dest.write_text(page, encoding="utf-8")
        written.append(dest)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Slaython docs site.")
    parser.add_argument("--out", default=str(ROOT / "_site"),
                        help="site folder; pages go in its docs/ folder (default: _site)")
    args = parser.parse_args(argv)
    written = build(args.out)
    print(f"built {len(written)} docs pages in {Path(args.out).resolve() / 'docs'}")


if __name__ == "__main__":
    main()

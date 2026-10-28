"""Build the browser playground into a static site.

    python tools/build_playground.py              # writes _site/
    python tools/build_playground.py --out DIR    # writes DIR/
    python -m http.server -d _site                # preview it

The site holds the page from playground/, every slaython/*.py file,
examples/*.slay and a manifest.json that the page reads at start-up.
It also builds the docs (docs/*.md) into docs/, see tools/build_docs.py.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_docs  # noqa: E402

from slaython import __version__  # noqa: E402
from slaython.keywords import KEPT_PYTHON, SLANG  # noqa: E402

PAGE_DIR = ROOT / "playground"
PACKAGE_DIR = ROOT / "slaython"
EXAMPLES_DIR = ROOT / "examples"
BUILD_MARK = "__BUILD__"   # replaced in .html files, for cache busting
FIRST_EXAMPLE = "hello"


def _skip(path):
    return "__pycache__" in path.parts or path.name.startswith(".")


def package_files():
    """Every .py file in the slaython package, found at build time."""
    return sorted(p for p in PACKAGE_DIR.rglob("*.py") if not _skip(p.relative_to(ROOT)))


def example_files():
    files = sorted(EXAMPLES_DIR.glob("*.slay"))
    return sorted(files, key=lambda p: p.stem != FIRST_EXAMPLE)  # stable: hello first


def _about(path):
    """The example's first comment line, used as a hint in the picker."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            break
    return ""


def _repo_url():
    # Set by GitHub Actions; lets the page link back to the source.
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}"


def _prepare(out):
    """Empty the output folder, refusing to wipe anything that isn't a build."""
    if out.exists():
        if not out.is_dir():
            sys.exit(f"build_playground: {out} is not a folder")
        if any(out.iterdir()) and not (out / "manifest.json").exists():
            sys.exit(f"build_playground: {out} is not empty and not a previous build; "
                     "pick another --out")
        shutil.rmtree(out)
    out.mkdir(parents=True)


def _copy(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def build(out):
    out = Path(out).resolve()
    if out == ROOT or ROOT.is_relative_to(out) or out in (PAGE_DIR, PACKAGE_DIR, EXAMPLES_DIR):
        sys.exit(f"build_playground: refusing to build into {out}")
    _prepare(out)

    page = [p for p in sorted(PAGE_DIR.rglob("*")) if p.is_file() and not _skip(p.relative_to(PAGE_DIR))]
    package = package_files()
    examples = example_files()
    if not (PACKAGE_DIR / "__init__.py").exists():
        sys.exit("build_playground: slaython/__init__.py is missing")

    digest = hashlib.sha256()
    for path in page + package + examples:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    build_id = digest.hexdigest()[:12]

    for path in page:
        dest = out / path.relative_to(PAGE_DIR)
        if path.suffix == ".html":
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(path.read_text(encoding="utf-8").replace(BUILD_MARK, build_id),
                            encoding="utf-8")
        else:
            _copy(path, dest)
    for path in package + examples:
        _copy(path, out / path.relative_to(ROOT))

    manifest = {
        "version": __version__,
        "build": build_id,
        "repo": _repo_url(),
        "package": [p.relative_to(ROOT).as_posix() for p in package],
        "examples": [
            {"name": p.stem, "file": p.relative_to(ROOT).as_posix(), "about": _about(p)}
            for p in examples
        ],
        "keywords": [
            {"slang": s.slang, "python": s.python, "why": s.why, "kind": s.kind} for s in SLANG
        ],
        "kept_python": list(KEPT_PYTHON),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    manifest["docs"] = len(build_docs.build(out))
    return out, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Slaython web playground.")
    parser.add_argument("--out", default=str(ROOT / "_site"),
                        help="output folder (default: _site in the repo root)")
    args = parser.parse_args(argv)
    out, manifest = build(args.out)
    print(f"built playground in {out}: {len(manifest['package'])} package files, "
          f"{len(manifest['examples'])} examples, {len(manifest['keywords'])} words, "
          f"{manifest['docs']} docs pages")


if __name__ == "__main__":
    main()

"""Let Python import .slay files like normal modules.

After ``install()`` (which ``import slaython`` does for you), ``import foo``
finds ``foo.slay`` (or a package with ``__init__.slay``) anywhere on
sys.path, using the same search order Python uses for .py files.
"""

import importlib
import importlib.machinery
import sys

from .compiler import compile_source

SUFFIX = ".slay"


class SlayLoader(importlib.machinery.SourceFileLoader):
    """Loads a .slay file by translating it to Python first."""

    def get_code(self, fullname):
        path = self.get_filename(fullname)
        source = self.get_source(fullname)
        # No .pyc caching: a cached foo.slay would share its cache file with foo.py.
        return compile_source(source, path, "exec")


def _supported_loaders():
    try:
        from importlib._bootstrap_external import _get_supported_file_loaders
        return list(_get_supported_file_loaders())
    except ImportError:  # pragma: no cover - very old or unusual Pythons
        m = importlib.machinery
        return [
            (m.ExtensionFileLoader, m.EXTENSION_SUFFIXES),
            (m.SourceFileLoader, m.SOURCE_SUFFIXES),
            (m.SourcelessFileLoader, m.BYTECODE_SUFFIXES),
        ]


def _is_file_finder_hook(hook):
    return "FileFinder" in getattr(hook, "__qualname__", "")


_original_hook = None


def install():
    """Teach the import system about .slay files. Safe to call twice."""
    global _original_hook
    if any(getattr(h, "_slaython", False) for h in sys.path_hooks):
        return
    loaders = _supported_loaders() + [(SlayLoader, [SUFFIX])]
    hook = importlib.machinery.FileFinder.path_hook(*loaders)
    hook._slaython = True
    for i, existing in enumerate(sys.path_hooks):
        if _is_file_finder_hook(existing):
            _original_hook = existing
            sys.path_hooks[i] = hook
            break
    else:
        sys.path_hooks.append(hook)
    sys.path_importer_cache.clear()
    importlib.invalidate_caches()


def uninstall():
    """Undo install()."""
    global _original_hook
    for i, existing in enumerate(sys.path_hooks):
        if getattr(existing, "_slaython", False):
            if _original_hook is not None:
                sys.path_hooks[i] = _original_hook
            else:
                del sys.path_hooks[i]
            break
    _original_hook = None
    sys.path_importer_cache.clear()
    importlib.invalidate_caches()

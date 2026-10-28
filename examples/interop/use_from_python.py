"""Plain Python importing a Slaython package.

Run from the repo root:  python examples/interop/use_from_python.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # find slaython
import slaython  # noqa: E402,F401  (lets Python import .slay files)

from squadpkg import VERSION, rank  # noqa: E402  (squadpkg/__init__.slay)
from squadpkg.ranking import to_json  # noqa: E402

scores = {"mia": [9, 10], "jay": [6, 7], "kai": [8, 9]}
print("squadpkg", VERSION, "ranking:", rank(scores))
print(to_json(scores))

# Slaython snippets inline, too
slaython.slay('yap("python said hi, slaython said", "W" fr rank(scores)[0] == "mia" ornah "L")')
print(slaython.slay_eval("[x * 2 doomscroll x in range(3)]"))

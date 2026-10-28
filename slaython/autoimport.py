"""Let plain `python` import .slay files without `import slaython` first.

`slaython autoimport on` writes a small .pth file into site-packages. Python
reads .pth files at startup, and this one imports slaython, which turns on
.slay imports. `slaython autoimport off` removes it again.
"""

import os
import site
import sys
import sysconfig

PTH_NAME = "slaython-autoimport.pth"
# One line, starting with "import" so site.py runs it. It never fails, so a
# removed slaython can't break Python startup.
PTH_LINE = ('import sys; exec("try:\\n import slaython\\nexcept Exception:\\n pass")\n')


def default_dir(user=False):
    if user:
        return site.getusersitepackages()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [sysconfig.get_paths()["purelib"], *getattr(site, "getsitepackages", lambda: [])()]
    if here in candidates:
        return here
    return candidates[0]


def pth_path(directory=None, user=False):
    return os.path.join(directory or default_dir(user), PTH_NAME)


def enable(directory=None, user=False):
    path = pth_path(directory, user)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(PTH_LINE)
    return path


def disable(directory=None, user=False):
    path = pth_path(directory, user)
    if os.path.exists(path):
        os.remove(path)
        return path
    return None


def status(directory=None, user=False):
    path = pth_path(directory, user)
    return path, os.path.exists(path)


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="slaython autoimport",
                                description="Let plain python import .slay files.")
    p.add_argument("action", choices=["on", "off", "status"])
    p.add_argument("--user", action="store_true", help="use your user site-packages")
    p.add_argument("--dir", help="write the .pth file into this folder instead")
    args = p.parse_args(argv)
    if args.action == "on":
        try:
            path = enable(args.dir, args.user)
        except PermissionError:
            sys.stderr.write("no permission to write there. try: slaython autoimport on --user\n")
            return 1
        print(f"on: python can now import .slay files ({path})")
    elif args.action == "off":
        path = disable(args.dir, args.user)
        print(f"off: removed {path}" if path else "already off")
    else:
        path, exists = status(args.dir, args.user)
        print(f"{'on' if exists else 'off'} ({path})")
    return 0

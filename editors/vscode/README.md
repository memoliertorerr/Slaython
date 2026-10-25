# Slaython for VS Code

Syntax highlighting for `.slay` files.

Install it locally:

```sh
# from the repo root
cp -r editors/vscode ~/.vscode/extensions/slaython
```

Then restart VS Code. These files are generated from `slaython/keywords.py`
by `python tools/gen_vscode_grammar.py`, so edit the keyword table, not the JSON.

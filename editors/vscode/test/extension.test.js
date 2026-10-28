'use strict';
// Smoke test for extension.js with a stubbed vscode module: node test/extension.test.js
// Show Python runs the real translator (`python -m slaython` from the repo root),
// set SLAYTHON_TEST_PYTHON to pick the interpreter.

const assert = require('assert');
const Module = require('module');
const path = require('path');
const fs = require('fs');

const repo = path.resolve(__dirname, '..', '..', '..');
const python = process.env.SLAYTHON_TEST_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const log = { sent: [], opened: [], shown: [], errors: [], warnings: [], saved: 0 };
const commands = {};
let hoverProvider;
let config = { command: `${python} -m slaython` };

class Uri { constructor(p) { this.fsPath = p; } }
class Range { constructor(a, b) { this.start = a; this.end = b; } }
class Hover { constructor(md, range) { this.contents = md; this.range = range; } }
class MarkdownString { constructor(v) { this.value = v; } }

function fakeDocument(file, text, extra = {}) {
  return {
    uri: new Uri(file), languageId: 'slaython', isUntitled: false, isDirty: false,
    getText: () => text, offsetAt: (pos) => pos, positionAt: (off) => off,
    save: async () => { log.saved++; return true; }, ...extra,
  };
}

const vscode = {
  Uri, Range, Hover, MarkdownString, ViewColumn: { Beside: -2 },
  languages: { registerHoverProvider: (lang, p) => { assert.strictEqual(lang, 'slaython'); hoverProvider = p; return {}; } },
  commands: { registerCommand: (id, fn) => { commands[id] = fn; return {}; } },
  workspace: {
    getConfiguration: () => ({ get: (k) => config[k] }),
    getWorkspaceFolder: () => ({ uri: new Uri(repo) }),
    workspaceFolders: [{ uri: new Uri(repo) }],
    openTextDocument: async (arg) => { log.opened.push(arg); return arg; },
  },
  window: {
    activeTextEditor: undefined,
    terminals: [],
    createTerminal: (opts) => {
      const t = { name: opts.name, cwd: opts.cwd, show() {}, sendText: (s) => log.sent.push(s) };
      vscode.window.terminals.push(t);
      return t;
    },
    showTextDocument: async (doc, opts) => { log.shown.push([doc, opts]); },
    showErrorMessage: (m) => log.errors.push(m),
    showWarningMessage: (m) => log.warnings.push(m),
  },
};

const load = Module._load;
Module._load = function (request, ...rest) {
  return request === 'vscode' ? vscode : load.call(this, request, ...rest);
};
const ext = require('../extension');

(async () => {
  const subs = [];
  ext.activate({ subscriptions: subs });
  assert.deepStrictEqual(Object.keys(commands).sort(),
    ['slaython.runFile', 'slaython.runTests', 'slaython.showPython']);
  assert.strictEqual(subs.length, 4);

  // hover
  const kw = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'keywords.json'), 'utf8'));
  const fumble = kw.words.find((e) => e.python === 'except');
  const doc = fakeDocument(path.join(repo, 'examples', 'hello.slay'), `x = 1\n${fumble.slang} E:\n`);
  const h = hoverProvider.provideHover(doc, 7);
  assert.ok(h.contents.value.includes('`except`') && h.contents.value.includes(fumble.why));
  assert.deepStrictEqual([h.range.start, h.range.end], [6, 6 + fumble.slang.length]);
  assert.strictEqual(hoverProvider.provideHover(doc, 1), undefined);

  // run file: saves first, then types the command into one reused terminal
  const file = path.join(repo, 'examples', 'hello.slay');
  vscode.window.activeTextEditor = { document: fakeDocument(file, '', { isDirty: true }) };
  await commands['slaython.runFile']();
  assert.strictEqual(log.saved, 1);
  assert.strictEqual(log.sent.pop(), `${config.command} ${file}`);
  await commands['slaython.runTests']();
  assert.strictEqual(log.sent.pop(), `${config.command} test ${repo}`);
  assert.strictEqual(vscode.window.terminals.length, 1);

  // show python: real translation, opened beside as a python document
  vscode.window.activeTextEditor = { document: fakeDocument(file, '') };
  await commands['slaython.showPython']();
  assert.deepStrictEqual(log.errors, []);
  const opened = log.opened.pop();
  assert.strictEqual(opened.language, 'python');
  assert.ok(/\bprint\(/.test(opened.content), opened.content);
  assert.strictEqual(log.shown.pop()[1].viewColumn, vscode.ViewColumn.Beside);

  // untitled documents go through a temp file
  vscode.window.activeTextEditor = {
    document: fakeDocument('Untitled-1', `${kw.words.find((e) => e.python === 'print').slang}("hi")\n`, { isUntitled: true }),
  };
  await commands['slaython.showPython']();
  assert.deepStrictEqual(log.errors, []);
  assert.strictEqual(log.opened.pop().content, 'print("hi")\n');

  // a missing executable gives a helpful error
  config = { command: 'definitely-not-slaython-xyz' };
  await commands['slaython.showPython']();
  assert.ok(/slaython\.command/.test(log.errors.pop()));

  console.log('extension smoke test passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});

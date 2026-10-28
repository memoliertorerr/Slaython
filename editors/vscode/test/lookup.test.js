'use strict';
// Plain node tests for lib/lookup.js and the generated data: node test/lookup.test.js

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const lookup = require('../lib/lookup');

const root = path.join(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root, 'data', 'keywords.json'), 'utf8'));
const snippets = JSON.parse(fs.readFileSync(path.join(root, 'snippets', 'slaython.json'), 'utf8'));
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const index = lookup.buildIndex(data);
const byPython = (py) => data.words.find((e) => e.python === py).slang;

let failed = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`ok   ${name}`);
  } catch (err) {
    failed++;
    console.log(`FAIL ${name}\n${err.stack}`);
  }
}

// `|` in the source marks the cursor; returns [text, offset].
function at(src) {
  const offset = src.indexOf('|');
  return [src.slice(0, offset) + src.slice(offset + 1), offset];
}
function hover(src) {
  const [text, offset] = at(src);
  const hit = lookup.wordAt(text, offset, index);
  return hit && { python: hit.entry.python, text: text.slice(hit.start, hit.end) };
}

const FUMBLE = byPython('except');
const ELIF = byPython('elif');
const [ELSE_W, IF_W] = ELIF.split(' ');
const PIPE = data.words.find((e) => e.kind === 'operator').slang;

test('plain keyword', () => {
  assert.deepStrictEqual(hover(`${FUMBLE.slice(0, 2)}|${FUMBLE.slice(2)} ValueError:`),
    { python: 'except', text: FUMBLE });
});

test('cursor at word start and end-1', () => {
  assert.strictEqual(hover(`|${FUMBLE}:`).python, 'except');
  assert.strictEqual(hover(`${FUMBLE.slice(0, -1)}|${FUMBLE.slice(-1)}:`).python, 'except');
  assert.strictEqual(hover(`${FUMBLE}|:`), null);
});

test('compound word from either half', () => {
  assert.deepStrictEqual(hover(`${ELSE_W[0]}|${ELSE_W.slice(1)} ${IF_W} x:`), { python: 'elif', text: ELIF });
  assert.deepStrictEqual(hover(`${ELSE_W} ${IF_W[0]}|${IF_W.slice(1)} x:`), { python: 'elif', text: ELIF });
  assert.deepStrictEqual(hover(`|${ELSE_W}    ${IF_W} x:`), { python: 'elif', text: `${ELSE_W}    ${IF_W}` });
  assert.strictEqual(hover(`${ELSE_W}  |  ${IF_W} x:`), null);
  assert.strictEqual(hover(`${ELSE_W[0]}|${ELSE_W.slice(1)}:`).python, 'else');
  assert.strictEqual(hover(`${IF_W[0]}|${IF_W.slice(1)} x:`).python, 'if');
});

test('pipe operator', () => {
  assert.deepStrictEqual(hover(`x |${PIPE} f`), { python: data.words.find((e) => e.slang === PIPE).python, text: PIPE });
  assert.strictEqual(hover(`x ${PIPE[0]}|${PIPE.slice(1)} f`).text, PIPE);
  assert.strictEqual(hover(`"a ${PIPE[0]}|${PIPE.slice(1)} b"`), null);
});

test('builtin, helper and syntax words', () => {
  assert.strictEqual(hover(`${byPython('print')[0]}|${byPython('print').slice(1)}("hi")`).python, 'print');
  for (const e of data.words.filter((x) => ['helper', 'syntax'].includes(x.kind))) {
    assert.strictEqual(hover(`|${e.slang} x`).python, e.python, e.slang);
  }
});

test('every entry can be hovered', () => {
  for (const e of data.words) {
    const src = e.kind === 'operator' ? `x |${e.slang} f` : `|${e.slang} x`;
    assert.strictEqual(hover(src).python, e.python, e.slang);
  }
});

test('no hover in strings, comments or on other names', () => {
  assert.strictEqual(hover(`"${FUMBLE[0]}|${FUMBLE.slice(1)}"`), null);
  assert.strictEqual(hover(`x = 1  # ${FUMBLE[0]}|${FUMBLE.slice(1)}`), null);
  assert.strictEqual(hover(`"""\n${FUMBLE[0]}|${FUMBLE.slice(1)}\n"""`), null);
  assert.strictEqual(hover(`'''a\nb ${FUMBLE[0]}|${FUMBLE.slice(1)}'''`), null);
  assert.strictEqual(hover('some|thing = 1'), null);
  assert.strictEqual(hover(`${FUMBLE}x|y`), null);
});

test('code after a closed string or multi-line string', () => {
  assert.strictEqual(hover(`"a" |${FUMBLE}`).python, 'except');
  assert.strictEqual(hover(`"""\nx\n"""\n|${FUMBLE}:`).python, 'except');
  assert.strictEqual(hover(`"it's" |${FUMBLE}`).python, 'except');
  assert.strictEqual(hover(`"a\\"b" |${FUMBLE}`).python, 'except');
});

test('f-string replacement fields are code', () => {
  const NONE = byPython('None');
  assert.strictEqual(hover(`f"{x |${NONE}}"`).python, 'None');
  assert.strictEqual(hover(`f"{d['k']} {|${NONE}}"`).python, 'None');
  assert.strictEqual(hover(`f"{x} |${NONE}"`), null);
  assert.strictEqual(hover(`f"{{|${NONE}}}"`), null);
});

test('attribute access and keyword arguments are not slang', () => {
  const DROP = byPython('yield');
  assert.strictEqual(hover(`df.|${DROP}("a")`), null);
  assert.strictEqual(hover(`f(|${DROP}=${byPython('True')})`), null);
  assert.strictEqual(hover(`f(\n    |${DROP}=1)`), null);
  assert.strictEqual(hover(`x = (|${DROP} == 1)`).python, 'yield');
  assert.strictEqual(hover(`|${DROP} x`).python, 'yield');
});

test('soft keywords only at statement start', () => {
  const SPILL = byPython('match');
  assert.strictEqual(hover(`|${SPILL} x:`).python, 'match');
  assert.strictEqual(hover(`    |${SPILL} x:`).python, 'match');
  assert.strictEqual(hover(`y = |${SPILL}`), null);
});

test('CRLF lines', () => {
  assert.strictEqual(hover(`x = 1\r\n|${FUMBLE}:\r\n`).python, 'except');
});

test('hover markdown has python and why', () => {
  const e = data.words.find((x) => x.python === 'except');
  const md = lookup.hoverMarkdown(e);
  assert.ok(md.includes('`except`'), md);
  assert.ok(md.includes(e.why), md);
  assert.ok(md.includes(e.meaning), md);
  const pipe = lookup.hoverMarkdown(data.words.find((x) => x.kind === 'operator'));
  assert.ok(pipe.includes(PIPE), pipe);
});

test('splitCommand', () => {
  assert.deepStrictEqual(lookup.splitCommand('slaython'), ['slaython']);
  assert.deepStrictEqual(lookup.splitCommand('  python  -m slaython '), ['python', '-m', 'slaython']);
  assert.deepStrictEqual(lookup.splitCommand('"C:\\My Py\\python.exe" -m slaython'),
    ['C:\\My Py\\python.exe', '-m', 'slaython']);
  assert.deepStrictEqual(lookup.splitCommand(''), []);
});

test('terminalLine quoting', () => {
  assert.strictEqual(lookup.terminalLine('slaython', ['/a/b.slay'], 'linux'), 'slaython /a/b.slay');
  assert.strictEqual(lookup.terminalLine('python -m slaython', ['/a b/it\'s.slay'], 'darwin'),
    "python -m slaython '/a b/it'\\''s.slay'");
  assert.strictEqual(lookup.terminalLine('slaython', ['test', 'C:\\a b'], 'win32'), 'slaython "test" "C:\\a b"');
});

test('snippets use the current words', () => {
  const known = new Set(data.words.flatMap((e) => e.slang.split(' ')));
  const bodies = Object.values(snippets);
  assert.ok(bodies.length >= 20);
  for (const s of bodies) {
    const first = s.body[0].split(/[\s:(]/)[0];
    assert.ok(known.has(first), `snippet starts with unknown word ${first}`);
    assert.ok(Array.isArray(s.body) && s.description, JSON.stringify(s));
  }
  const prefixes = bodies.flatMap((s) => [].concat(s.prefix));
  assert.strictEqual(new Set(prefixes).size, prefixes.length, 'duplicate snippet prefixes');
  const want = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'match', 'case', 'with']
    .map(byPython);
  for (const w of want) assert.ok(prefixes.includes(w.replace(' ', '')), `no snippet for ${w}`);
  for (const e of data.words.filter((x) => x.kind === 'syntax')) {
    assert.ok(prefixes.includes(e.slang), `no snippet for ${e.slang}`);
  }
});

test('package.json commands are all wired up', () => {
  const src = fs.readFileSync(path.join(root, 'extension.js'), 'utf8');
  for (const c of pkg.contributes.commands) {
    assert.ok(src.includes(`'${c.command}'`), `${c.command} not registered`);
  }
  assert.strictEqual(pkg.main, './extension.js');
  assert.strictEqual(pkg.version, data.version);
});

if (failed) {
  console.log(`${failed} failed`);
  process.exit(1);
}
console.log('all passed');

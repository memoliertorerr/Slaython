'use strict';
// Pure helpers for the extension (no vscode API), so they can be tested with plain node.

const IDENT = /[\p{L}\p{N}_]+/gu;
const IDENT_CHAR = /[\p{L}\p{N}_]/u;

// Builds lookup tables from the generated data/keywords.json.
function buildIndex(data) {
  const index = { words: new Map(), compounds: [], operators: [] };
  for (const entry of data.words) {
    if (entry.kind === 'operator') {
      index.operators.push(entry);
    } else if (entry.kind === 'compound') {
      index.compounds.push({ parts: entry.slang.split(/\s+/), entry });
    } else {
      index.words.set(entry.slang, entry);
    }
  }
  index.operators.sort((a, b) => b.slang.length - a.slang.length);
  return index;
}

// Scans text up to `offset` and reports whether it is code, string or comment,
// plus the bracket depth there. Handles triple quotes and f-string {...} parts.
function scanState(text, offset) {
  let depth = 0;
  let quote = null;   // '"', "'", '"""' or "'''" while inside a string
  let fstring = false;
  let fdepth = 0;     // brace depth inside an f-string replacement field
  let i = 0;
  while (i < offset) {
    const ch = text[i];
    if (quote && fdepth === 0) {
      if (ch === '\\') { i += 2; continue; }
      if (text.startsWith(quote, i)) { i += quote.length; quote = null; continue; }
      if (quote.length === 1 && ch === '\n') { quote = null; i++; continue; }
      if (fstring && ch === '{') {
        if (text[i + 1] === '{') { i += 2; continue; }
        fdepth = 1;
      }
      i++;
      continue;
    }
    if (quote) {
      // code inside an f-string replacement field
      if (ch === '{') fdepth++;
      else if (ch === '}') fdepth--;
      i++;
      continue;
    }
    if (ch === '#') {
      const nl = text.indexOf('\n', i);
      if (nl === -1 || nl >= offset) return { state: 'comment', depth };
      i = nl;
      continue;
    }
    if (ch === '"' || ch === "'") {
      let p = i - 1;
      while (p >= 0 && /[rRbBuUfF]/.test(text[p])) p--;
      const prefix = text.slice(p + 1, i);
      const isPrefix = prefix.length <= 2 && (p < 0 || !IDENT_CHAR.test(text[p]));
      fstring = isPrefix && /[fF]/.test(prefix);
      quote = text.startsWith(ch.repeat(3), i) ? ch.repeat(3) : ch;
      i += quote.length;
      continue;
    }
    if (ch === '(' || ch === '[' || ch === '{') depth++;
    else if ((ch === ')' || ch === ']' || ch === '}') && depth > 0) depth--;
    i++;
  }
  if (quote) return { state: fdepth > 0 ? 'code' : 'string', depth };
  return { state: 'code', depth };
}

function lineBounds(text, offset) {
  const start = text.lastIndexOf('\n', offset - 1) + 1;
  let end = text.indexOf('\n', offset);
  if (end === -1) end = text.length;
  if (end > start && text[end - 1] === '\r') end--;
  return { start, end };
}

// Identifier tokens on [start, end) of text, as {word, start, end} with absolute offsets.
function tokens(text, start, end) {
  const out = [];
  const line = text.slice(start, end);
  for (const m of line.matchAll(IDENT)) {
    out.push({ word: m[0], start: start + m.index, end: start + m.index + m[0].length });
  }
  return out;
}

// Finds the Slaython word or operator at `offset` in `text`.
// Returns {entry, start, end} (absolute offsets) or null.
function wordAt(text, offset, index) {
  const { start: ls, end: le } = lineBounds(text, offset);

  for (const op of index.operators) {
    const from = Math.max(ls, offset - op.slang.length + 1);
    for (let s = from; s <= offset && s + op.slang.length <= le; s++) {
      if (text.startsWith(op.slang, s) && scanState(text, s).state === 'code') {
        return { entry: op, start: s, end: s + op.slang.length };
      }
    }
  }

  const toks = tokens(text, ls, le);
  const k = toks.findIndex((t) => t.start <= offset && offset < t.end);
  if (k === -1) return null;
  const tok = toks[k];
  const ctx = scanState(text, tok.start);
  if (ctx.state !== 'code') return null;

  const before = text.slice(ls, tok.start);
  const after = text.slice(tok.end, le);
  if (/\.\s*$/.test(before) && !/\.\.\.\s*$/.test(before)) return null; // attribute: df.drop
  if (ctx.depth > 0 && /^\s*=(?!=)/.test(after)) return null;             // keyword argument

  // two-word keywords such as `ornah fr`
  for (const { parts, entry } of index.compounds) {
    for (let p = 0; p < parts.length; p++) {
      const first = k - p;
      if (first < 0 || first + parts.length > toks.length) continue;
      const run = toks.slice(first, first + parts.length);
      const matches = run.every((t, j) => t.word === parts[j]);
      const gapsOk = run.every((t, j) => j === 0 || /^\s+$/.test(text.slice(run[j - 1].end, t.start)));
      if (matches && gapsOk) return { entry, start: run[0].start, end: run[run.length - 1].end };
    }
  }

  const entry = index.words.get(tok.word);
  if (!entry) return null;
  // soft keywords (spill, pov) only count at the start of a statement
  if (entry.kind === 'soft' && before.trim() !== '') return null;
  return { entry, start: tok.start, end: tok.end };
}

const KIND_LABEL = {
  keyword: 'Python keyword',
  soft: 'Python soft keyword',
  compound: 'Python keyword',
  builtin: 'Python builtin',
  helper: 'Slaython helper, works like',
  syntax: 'Slaython syntax, like',
  operator: 'Slaython operator,',
};

function code(text) {
  const ticks = text.includes('`') ? '``' : '`';
  return `${ticks}${text}${ticks}`;
}

// Markdown shown on hover, e.g. **fumble** = Python keyword `except`.
function hoverMarkdown(entry) {
  const label = KIND_LABEL[entry.kind] || 'Python';
  return [
    `**${entry.slang}** = ${label} ${code(entry.python)}`,
    '',
    entry.why,
    '',
    `*${entry.slang}: ${entry.meaning}*`,
  ].join('\n');
}

// Splits a command setting like `python -m slaython` or `"C:\My Python\python.exe" -m slaython`.
function splitCommand(command) {
  const parts = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  for (const m of String(command || '').matchAll(re)) {
    parts.push(m[1] !== undefined ? m[1] : m[2] !== undefined ? m[2] : m[3]);
  }
  return parts;
}

// Quotes a path for typing into an integrated terminal.
function quoteArg(arg, platform) {
  if (platform === 'win32') return `"${arg}"`;
  if (/^[\w@%+=:,./-]+$/.test(arg)) return arg;
  return `'${arg.replace(/'/g, "'\\''")}'`;
}

// The line typed into the terminal, e.g. `slaython '/path/my file.slay'`.
function terminalLine(command, args, platform) {
  return [String(command || 'slaython').trim(), ...args.map((a) => quoteArg(a, platform))].join(' ');
}

module.exports = {
  buildIndex, scanState, wordAt, hoverMarkdown, splitCommand, quoteArg, terminalLine,
};

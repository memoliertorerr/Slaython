"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const BUILD = document.querySelector('meta[name="build"]').content;
  const PY_ROOT = "/slay";           // where the package lives inside Pyodide
  const DRAFT_KEY = "slaython-playground-draft";
  const MAX_OUTPUT = 200000;         // characters kept in the output panel
  const INDENT = "    ";
  const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  const els = {
    code: $("code"), hl: $("hl"), gutter: $("gutter"), editor: $("editor"),
    run: $("run"), runLabel: $("run-label"), runKeys: $("run-keys"),
    examples: $("examples"), share: $("share"), clear: $("clear"),
    tabOut: $("tab-out"), tabPy: $("tab-py"), outPanel: $("out-panel"), pyPanel: $("py-panel"),
    output: $("output"), python: $("python"),
    status: $("status"), statusText: $("status-text"),
    find: $("find"), sheet: $("sheet-body"), toast: $("toast"),
    version: $("version"), repo: $("repo-link"),
  };

  let manifest = null;
  let api = null;         // the slay_playground module inside Pyodide
  let running = false;

  // ---------- small helpers ----------

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* storage blocked */ } },
  };

  function setStatus(state, text) {
    els.status.dataset.state = state;
    els.statusText.textContent = text;
  }

  let toastTimer = 0;
  function toast(text) {
    els.toast.textContent = text;
    els.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { els.toast.hidden = true; }, 2200);
  }

  function escapeHtml(s) {
    return s.replace(/[&<>]/g, (c) => (c === "&" ? "&amp;" : c === "<" ? "&lt;" : "&gt;"));
  }

  // base64url of UTF-8 text, for share links
  function encodeCode(text) {
    const bytes = new TextEncoder().encode(text);
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function decodeCode(b64) {
    const norm = b64.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(norm + "===".slice((norm.length + 3) % 4));
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  }

  function codeFromHash() {
    const m = /(?:^#|&)code=([A-Za-z0-9_-]*)/.exec(location.hash);
    if (!m) return null;
    try { return decodeCode(m[1]); } catch { return null; }
  }

  // ---------- highlighting ----------

  const PY_KEYWORDS = new Set((
    "False None True and as assert async await break class continue def del elif else except " +
    "finally for from global if import in is lambda nonlocal not or pass raise return try while " +
    "with yield match case"
  ).split(" "));
  const CONSTS = new Set(["True", "False", "None"]);

  // word -> { cls, soft }, filled from manifest.keywords
  const SLANG = new Map();

  function loadWords(keywords) {
    for (const k of keywords) {
      if (k.kind === "operator") continue;
      const cls = k.kind === "builtin" || k.kind === "helper" ? "t-builtin"
        : CONSTS.has(k.python) ? "t-const" : "t-slang";
      const soft = k.kind === "soft" || k.slang === "runitfoo";
      for (const w of k.slang.split(/\s+/)) {
        if (/^[\p{L}_][\p{L}\p{N}_]*$/u.test(w) && !SLANG.has(w)) SLANG.set(w, { cls, soft });
      }
    }
  }

  const TOKEN = new RegExp([
    "(#[^\\n]*)",                                                     // 1 comment
    "((?:[rRbBuUfF]{1,2})?(?:'''[\\s\\S]*?(?:'''|$)|\"\"\"[\\s\\S]*?(?:\"\"\"|$)" +
      "|'(?:\\\\.|[^'\\\\\\n])*'?|\"(?:\\\\.|[^\"\\\\\\n])*\"?))",    // 2 string
    "([\\p{L}_][\\p{L}\\p{N}_]*)",                                    // 3 name
    "(\\d[\\d_]*(?:\\.[\\d_]*)?(?:[eE][+-]?\\d+)?[jJ]?|\\.\\d[\\d_]*)", // 4 number
    "(\\|>)",                                                         // 5 pipe
    "([(\\[{])", "([)\\]}])",                                         // 6 open, 7 close
    "(\\n)",                                                          // 8 newline
    "([^\\S\\n]+)",                                                   // 9 spaces
    "([\\s\\S])",                                                     // 10 anything else
  ].join("|"), "gu");

  // Returns highlighted HTML. slangMode=false highlights plain Python.
  function highlight(src, slangMode) {
    let out = "";
    let depth = 0;
    let lineStart = true;    // no token yet on this logical line
    let prev = "";           // previous significant token text
    TOKEN.lastIndex = 0;
    let m;
    while ((m = TOKEN.exec(src)) !== null) {
      const t = m[0];
      if (t === "") { TOKEN.lastIndex++; continue; }
      if (m[9] !== undefined) { out += t; continue; }
      if (m[8] !== undefined) {
        out += t;
        if (depth === 0) lineStart = true;
        continue;
      }
      const atStart = lineStart;
      lineStart = false;
      let cls = "";
      if (m[1] !== undefined) { cls = "t-com"; lineStart = atStart; }
      else if (m[2] !== undefined) cls = "t-str";
      else if (m[4] !== undefined) cls = "t-num";
      else if (m[5] !== undefined) cls = slangMode ? "t-op" : "";
      else if (m[6] !== undefined) depth++;
      else if (m[7] !== undefined) depth = Math.max(0, depth - 1);
      else if (m[3] !== undefined) cls = nameClass(src, m, prev, atStart, depth, slangMode);
      if (m[1] === undefined) prev = t;
      out += cls ? `<span class="${cls}">${escapeHtml(t)}</span>` : escapeHtml(t);
    }
    return out;
  }

  function nameClass(src, m, prev, atStart, depth, slangMode) {
    const word = m[0];
    if (prev === ".") return "";                         // attribute access stays as-is
    if (slangMode && SLANG.has(word)) {
      const info = SLANG.get(word);
      if (info.soft && !atStart) return "";
      if (depth > 0) {                                   // keyword argument: f(drop=nocap)
        const rest = src.slice(m.index + word.length);
        if (/^[^\S\n]*=(?!=)/.test(rest)) return "";
      }
      return info.cls;
    }
    if (PY_KEYWORDS.has(word)) return CONSTS.has(word) ? "t-const" : "t-pykw";
    return "";
  }

  // ---------- editor ----------

  function syncEditor() {
    const src = els.code.value;
    try {
      els.hl.innerHTML = highlight(src, true) + "\n";
    } catch (err) {
      els.editor.classList.add("plain");     // fall back to an unhighlighted textarea
      console.error(err);
    }
    let lines = 1;
    for (let i = 0; i < src.length; i++) if (src.charCodeAt(i) === 10) lines++;
    if (els.gutter.dataset.lines !== String(lines)) {
      els.gutter.dataset.lines = String(lines);
      let g = "";
      for (let i = 1; i <= lines; i++) g += i + "\n";
      els.gutter.textContent = g;
    }
    syncScroll();
  }

  function syncScroll() {
    const { scrollTop, scrollLeft } = els.code;
    els.hl.parentElement.style.transform = `translate(${-scrollLeft}px, ${-scrollTop}px)`;
    els.gutter.style.transform = `translateY(${-scrollTop}px)`;
  }

  let syncQueued = false;
  function queueSync() {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(() => { syncQueued = false; syncEditor(); });
  }

  // Replace [start, end) with text, keeping the browser's undo history when possible.
  function replaceRange(start, end, text, selStart, selEnd) {
    const ta = els.code;
    ta.focus();
    ta.setSelectionRange(start, end);
    let done = false;
    try {
      done = text === "" ? document.execCommand("delete") : document.execCommand("insertText", false, text);
    } catch { done = false; }
    if (!done || ta.value.slice(start, start + text.length) !== text) {
      ta.setRangeText(text, start, end, "end");
      ta.dispatchEvent(new Event("input"));
    }
    if (selStart !== undefined) ta.setSelectionRange(selStart, selEnd === undefined ? selStart : selEnd);
  }

  function setCode(text) {
    const ta = els.code;
    if (ta.value === text) return;
    replaceRange(0, ta.value.length, text, 0, 0);
    ta.scrollTop = 0;
    ta.scrollLeft = 0;
  }

  function lineBounds(value, start, end) {
    const from = value.lastIndexOf("\n", start - 1) + 1;
    // A selection ending right after a newline doesn't include the next line.
    const stop = end > start && value[end - 1] === "\n" ? end - 1 : end;
    let to = value.indexOf("\n", stop);
    if (to === -1) to = value.length;
    return [from, to];
  }

  let tabReleased = false;

  function onKeyDown(e) {
    const ta = els.code;
    const { selectionStart: s, selectionEnd: t, value } = ta;
    if (e.key === "Escape") { tabReleased = true; return; }
    if (e.key === "Tab" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (tabReleased) { tabReleased = false; return; }
      e.preventDefault();
      const multi = value.slice(s, t).includes("\n");
      if (!e.shiftKey && !multi) {
        const col = s - (value.lastIndexOf("\n", s - 1) + 1);
        const pad = " ".repeat(4 - (col % 4));
        replaceRange(s, t, pad, s + pad.length);
        return;
      }
      const [from, to] = lineBounds(value, s, t);
      const lines = value.slice(from, to).split("\n");
      let firstDelta = 0;
      const changed = lines.map((line, i) => {
        let d;
        if (e.shiftKey) {
          const n = line.match(/^ {0,4}/)[0].length || (line[0] === "\t" ? 1 : 0);
          d = -n;
          line = line.slice(n);
        } else {
          d = line.length ? INDENT.length : 0;
          line = (line.length ? INDENT : "") + line;
        }
        if (i === 0) firstDelta = d;
        return line;
      }).join("\n");
      if (changed === value.slice(from, to)) return;
      const total = changed.length - (to - from);
      const newStart = Math.max(from, s + firstDelta);
      replaceRange(from, to, changed, multi ? from : newStart, multi ? to + total : Math.max(from, t + firstDelta));
      return;
    }
    tabReleased = false;
    if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey && !e.isComposing) {
      const from = value.lastIndexOf("\n", s - 1) + 1;
      const before = value.slice(from, s);
      let indent = before.match(/^[ \t]*/)[0];
      if (/:\s*(#.*)?$/.test(before)) indent += INDENT;
      e.preventDefault();
      replaceRange(s, t, "\n" + indent, s + 1 + indent.length);
      return;
    }
    if (e.key === "Backspace" && s === t && s > 0) {
      const from = value.lastIndexOf("\n", s - 1) + 1;
      const before = value.slice(from, s);
      if (before.length && /^ +$/.test(before)) {
        e.preventDefault();
        const n = before.length % 4 || 4;
        replaceRange(s - n, s, "", s - n);
      }
    }
  }

  let draftTimer = 0;
  function onInput() {
    queueSync();
    if (els.pyPanel.hidden === false) queueTranslate();
    clearTimeout(draftTimer);
    draftTimer = setTimeout(() => store.set(DRAFT_KEY, els.code.value), 300);
    // Once edited, the code no longer matches a shared link; the draft has it.
    if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  }

  // ---------- output ----------

  let outLength = 0;
  let outTruncated = false;

  function clearOutput() {
    els.output.textContent = "";
    outLength = 0;
    outTruncated = false;
  }

  function write(text, cls) {
    if (!text) return;
    if (outTruncated) return;
    if (outLength + text.length > MAX_OUTPUT) {
      text = text.slice(0, Math.max(0, MAX_OUTPUT - outLength));
      outTruncated = true;
    }
    outLength += text.length;
    const last = els.output.lastChild;
    if (last && last.nodeType === 1 && last.className === cls) {
      last.appendChild(document.createTextNode(text));
    } else {
      const span = document.createElement("span");
      span.className = cls;
      span.textContent = text;
      els.output.appendChild(span);
    }
    if (outTruncated) note("\n[output cut off: more than " + MAX_OUTPUT.toLocaleString() + " characters]\n");
    els.outPanel.scrollTop = els.outPanel.scrollHeight;
  }

  function note(text) {
    const span = document.createElement("span");
    span.className = "note";
    span.textContent = text;
    els.output.appendChild(span);
  }

  function hint(text) {
    clearOutput();
    const span = document.createElement("span");
    span.className = "hint";
    span.textContent = text;
    els.output.appendChild(span);
  }

  // Text written to stdout since the last newline: becomes the hmu() prompt.
  let pendingLine = "";

  function streamWriter(cls) {
    const decoder = new TextDecoder();
    return (buf) => {
      const text = decoder.decode(buf, { stream: true });
      if (cls === "out") {
        const nl = text.lastIndexOf("\n");
        pendingLine = nl === -1 ? pendingLine + text : text.slice(nl + 1);
      }
      write(text, cls);
      return buf.length;
    };
  }

  function readInput() {
    const question = pendingLine.trim() || "Input for hmu()";
    const answer = window.prompt(question, "");
    if (answer === null) return null;          // cancel = end of input (EOFError)
    write(answer + "\n", "in");
    pendingLine = "";
    return answer;
  }

  // ---------- tabs and python view ----------

  function showTab(which) {
    const py = which === "py";
    els.tabOut.setAttribute("aria-selected", String(!py));
    els.tabPy.setAttribute("aria-selected", String(py));
    els.outPanel.hidden = py;
    els.pyPanel.hidden = !py;
    if (py) translateNow();
  }

  let translateTimer = 0;
  function queueTranslate() {
    clearTimeout(translateTimer);
    translateTimer = setTimeout(translateNow, 150);
  }

  function translateNow() {
    if (!api) {
      els.python.innerHTML = '<span class="hint">The Python view works once Python has loaded.</span>';
      return;
    }
    const res = callPy(api.translate, els.code.value);
    if (res[0]) {
      els.python.innerHTML = highlight(res[1], false);
    } else {
      els.python.innerHTML = `<span class="err">${escapeHtml(res[1])}</span>`;
    }
  }

  // Call a Python function and convert its list result to a JS array.
  function callPy(fn, ...args) {
    const res = fn(...args);
    try { return res.toJs(); } finally { res.destroy(); }
  }

  // ---------- running ----------

  async function run() {
    if (!api || running) return;
    running = true;
    showTab("out");
    clearOutput();
    pendingLine = "";
    els.run.disabled = true;
    els.runLabel.textContent = "Running";
    setStatus("running", "Running");
    // Let the browser paint the cleared panel before Python takes over.
    await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
    const started = performance.now();
    let result = [1, false];
    try {
      // callPromising lets asyncio.run() work where the browser supports it.
      const out = api.run.callPromising ? await api.run.callPromising(els.code.value) : api.run(els.code.value);
      try { result = out.toJs(); } finally { out.destroy(); }
    } catch (err) {
      write(String(err && err.message || err) + "\n", "err");
    }
    const ms = performance.now() - started;
    const took = ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
    const [code, exited] = result;
    if (els.output.childNodes.length === 0) note("(no output)\n");
    if (code === 0) setStatus("ok", exited ? `Touched grass after ${took}` : `Done in ${took}`);
    else setStatus("error", `Exited with code ${code} after ${took}`);
    running = false;
    els.run.disabled = false;
    els.runLabel.textContent = "Run";
  }

  // ---------- examples, share, sheet ----------

  async function loadExample(file) {
    const res = await fetch(`${file}?v=${BUILD}`);
    if (!res.ok) throw new Error(`${file}: ${res.status}`);
    return res.text();
  }

  function fillExamples() {
    for (const ex of manifest.examples) {
      const opt = document.createElement("option");
      opt.value = ex.file;
      opt.textContent = ex.name;
      if (ex.about) opt.title = ex.about;
      els.examples.appendChild(opt);
    }
  }

  async function share() {
    const url = `${location.origin}${location.pathname}#code=${encodeCode(els.code.value)}`;
    history.replaceState(null, "", url);
    try {
      await navigator.clipboard.writeText(url);
      toast("Link copied");
    } catch {
      window.prompt("Copy this link", url);
    }
  }

  const GROUPS = [
    ["Keywords", (k) => ["keyword", "soft", "compound"].includes(k.kind)],
    ["Builtins", (k) => k.kind === "builtin"],
    ["Helpers", (k) => k.kind === "helper"],
    ["New syntax", (k) => k.kind === "syntax" || k.kind === "operator"],
    ["Other", () => true],
  ];

  function renderSheet(filter) {
    const q = (filter || "").trim().toLowerCase();
    const words = manifest.keywords.filter((k) => !q ||
      k.slang.toLowerCase().includes(q) || k.python.toLowerCase().includes(q) || k.why.toLowerCase().includes(q));
    const used = new Set();
    let html = "";
    for (const [title, test] of GROUPS) {
      const rows = words.filter((k) => !used.has(k) && test(k));
      rows.forEach((k) => used.add(k));
      if (!rows.length) continue;
      html += `<div class="sheet-group"><h3>${title}</h3>`;
      for (const k of rows) {
        html += `<div class="row"><code class="s">${escapeHtml(k.slang)}</code>` +
          `<code class="p">${escapeHtml(k.python)}</code><span class="w">${escapeHtml(k.why)}</span></div>`;
      }
      html += "</div>";
    }
    const kept = (manifest.kept_python || []).filter((w) => !q || w.includes(q));
    if (kept.length) {
      html += `<div class="sheet-group"><h3>Plain Python</h3>`;
      for (const w of kept) {
        html += `<div class="row"><code class="s">${escapeHtml(w)}</code><code class="p">${escapeHtml(w)}</code>` +
          `<span class="w">no slang, write it as in Python</span></div>`;
      }
      html += "</div>";
    }
    els.sheet.innerHTML = html || `<p class="sheet-empty">No word matches "${escapeHtml(filter)}".</p>`;
  }

  // ---------- boot ----------

  async function bootPython() {
    if (typeof loadPyodide !== "function") throw new Error("the Pyodide script did not load");
    setStatus("loading", "Loading Python");
    const pyodide = await loadPyodide();
    setStatus("loading", "Loading Slaython");
    const files = [...manifest.package, "slay_playground.py"];
    const texts = await Promise.all(files.map(async (f) => {
      const res = await fetch(`${f}?v=${BUILD}`);
      if (!res.ok) throw new Error(`${f}: ${res.status}`);
      return res.text();
    }));
    files.forEach((f, i) => {
      const path = `${PY_ROOT}/${f}`;
      pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
      pyodide.FS.writeFile(path, texts[i]);
    });
    pyodide.setStdout({ write: streamWriter("out"), isatty: false });
    pyodide.setStderr({ write: streamWriter("err"), isatty: false });
    pyodide.setStdin({ stdin: readInput, isatty: false });
    pyodide.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(PY_ROOT)})\nimport slaython`);
    api = pyodide.pyimport("slay_playground");
  }

  async function boot() {
    els.runKeys.textContent = IS_MAC ? "Cmd+Enter" : "Ctrl+Enter";
    els.code.addEventListener("input", onInput);
    els.code.addEventListener("scroll", syncScroll, { passive: true });
    els.code.addEventListener("keydown", onKeyDown);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); }
    });
    els.run.addEventListener("click", run);
    els.clear.addEventListener("click", clearOutput);
    els.share.addEventListener("click", share);
    els.tabOut.addEventListener("click", () => showTab("out"));
    els.tabPy.addEventListener("click", () => showTab("py"));
    els.tabOut.parentElement.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        const next = els.tabOut.getAttribute("aria-selected") === "true" ? els.tabPy : els.tabOut;
        showTab(next === els.tabPy ? "py" : "out");
        next.focus();
      }
    });
    els.examples.addEventListener("change", async () => {
      const file = els.examples.value;
      if (!file) return;
      try { setCode(await loadExample(file)); } catch (err) { toast(`Couldn't load that example (${err.message})`); }
      els.examples.value = "";
    });
    els.find.addEventListener("input", () => renderSheet(els.find.value));
    window.addEventListener("hashchange", () => {
      const shared = codeFromHash();
      if (shared !== null) setCode(shared);
    });

    hint("Python is loading. You can start typing.");
    setStatus("loading", "Loading");

    // Show something in the editor right away; a shared link wins over the draft.
    const shared = codeFromHash();
    const draft = store.get(DRAFT_KEY);
    if (shared !== null) els.code.value = shared;
    else if (draft) els.code.value = draft;
    syncEditor();

    try {
      const res = await fetch(`manifest.json?v=${BUILD}`, { cache: "no-cache" });
      if (!res.ok) throw new Error(`manifest.json: ${res.status}`);
      manifest = await res.json();
    } catch (err) {
      setStatus("error", "Couldn't load the playground");
      hint(`Couldn't load manifest.json (${err.message}). If you opened this file directly, build it with tools/build_playground.py and serve the _site folder.`);
      return;
    }
    els.version.textContent = `v${manifest.version}`;
    els.version.hidden = false;
    if (manifest.repo) { els.repo.href = manifest.repo; els.repo.hidden = false; }
    loadWords(manifest.keywords);
    fillExamples();
    renderSheet("");
    if (shared === null && !draft && manifest.examples.length) {
      try { els.code.value = await loadExample(manifest.examples[0].file); } catch { /* leave it empty */ }
    }
    syncEditor();

    try {
      await bootPython();
    } catch (err) {
      console.error(err);
      setStatus("error", "Python didn't load");
      hint(`Couldn't load Python (${err.message}). Check your connection and reload the page.`);
      return;
    }
    els.run.disabled = false;
    setStatus("idle", "Ready");
    const touch = window.matchMedia && matchMedia("(pointer: coarse)").matches;
    hint(touch ? "Ready. Press Run." : `Ready. Press Run or ${IS_MAC ? "Cmd" : "Ctrl"}+Enter.`);
    if (!els.pyPanel.hidden) translateNow();
  }

  boot();
})();

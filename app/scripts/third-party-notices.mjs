// Writes THIRD-PARTY-NOTICES.txt: the open-source Rust crates compiled into the desktop app, with their licences
// and the licence texts and copyright notices they ship. The installers include the file, and each release
// carries a copy.
//
// Run from app/ before `tauri build` (it needs cargo; the first run downloads the crates):
//   node scripts/third-party-notices.mjs [output file]
// NOTICE_TARGETS (comma-separated target triples) sets the platforms; by default Windows and both Macs.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const OUT = process.argv[2] || path.join('src-tauri', 'THIRD-PARTY-NOTICES.txt');
const MANIFEST = path.join('src-tauri', 'Cargo.toml');
const TARGETS = (process.env.NOTICE_TARGETS || 'x86_64-pc-windows-msvc,aarch64-apple-darwin,x86_64-apple-darwin')
  .split(',').map((s) => s.trim()).filter(Boolean);
const LICENCE_FILE = /^(licen[cs]e|copying|copyright|notice|unlicense)([-._ ].*)?$/i;
const LICENCE_DIR = /^licen[cs]es?$/i;
const MAX_TEXT = 100000;

function metadata(target) {
  const args = ['metadata', '--format-version', '1', '--manifest-path', MANIFEST, '--filter-platform', target];
  return JSON.parse(execFileSync('cargo', args, { encoding: 'utf8', maxBuffer: 1 << 28, stdio: ['ignore', 'pipe', 'inherit'] }));
}

// Packages reachable from the app through normal dependencies (build scripts and dev-only crates are not shipped).
const packages = new Map(), shipped = new Set();
let rootName = '', rootVersion = '';
for (const target of TARGETS) {
  const meta = metadata(target);
  for (const p of meta.packages) packages.set(p.id, p);
  const nodes = new Map(meta.resolve.nodes.map((n) => [n.id, n]));
  const root = meta.resolve.root;
  const rootPkg = packages.get(root);
  if (rootPkg) { rootName = rootPkg.name; rootVersion = rootPkg.version; }
  const stack = [root], seen = new Set();
  while (stack.length) {
    const id = stack.pop();
    if (seen.has(id)) continue;
    seen.add(id);
    if (id !== root) shipped.add(id);
    const node = nodes.get(id);
    if (!node) continue;
    for (const dep of node.deps || []) {
      if ((dep.dep_kinds || []).some((k) => k.kind === null || k.kind === undefined || k.kind === 'normal')) stack.push(dep.pkg);
    }
  }
}

function licenceFiles(p) {
  const dir = path.dirname(p.manifest_path), files = [];
  const add = (f) => { try { if (fs.statSync(f).isFile() && !files.includes(f)) files.push(f); } catch (e) { /* missing */ } };
  if (p.license_file) add(path.resolve(dir, p.license_file));
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return files; }
  for (const e of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.isFile() && LICENCE_FILE.test(e.name)) add(path.join(dir, e.name));
    else if (e.isDirectory() && LICENCE_DIR.test(e.name)) {
      for (const f of fs.readdirSync(path.join(dir, e.name)).sort()) add(path.join(dir, e.name, f));
    }
  }
  return files;
}
function readText(f) {
  let t = fs.readFileSync(f, 'utf8').replace(/\r\n?/g, '\n').replace(/[ \t]+$/gm, '').trim();
  if (t.length > MAX_TEXT) t = t.slice(0, MAX_TEXT) + '\n[… shortened; the full text is in the crate]';
  return t;
}

const crates = [...shipped].map((id) => packages.get(id)).filter(Boolean)
  .sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version, undefined, { numeric: true }));
const texts = new Map();   // hash -> { n, text, users: [] }
const rows = [];
for (const p of crates) {
  const refs = [];
  for (const f of licenceFiles(p)) {
    const text = readText(f);
    if (!text) continue;
    const key = createHash('sha256').update(text).digest('hex');
    if (!texts.has(key)) texts.set(key, { n: texts.size + 1, text, users: [] });
    const entry = texts.get(key);
    entry.users.push(p.name + ' ' + p.version);
    refs.push(entry.n);
  }
  rows.push({ name: p.name, version: p.version, licence: p.license || (p.license_file ? 'see licence file' : 'not stated'),
    repo: p.repository || p.homepage || 'https://crates.io/crates/' + p.name, refs });
}

const lines = [];
lines.push('Supercon Progress ' + (rootVersion || '') + ': third-party software notices', '');
lines.push('The desktop app is built with Tauri and the open-source Rust crates listed below, compiled into the app.',
  'Each crate is used under the licence shown; where a crate offers a choice (for example "MIT OR Apache-2.0"),',
  'any of the listed licences applies. The licence texts and copyright notices that ship with each crate follow',
  'the list, each text once, with the crates that use it.', '',
  'The app shows its interface in the web view that comes with the operating system (Microsoft Edge WebView2 on',
  'Windows, WebKit on macOS); it is not part of the app. The Windows installers are made with NSIS and the WiX',
  'Toolset using Tauri\'s installer templates. The app\'s own interface (index.html) contains no third-party code.', '',
  'Platforms covered: ' + TARGETS.join(', '), 'Crates: ' + rows.length, '');
lines.push('== Crates ==', '');
for (const r of rows) {
  lines.push(r.name + ' ' + r.version, '  Licence: ' + r.licence, '  Source: ' + r.repo,
    '  Licence text: ' + (r.refs.length ? r.refs.map((n) => '[' + n + ']').join(' ') : 'none shipped with the crate; see the source'), '');
}
lines.push('== Licence texts ==', '');
for (const t of [...texts.values()].sort((a, b) => a.n - b.n)) {
  lines.push('[' + t.n + '] Used by: ' + t.users.join(', '), '', t.text, '', '-'.repeat(78), '');
}
fs.writeFileSync(OUT, lines.join('\n') + '\n');
console.log('Wrote ' + OUT + ': ' + rows.length + ' crates, ' + texts.size + ' distinct licence texts' + (rootName ? ' (' + rootName + ')' : ''));
const missing = rows.filter((r) => !r.refs.length).map((r) => r.name);
if (missing.length) console.log('No licence file shipped with: ' + missing.join(', '));

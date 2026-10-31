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

// Standard texts for crates that do not ship a licence file. MIT, BSD-3-Clause and Zlib get the crate's own copyright
// line (from its authors); Apache-2.0 and MPL-2.0 point to the full text shipped by another crate, or to the official one.
const MIT_BODY = `Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;
const BSD3_BODY = `Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.`;
const ZLIB_BODY = `This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.`;
const OFFICIAL = { 'Apache-2.0': 'https://www.apache.org/licenses/LICENSE-2.0.txt', 'MPL-2.0': 'https://www.mozilla.org/MPL/2.0/' };
const FULL_TEXT = { 'Apache-2.0': /Apache License\s+Version 2\.0, January 2004/, 'MPL-2.0': /Mozilla Public License,? Version 2\.0/ };
// For a licence choice ("A OR B"), the first of these that is offered is used.
const PREFER = ['MIT', 'Zlib', 'BSD-3-Clause', 'Apache-2.0', 'MPL-2.0'];
function holders(p) {
  const names = (p.authors || []).map((a) => String(a).replace(/\s*<[^>]*>\s*/g, '').trim()).filter(Boolean);
  return names.length ? names.join(', ') : 'the ' + p.name + ' developers';
}
function chosenLicences(expr) {
  const e = String(expr || '').replace(/[()]/g, ' ');
  if (/\bAND\b/.test(e)) return e.split(/\bAND\b/).map((part) => chosenLicences(part)[0]).filter(Boolean);
  const ids = e.split(/\bOR\b|\//).map((x) => x.trim().split(/\s+WITH\s+/)[0].trim()).filter(Boolean);
  const pick = PREFER.find((id) => ids.includes(id)) || ids[0];
  return pick ? [pick] : [];
}

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

function standardText(p, id) {
  const line = 'Copyright (c) ' + holders(p);
  if (id === 'MIT') return 'MIT License\n\n' + line + '\n\n' + MIT_BODY;
  if (id === 'BSD-3-Clause') return 'BSD 3-Clause License\n\n' + line + '\n\n' + BSD3_BODY;
  if (id === 'Zlib') return 'zlib License\n\n' + line + '\n\n' + ZLIB_BODY;
  return '';
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
  rows.push({ p, name: p.name, version: p.version, licence: p.license || (p.license_file ? 'see licence file' : 'not stated'),
    repo: p.repository || p.homepage || 'https://crates.io/crates/' + p.name, refs, notes: [] });
}
// Crates without a licence file: add the standard text of the licence used, with the crate's copyright line.
for (const r of rows.filter((x) => !x.refs.length)) {
  for (const id of chosenLicences(r.p.license)) {
    const text = standardText(r.p, id);
    if (text) {
      const key = createHash('sha256').update(text).digest('hex');
      if (!texts.has(key)) texts.set(key, { n: texts.size + 1, text, users: [] });
      const entry = texts.get(key);
      entry.users.push(r.name + ' ' + r.version + ' (standard ' + id + ' text; the crate ships no licence file)');
      r.refs.push(entry.n);
    } else if (FULL_TEXT[id]) {
      const full = [...texts.values()].find((t) => FULL_TEXT[id].test(t.text));
      if (full) { full.users.push(r.name + ' ' + r.version + ' (the crate ships no licence file)'); r.refs.push(full.n); }
      r.notes.push(id + ': full text at ' + OFFICIAL[id] + (id === 'MPL-2.0' ? '; the source code of this crate is available at ' + r.repo + ' and https://crates.io/crates/' + r.name : ''));
    } else {
      r.notes.push(id + ': see https://spdx.org/licenses/' + id + '.html');
    }
  }
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
    '  Licence text: ' + (r.refs.length ? r.refs.map((n) => '[' + n + ']').join(' ') : 'none shipped with the crate; see the source'));
  for (const n of r.notes) lines.push('  ' + n);
  lines.push('');
}
lines.push('== Licence texts ==', '');
for (const t of [...texts.values()].sort((a, b) => a.n - b.n)) {
  lines.push('[' + t.n + '] Used by: ' + t.users.join(', '), '', t.text, '', '-'.repeat(78), '');
}
fs.writeFileSync(OUT, lines.join('\n') + '\n');
console.log('Wrote ' + OUT + ': ' + rows.length + ' crates, ' + texts.size + ' distinct licence texts' + (rootName ? ' (' + rootName + ')' : ''));
const missing = rows.filter((r) => !r.refs.length && !r.notes.length).map((r) => r.name);
if (missing.length) console.log('Still without a licence text: ' + missing.join(', '));
const tally = {};
for (const r of rows) tally[r.licence] = (tally[r.licence] || 0) + 1;
console.log('Licences: ' + Object.entries(tally).sort((a, b) => b[1] - a[1]).map(([k, v]) => v + ' × ' + k).join('; '));

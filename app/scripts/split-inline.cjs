/* One-time, AST-checked extraction of the original single-IIFE frontend.
 * Run with Node's bundled Acorn: node --expose-internals scripts/split-inline.cjs
 * Definitions load before initialization. Initializer functions are called together
 * by bootstrap.js, retaining the original synchronous statement order and hoisting.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const acorn = require('internal/deps/acorn/acorn/dist/acorn');
const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
const htmlPath = path.join(dist, 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const style = /<style>([\s\S]*?)<\/style>/.exec(html);
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].find((m) => m[1].includes('(function ()'));
if (!style || !script) throw Error('Expected the original inline style and application IIFE; extraction is not repeatable on the split output.');
const source = script[1];
const parsed = acorn.parse(source, { ecmaVersion: 'latest' });
const outer = parsed.body[0]?.expression;
if (parsed.body.length !== 1 || outer?.type !== 'CallExpression' || outer.callee.type !== 'FunctionExpression') throw Error('Unexpected application wrapper');
const body = outer.callee.body.body;
// Git checkouts may use CRLF locally and LF in CI; source fingerprints use LF.
const hash = (s) => crypto.createHash('sha256').update(s.replace(/\r\n/g, '\n')).digest('hex');
const canonical = (v) => Array.isArray(v) ? v.map(canonical) : v && typeof v === 'object' ?
  Object.fromEntries(Object.keys(v).filter((k) => !['start', 'end', 'loc', 'raw'].includes(k)).sort().map((k) => [k, canonical(v[k])])) : v;
const astHash = (node) => hash(JSON.stringify(canonical(node)));
const functions = body.filter((n) => n.type === 'FunctionDeclaration');
const bindings = [...new Set(body.filter((n) => n.type === 'VariableDeclaration').flatMap((n) => n.declarations.map((d) => {
  if (d.id.type !== 'Identifier' || n.kind !== 'var') throw Error('Only original var identifier declarations are supported');
  return d.id.name;
})))];
const functionNames = functions.map((n) => n.id.name);
if (new Set(functionNames).size !== functionNames.length || bindings.some((n) => functionNames.includes(n))) throw Error('Duplicate declaration requires manual scope review');
const forbiddenWindowBindings = ['window', 'self', 'document', 'location', 'top', 'parent', 'frames', 'length', 'navigator', 'history', 'name', 'status', 'undefined', 'Infinity', 'NaN'];
if ([...bindings, ...functionNames].some((n) => forbiddenWindowBindings.includes(n))) throw Error('Potential Window binding conflict');

// The original application uses var. Resolve writes through function scopes so
// local names such as s/t/fmt are not mistaken for writes to the outer helpers.
function namesIn(pattern) {
  if (!pattern) return [];
  if (pattern.type === 'Identifier') return [pattern.name];
  if (pattern.type === 'RestElement') return namesIn(pattern.argument);
  if (pattern.type === 'AssignmentPattern') return namesIn(pattern.left);
  if (pattern.type === 'ArrayPattern') return pattern.elements.flatMap(namesIn);
  if (pattern.type === 'ObjectPattern') return pattern.properties.flatMap((p) => namesIn(p.value || p.argument));
  return [];
}
function functionLocals(fn) {
  const names = new Set(fn.params.flatMap(namesIn));
  if (fn.id) names.add(fn.id.name);
  function collect(n) {
    if (!n || typeof n !== 'object') return;
    if (/Function/.test(n.type)) { if (n.type === 'FunctionDeclaration') names.add(n.id.name); return; }
    if (n.type === 'VariableDeclaration') n.declarations.forEach((d) => namesIn(d.id).forEach((s) => names.add(s)));
    for (const value of Object.values(n)) if (Array.isArray(value)) value.forEach(collect); else if (value && typeof value === 'object') collect(value);
  }
  collect(fn.body);
  return names;
}
function checkScope(n, scopes = []) {
  if (!n || typeof n !== 'object') return;
  const isFunction = /Function/.test(n.type);
  const nested = isFunction ? scopes.concat(functionLocals(n)) : scopes;
  if (!scopes.length && ['ThisExpression', 'ReturnStatement'].includes(n.type)) throw Error('Initializer depends on original wrapper context');
  if (!scopes.length && n.type === 'VariableDeclaration' && !body.includes(n)) throw Error('Nested outer var requires manual hoisting');
  if (['AssignmentExpression', 'UpdateExpression'].includes(n.type)) {
    const target = n.left || n.argument;
    if (target.type === 'Identifier' && functionNames.includes(target.name) && !scopes.some((s) => s.has(target.name))) throw Error('Outer helper is reassigned: ' + target.name);
  }
  for (const value of Object.values(n)) if (Array.isArray(value)) value.forEach((v) => checkScope(v, nested)); else if (value && typeof value === 'object') checkScope(value, nested);
}
body.forEach((n) => checkScope(n));

const sections = [...source.matchAll(/^  \/\* ---------- ([^\r\n]+)/gm)].map((m) => ({ start: m.index, title: m[1] }));
const bootStart = source.indexOf("  $('#btn-refresh').addEventListener");
function sectionName(position) {
  if (position >= bootStart && bootStart >= 0) return 'startup';
  const title = sections.filter((s) => s.start <= position).at(-1)?.title || '';
  const mappings = [
    [/helpers|^data /, 'core'], [/derived values|rendering/, 'progress'], [/physics demos/, 'demo-player'],
    [/^references|^recent advances|^Live curated/, 'content'], [/Hello Super:/, 'tour'], [/Our model:/, 'model-demo'],
    [/Baselines:/, 'baseline-demos'], [/Storm in use/, 'storm-current-demo'], [/Storm:/, 'storm-demo'],
    [/Hurricane in the Hello/, 'hurricane-tour'], [/Hurricane:/, 'hurricane-demo'], [/Radar:/, 'radar-demo'],
    [/Predict Tc:/, 'prediction-demo'], [/Theory & materials: mini/, 'theory-drawings'], [/illustrations for the Nobel/, 'nobel-drawings'],
    [/classic high-Tc/, 'mechanism-drawings'], [/news illustrations/, 'news-drawings'], [/mini animations/, 'mini-player'],
    [/Theory & materials view/, 'theory-view'], [/New papers:/, 'papers-view'], [/Our models:/, 'model-cards'],
    [/Authors:/, 'authors'], [/Cite:|Write to us:|where the data/, 'citation-contact'], [/Model details/, 'model-details'],
    [/AI ×/, 'ai-view'], [/Candidate superconductors|elements: symbols/, 'candidates'], [/turning crystal/, 'crystal-viewer'],
    [/phone link/, 'phone'], [/new-version/, 'updates']
  ];
  return mappings.find(([pattern]) => pattern.test(title))?.[1] || 'core';
}
const definitionItems = [], initializerItems = [], expectedInitialization = [];
let previousEnd = outer.callee.body.start + 1;
for (const node of body) {
  const leading = source.slice(previousEnd, node.start);
  previousEnd = node.end;
  if (node.type === 'ExpressionStatement' && node.directive === 'use strict') continue;
  const group = sectionName(node.start);
  if (node.type === 'FunctionDeclaration') {
    definitionItems.push({ group, code: leading + 'const ' + node.id.name + ' = ' + source.slice(node.start, node.end) + ';' });
    continue;
  }
  let code = source.slice(node.start, node.end);
  if (node.type === 'VariableDeclaration') code = node.declarations.filter((d) => d.init)
    .map((d) => d.id.name + ' = ' + source.slice(d.init.start, d.init.end) + ';').join('\n  ');
  if (!code) continue;
  initializerItems.push({ group, code: leading + code });
  expectedInitialization.push(...acorn.parse(code, { ecmaVersion: 'latest' }).body.map(astHash));
}
function parts(items, kind) {
  const chunks = [], counts = new Map();
  let current;
  for (const item of items) {
    if (!current || current.group !== item.group || Buffer.byteLength(current.code + item.code) > 68000) {
      const number = (counts.get(item.group) || 0) + 1;
      counts.set(item.group, number);
      current = { group: item.group, stem: item.group + (number > 1 ? '-' + number : ''), code: '' };
      chunks.push(current);
    }
    current.code += item.code + '\n';
  }
  return chunks.map((chunk) => {
    const file = 'js/' + kind + '/' + chunk.stem + '.js';
    const initialize = 'initializeSupercon' + chunk.stem.split('-').map((s) => s[0].toUpperCase() + s.slice(1)).join('');
    const header = "'use strict';\n// " + chunk.group + ': ' + (kind === 'definitions' ? 'shared lexical function definitions; no startup side effects.' : 'original initialization order; invoked synchronously by bootstrap.js.') + '\n';
    const code = header + (kind === 'definitions' ? chunk.code : 'const ' + initialize + ' = function ' + initialize + '() {\n' + chunk.code + '\n};\n');
    return { file, code, initialize };
  });
}
const definitions = parts(definitionItems, 'definitions');
const initializers = parts(initializerItems, 'initialize');
const bindingFile = { file: 'js/bindings.js', code: "'use strict';\n// Shared lexical state. As in the original IIFE, every var exists before any initializer runs.\nlet " + bindings.join(',\n  ') + ';\n' };
const bootstrapFile = { file: 'js/bootstrap.js', code: "'use strict';\n// All definitions and initializer functions are now loaded. Run startup in one\n// synchronous stack, so timers and events cannot interleave between resources.\n" + initializers.map((c) => c.initialize + '();').join('\n') + '\n' };
const files = [bindingFile, ...definitions, ...initializers, bootstrapFile];
const assetManifest = { styles: ['styles.css'], scripts: ['candidates.js', ...files.map((f) => f.file)] };
const sourceManifest = {
  source: 'The complete inline index.html immediately before resource extraction',
  source_hash_line_endings: 'LF',
  original_html_sha256: hash(html), original_script_sha256: hash(source), css_sha256: hash(style[1]),
  scope_checks: { top_level_this: false, top_level_return: false, nested_outer_var: false, reassigned_outer_function: false },
  bindings, functions: Object.fromEntries(functions.map((n) => [n.id.name, astHash({ ...n, type: 'FunctionExpression' })])),
  initialization: expectedInitialization, scripts: assetManifest.scripts
};
for (const f of files) {
  if (Buffer.byteLength(f.code) > 70000) throw Error('Reviewable resource limit exceeded: ' + f.file);
  acorn.parse(f.code, { ecmaVersion: 'latest' });
}
for (const f of files) { const target = path.join(dist, f.file); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, f.code); }
fs.writeFileSync(path.join(dist, 'styles.css'), style[1]);
fs.writeFileSync(path.join(dist, 'assets.json'), JSON.stringify(assetManifest, null, 2) + '\n');
fs.writeFileSync(path.join(__dirname, 'inline-source-manifest.json'), JSON.stringify(sourceManifest, null, 2) + '\n');
const references = assetManifest.scripts.map((file) => '<script src="' + file + '"></script>').join('\n');
const nextHtml = html.replace(style[0], '<link rel="stylesheet" href="styles.css">')
  .replace('<script src="candidates.js"></script>', '').replace(script[0], references);
if (Buffer.byteLength(nextHtml) > 70000) throw Error('HTML shell exceeds resource limit');
fs.writeFileSync(htmlPath, nextHtml);
console.log(JSON.stringify({ definitions: definitions.length, initializers: initializers.length, functions: functions.length,
  initializer_statements: expectedInitialization.length, resources: files.length + 2,
  max_resource_bytes: Math.max(...files.map((f) => Buffer.byteLength(f.code)), Buffer.byteLength(style[1])) }, null, 2));

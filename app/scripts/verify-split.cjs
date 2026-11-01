/* Verify the reviewed frontend resources without installing parser packages.
 * Node 22 (the app's CI version) includes Acorn behind --expose-internals.
 * The manifest retains original extraction provenance and a complete reviewed AST
 * baseline. Intentional revisions are recorded explicitly; current functions are
 * not claimed to remain identical to the historical inline implementation.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const vm = require('node:vm');
const acorn = require('internal/deps/acorn/acorn/dist/acorn');
const app = path.resolve(__dirname, '..');
const dist = path.join(app, 'dist');
const html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8');
const assets = JSON.parse(fs.readFileSync(path.join(dist, 'assets.json'), 'utf8'));
const baseline = JSON.parse(fs.readFileSync(path.join(__dirname, 'inline-source-manifest.json'), 'utf8'));
// Compare source contents consistently across Windows CRLF and Linux LF checkouts.
const hash = (s) => crypto.createHash('sha256').update(s.replace(/\r\n/g, '\n')).digest('hex');
const canonical = (v) => Array.isArray(v) ? v.map(canonical) : v && typeof v === 'object' ?
  Object.fromEntries(Object.keys(v).filter((k) => !['start', 'end', 'loc', 'raw'].includes(k)).sort().map((k) => [k, canonical(v[k])])) : v;
const astHash = (node) => hash(JSON.stringify(canonical(node)));
const isDirective = (n) => n.type === 'ExpressionStatement' && n.directive === 'use strict';
const codeOf = (file) => fs.readFileSync(path.join(dist, file), 'utf8');
const parse = (code) => acorn.parse(code, { ecmaVersion: 'latest' });
const scripts = [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/g)].map((m) => m[1]);
const styles = [...html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g)].map((m) => m[1]);
assert.deepEqual(scripts, assets.scripts, 'HTML script order must match the complete asset manifest');
assert.deepEqual(scripts, baseline.scripts, 'Reviewed load order must remain exact');
assert.deepEqual(styles, assets.styles);
assert.equal(/<style\b/.test(html), false, 'Styles belong in the stylesheet');
for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
  if (!match[1].includes('src=') && !match[1].includes('application/json')) assert.equal(match[2].trim(), '', 'No inline executable fragments');
}
for (const file of [...assets.scripts, ...assets.styles, 'index.html', 'assets.json']) {
  assert.equal(path.isAbsolute(file) || file.split('/').includes('..'), false, 'Local resource path: ' + file);
  assert.ok(fs.existsSync(path.join(dist, file)), 'Referenced resource exists: ' + file);
  assert.ok(fs.statSync(path.join(dist, file)).size <= 70000, 'Complete resource stays below 70 KB: ' + file);
}
assert.equal(hash(codeOf('styles.css')), baseline.css_sha256, 'Complete stylesheet matches its reviewed baseline after LF normalization');
const allCode = scripts.map(codeOf);
for (let i = 0; i < scripts.length; i++) { parse(allCode[i]); new vm.Script(allCode[i], { filename: scripts[i] }); }
parse(allCode.join('\n'));
new vm.Script(allCode.join('\n'), { filename: 'all-scripts-in-html-order.js' });

const functions = {}, initializers = [], initialization = [];
const definitionsEnd = scripts.findIndex((file) => file.startsWith('js/initialize/'));
const bootstrapIndex = scripts.indexOf('js/bootstrap.js');
assert.ok(definitionsEnd > 1 && bootstrapIndex === scripts.length - 1, 'Bootstrap is last');
for (let i = 0; i < scripts.length; i++) {
  const file = scripts[i];
  if (!file.startsWith('js/definitions/') && !file.startsWith('js/initialize/')) continue;
  const nodes = parse(allCode[i]).body;
  assert.ok(isDirective(nodes[0]), 'Every resource retains strict mode: ' + file);
  for (const node of nodes.slice(1)) {
    assert.equal(node.type, 'VariableDeclaration');
    assert.equal(node.kind, 'const');
    for (const d of node.declarations) {
      assert.equal(d.init.type, 'FunctionExpression', 'Resource loading only creates functions');
      assert.equal(d.id.name, d.init.id.name, 'Named functions retain their names');
      if (file.startsWith('js/definitions/')) {
        assert.ok(i < definitionsEnd, 'All definitions precede every initializer resource');
        assert.equal(functions[d.id.name], undefined, 'No duplicate shared function binding');
        functions[d.id.name] = astHash(d.init);
      } else {
        assert.ok(i < bootstrapIndex);
        initializers.push(d.id.name);
        initialization.push(...d.init.body.body.map(astHash));
      }
    }
  }
}
assert.deepEqual(functions, baseline.functions, 'Every function body, parameter and expression matches the reviewed AST baseline');
assert.deepEqual(initialization, baseline.initialization, 'Every initialization statement retains its reviewed AST and order');
const referenceFlag = process.argv.indexOf('--reference');
if (referenceFlag >= 0) {
  const referenceHtml = fs.readFileSync(process.argv[referenceFlag + 1], 'utf8');
  assert.equal(hash(referenceHtml), baseline.original_html_sha256, 'Reference is the original complete HTML snapshot');
  if (baseline.original_css_sha256) {
    const referenceStyles = [...referenceHtml.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)];
    assert.equal(referenceStyles.length, 1, 'Original snapshot has one complete stylesheet');
    assert.equal(hash(referenceStyles[0][1]), baseline.original_css_sha256, 'Independent original stylesheet provenance');
  }
  const referenceScript = [...referenceHtml.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .find((m) => m[1].includes('(function ()'))?.[1];
  assert.equal(hash(referenceScript), baseline.original_script_sha256, 'Reference retains the original complete script snapshot');
  const originalBody = parse(referenceScript).body[0].expression.callee.body.body;
  const originalFunctions = Object.fromEntries(originalBody.filter((n) => n.type === 'FunctionDeclaration')
    .map((n) => [n.id.name, astHash({ ...n, type: 'FunctionExpression' })]));
  const originalInitialization = originalBody.filter((n) => n.type !== 'FunctionDeclaration' && !isDirective(n)).flatMap((n) => {
    if (n.type !== 'VariableDeclaration') return [astHash(n)];
    return n.declarations.filter((d) => d.init).flatMap((d) =>
      parse(d.id.name + ' = ' + referenceScript.slice(d.init.start, d.init.end) + ';').body.map(astHash));
  });
  if (baseline.reviewed_revision) {
    assert.equal(astHash(originalFunctions), baseline.original_ast_sha256.functions, 'Independent original full-source function AST provenance');
    assert.equal(astHash(originalInitialization), baseline.original_ast_sha256.initialization, 'Independent original full-source initialization AST provenance');
  } else {
    assert.deepEqual(functions, originalFunctions, 'Independent full-source function AST comparison');
    assert.deepEqual(initialization, originalInitialization, 'Independent full-source initialization AST comparison');
  }
}
const bindingNodes = parse(codeOf('js/bindings.js')).body;
assert.ok(isDirective(bindingNodes[0]));
assert.equal(bindingNodes[1].kind, 'let');
assert.deepEqual(bindingNodes[1].declarations.map((d) => { assert.equal(d.init, null); return d.id.name; }), baseline.bindings);
const boot = parse(codeOf('js/bootstrap.js')).body;
assert.ok(isDirective(boot[0]));
assert.deepEqual(boot.slice(1).map((n) => {
  assert.equal(n.type, 'ExpressionStatement'); assert.equal(n.expression.type, 'CallExpression');
  assert.equal(n.expression.callee.type, 'Identifier'); assert.equal(n.expression.arguments.length, 0);
  return n.expression.callee.name;
}), initializers, 'All initializers run together in reviewed order, with no resource-load timing gaps');
for (const file of ['inline-source-manifest.json', 'split-inline.cjs', 'verify-split.cjs']) {
  assert.ok(fs.statSync(path.join(__dirname, file)).size <= 70000, 'Complete review metadata/tool stays below 70 KB: ' + file);
}

// Run declarations in separate classic-script contexts, as the browser does.
// No initializer is called here: this must not require a DOM, timers or fetch.
const sandbox = vm.createContext({});
for (let i = 0; i < bootstrapIndex; i++) vm.runInContext(allCode[i], sandbox, { filename: scripts[i] });
for (const name of [...baseline.bindings, ...Object.keys(functions), ...initializers]) {
  assert.equal(Object.hasOwn(sandbox, name), false, 'Shared lexical binding must not overwrite a Window property: ' + name);
}
console.log(JSON.stringify({ scripts: scripts.length, functions: Object.keys(functions).length, initializationStatements: initialization.length,
  maximumResourceBytes: Math.max(...assets.scripts.concat(assets.styles).map((file) => fs.statSync(path.join(dist, file)).size)),
  astEquivalent: true, astComparison: 'reviewed-baseline', intentionalRevisionsRecorded: !!baseline.reviewed_revision }));

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const app = fileURLToPath(new URL('../app/', import.meta.url));
const hash = text => crypto.createHash('sha256').update(text.replace(/\r\n/g, '\n')).digest('hex');
function reviewedCopy(run) {
  const base = fs.realpathSync(os.tmpdir());
  const directory = fs.mkdtempSync(path.join(base, 'supercon-review-history-'));
  const assets = JSON.parse(fs.readFileSync(path.join(app, 'dist/assets.json'), 'utf8'));
  const baseline = JSON.parse(fs.readFileSync(path.join(app, 'scripts/inline-source-manifest.json'), 'utf8'));
  const files = ['dist/index.html', 'dist/assets.json', ...assets.scripts.map(file => 'dist/' + file),
    ...assets.styles.map(file => 'dist/' + file), 'scripts/inline-source-manifest.json', 'scripts/verify-split.cjs', 'scripts/split-inline.cjs',
    ...baseline.reviewed_revision_history_files.map(entry => 'scripts/' + entry.path)];
  try {
    for (const file of files) {
      assert.equal(path.isAbsolute(file) || file.split('/').includes('..'), false);
      fs.mkdirSync(path.dirname(path.join(directory, file)), {recursive: true});
      fs.copyFileSync(path.join(app, file), path.join(directory, file));
    }
    const saveBaseline = () => fs.writeFileSync(path.join(directory, 'scripts/inline-source-manifest.json'), JSON.stringify(baseline, null, 2) + '\n');
    const verify = () => spawnSync(process.execPath, ['--expose-internals', path.join(directory, 'scripts/verify-split.cjs')], {encoding: 'utf8'});
    run({directory, baseline, saveBaseline, verify});
  } finally {
    const resolved = fs.realpathSync(directory);
    assert.ok(resolved.startsWith(base + path.sep) && path.basename(resolved).startsWith('supercon-review-history-'));
    fs.rmSync(resolved, {recursive: true, force: true});
  }
}

test('external review history keeps the original provenance and all thirty-one published prior revisions', () => {
  const baseline = JSON.parse(fs.readFileSync(path.join(app, 'scripts/inline-source-manifest.json'), 'utf8'));
  const entries = baseline.reviewed_revision_history_files;
  assert.equal(entries.length, 27);
  const revisions = entries.flatMap(entry => {
    const historyText = fs.readFileSync(path.join(app, 'scripts', entry.path), 'utf8');
    assert.equal(hash(historyText), entry.sha256);
    const history = JSON.parse(historyText);
    assert.equal(history.revisions.length, entry.count);
    return history.revisions;
  });
  assert.equal(revisions.length, 31);
  assert.equal(baseline.reviewed_revision_count, 32);
  assert.equal(baseline.reviewed_revision_history, undefined, 'History has one unambiguous order');
  assert.equal(baseline.original_html_sha256, 'a9126c038c44c5babd60aa94a002525040e4db5a636a89cd725199616197d93b');
  assert.equal(baseline.original_script_sha256, '79fde250a59921ecf98ec98503fd7e8ff4ca55e949a48d03cd44ea81128c523b');
  assert.equal(baseline.original_css_sha256, '62e4f2aa68a5a89947192c001d57572d0ffd73087b1cf6a1db2abd6525684441');
  for (const revision of revisions) {
    assert.ok(revision.controls_preserved.includes('original snapshot provenance'));
    assert.ok(revision.controls_preserved.includes('complete function and initializer AST comparison'));
  }
});

test('verifier rejects changed historical bytes even when their JSON meaning is unchanged', () => reviewedCopy(({directory, baseline, verify}) => {
  fs.appendFileSync(path.join(directory, 'scripts', baseline.reviewed_revision_history_files[0].path), ' ');
  const result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Complete review history content hash/);
}));

test('verifier fails if a required history file is missing', () => reviewedCopy(({directory, baseline, verify}) => {
  fs.unlinkSync(path.join(directory, 'scripts', baseline.reviewed_revision_history_files[0].path));
  const result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /ENOENT/);
}));

test('verifier rejects dropped history records even when the edited file has a matching digest', () => reviewedCopy(({directory, baseline, saveBaseline, verify}) => {
  const entry = baseline.reviewed_revision_history_files[0];
  const file = path.join(directory, 'scripts', entry.path);
  const history = JSON.parse(fs.readFileSync(file, 'utf8'));
  history.revisions.pop();
  const text = JSON.stringify(history, null, 2) + '\n';
  fs.writeFileSync(file, text);
  entry.sha256 = hash(text);
  saveBaseline();
  let result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Every historical revision is retained/);
  entry.count--;
  saveBaseline();
  result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Complete reviewed revision count/);
}));

test('verifier rejects external, duplicate and ambiguous review history descriptors', () => reviewedCopy(({baseline, saveBaseline, verify}) => {
  const original = structuredClone(baseline.reviewed_revision_history_files);
  for (const filename of ['../review-history-01.json', 'C:/review-history-01.json']) {
    baseline.reviewed_revision_history_files = [{...original[0], path: filename}];
    saveBaseline();
    const result = verify();
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Review history must use a local, dedicated filename/);
  }
  baseline.reviewed_revision_history_files = [...original, ...original];
  saveBaseline();
  let result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /No duplicate review history file/);
  baseline.reviewed_revision_history_files = original;
  baseline.reviewed_revision_history = [baseline.reviewed_revision];
  saveBaseline();
  result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Do not mix inline and external review histories/);
}));

test('additional authentication implementation is reviewed while public endpoint configuration stays configurable', () => reviewedCopy(({directory, verify}) => {
  const config = path.join(directory, 'dist/team-auth-config.js');
  fs.writeFileSync(config, "'use strict';\nglobalThis.SuperconTeamConfig = Object.freeze({apiBase: 'https://configured.example.org'});\n");
  let result = verify();
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.equal(JSON.parse(result.stdout).reviewedRevisionCount, 32);
  fs.appendFileSync(path.join(directory, 'dist/team-auth.js'), '\n// unreviewed implementation edit\n');
  result = verify();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Complete additional source matches its reviewed baseline: team-auth.js/);
}));

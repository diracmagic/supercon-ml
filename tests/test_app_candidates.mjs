import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import path from 'node:path';
import candidates from '../app/dist/candidates.js';

const rows = [
  { id: 'in', formula: 'NbB2', novelty: 0.8, outside: false },
  { id: 'out', formula: 'TaC', novelty: 1.2, outside: true },
  { id: 'unknown', formula: 'BaCa2', outside: false },
  { id: 'both', formula: 'MoBC', novelty: 0.4 },
];
const ids = (xs) => xs.map(candidates.id);

const reviewedEarlierCandidate = () => ({ id: 'JVASP-reviewed', formula: 'NbB2', tc: 8, tc_sc: 12, novelty: .5,
  prediction_provenance: { candidate_id: 'JVASP-reviewed', reviewed: true, frozen_at: '2026-10-30',
    url: 'https://example.org/frozen-prediction.json', cite: 'Frozen prediction record' },
  prior_superconductivity: { candidate_id: 'JVASP-reviewed', reviewed: true, kind: 'experiment', superconducts: true,
    published_at: '2024-03-01', doi: '10.1234/measured', cite: 'Reviewed experimental report',
    locator: 'Results, Figure 2', sample_context: 'Reviewed single phase bulk specimen',
    identity_match: { composition: true, structure: true, phase: true, pressure: true, doping: true, sample_form: true } } });

test('predicted-Tc ordering is stable, keeps unknowns last and does not alter predictions or fold ranges', () => {
  const input = [{ id: 'unknown', tc: null }, { id: 'joint-first', tc: 10, tc_sc: 3, p_sc: .9, p_lo: .8, p_hi: .95 },
    { id: 'conditional-first', tc: 2, tc_sc: 30, p_sc: .05, p_lo: .02, p_hi: .08 }, { id: 'tie', tc: 2 },
    { id: 'nan', tc: NaN }, { id: 'zero', tc: 0 }, { id: 'text', tc: '1000' }];
  const original = structuredClone(input);
  assert.deepEqual(ids(candidates.sortByPredictedTc(input, 'storm')), ['joint-first', 'conditional-first', 'tie', 'zero', 'unknown', 'nan', 'text']);
  assert.deepEqual(ids(candidates.sortByPredictedTc(input, 'hurricane')), ['conditional-first', 'joint-first', 'unknown', 'tie', 'nan', 'zero', 'text']);
  assert.deepEqual(input, original);
  assert.equal(candidates.sortByPredictedTc(input, 'hurricane')[0], input[2], 'Rows and reported uncertainty are retained, not reconstructed');
});

test('Hurricane missing conditional Tc stays unknown instead of relabelling its joint prediction', () => {
  const missing = { id: 'joint-only', formula: 'NbB2', tc: 10, p_sc: .2, tc_sc: null };
  const conditional = { id: 'conditional', formula: 'TaC', tc: .1, p_sc: .2, tc_sc: .5 };
  assert.equal(candidates.predictedTc(missing, 'hurricane'), null);
  assert.equal(candidates.predictedTc({ ...missing, tc_sc: undefined }, 'hurricane'), null);
  assert.equal(candidates.predictedTc({ ...missing, tc_sc: NaN }, 'hurricane'), null);
  assert.equal(candidates.predictedTc({ ...missing, tc_sc: '50' }, 'hurricane'), null);
  assert.equal(candidates.predictedTc({ ...missing, tc_sc: 0 }, 'hurricane'), 0);
  assert.equal(candidates.predictedTc(missing, 'storm'), 10);
  assert.deepEqual(ids(candidates.sortByPredictedTc([missing, conditional], 'hurricane')), ['conditional', 'joint-only']);
  const source = fs.readFileSync(new URL('../app/dist/js/definitions/candidates.js', import.meta.url), 'utf8');
  const context = { candidateData: candidates };
  vm.runInNewContext(source + '\nglobalThis.temperature = { candTcSc, candK, renderCandidates, candViewer };', context);
  assert.equal(context.temperature.candTcSc(missing), null);
  assert.equal(context.temperature.candK(context.temperature.candTcSc(missing)), '—');
  assert.match(context.temperature.renderCandidates.toString(), /var tc = hur \? candTcSc\(c\) : c\.tc/);
  assert.match(context.temperature.candViewer.toString(), /candK\(candTcSc\(c\)\)/);
  assert.equal(missing.tc, 10, 'The original joint prediction remains unchanged');
});

test('only a sourced, reviewed exact experimental positive predating the frozen prediction enters the archive', () => {
  const confirmed = reviewedEarlierCandidate();
  assert.equal(candidates.earlierReport(confirmed).status, 'confirmed');
  const negatives = [false, null].map(value => ({ ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, superconducts: value } }));
  const unresolved = [
    { ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, kind: 'dft' } },
    { ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, candidate_id: 'other' } },
    { ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, reviewed: false } },
    { ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, doi: '', url: 'javascript:alert(1)' } },
    { ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, locator: '' } },
    { ...confirmed, prediction_provenance: undefined, listed: { date: '2026-10-30' } },
    { ...confirmed, prediction_provenance: { ...confirmed.prediction_provenance, reviewed: false } },
    { ...confirmed, prediction_provenance: { ...confirmed.prediction_provenance, candidate_id: 'other' } },
    ...['2026-10-30', '2026-10-31', '2024', '2024-02-30', '2024-03-01T24:00:00Z'].map(published_at =>
      ({ ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity, published_at } })),
    ...['composition', 'structure', 'phase', 'pressure', 'doping', 'sample_form'].map(key =>
      ({ ...confirmed, prior_superconductivity: { ...confirmed.prior_superconductivity,
        identity_match: { ...confirmed.prior_superconductivity.identity_match, [key]: null } } })),
    { id: 'formula-only', formula: confirmed.formula, prior: true, supercon: 'same formula',
      literature_audit: { status: 'reported-superconducting' }, check: { kind: 'experiment', superconducts: true, tc: 8, doi: '10.1234/measured' } },
  ];
  for (const candidate of [...negatives, ...unresolved]) assert.equal(candidates.earlierReport(candidate).status, 'unknown');
  const before = structuredClone(confirmed);
  const split = candidates.partitionCandidates([confirmed, ...negatives, ...unresolved], 'storm');
  assert.deepEqual(split.reported, [confirmed]);
  assert.equal(split.rows.length, negatives.length + unresolved.length);
  assert.equal(split.hidden, 1);
  assert.deepEqual(confirmed, before);
  assert.match(candidates.priorReportLines(confirmed).join(' '), /before the frozen prediction/);
});

test('exact-ID audit metadata can provide a reviewed report but formula/structure-only statuses cannot', () => {
  const previous = globalThis.SuperconLiterature;
  const c = reviewedEarlierCandidate(), evidence = c.prior_superconductivity;
  delete c.prior_superconductivity;
  try {
    globalThis.SuperconLiterature = { by_id: { [c.id]: { status: 'reported-superconducting', prior_superconductivity: evidence } } };
    assert.equal(candidates.earlierReport(c).status, 'confirmed');
    assert.equal(candidates.earlierReport({ ...c, id: 'other' }).status, 'unknown');
    globalThis.SuperconLiterature.by_id[c.id] = { status: 'structure-only', sources: [{ url: 'https://doi.org/10.1234/measured' }] };
    assert.equal(candidates.earlierReport(c).status, 'unknown');
  } finally { globalThis.SuperconLiterature = previous; }
});

test('candidate views sort within all four Storm groups and retain unresolved prior flags and unknown Tc', () => {
  const context = { candidateData: candidates, list: value => Array.isArray(value) ? value : [], candState: { track: 'borides', archive: false },
    AI_FOUND: [{ h: 'NbB2 superconductor' }], AI_WATCH: [], RECENT: [] };
  const source = fs.readFileSync(new URL('../app/dist/js/definitions/candidates.js', import.meta.url), 'utf8');
  vm.runInNewContext(source + '\nglobalThis.views = { candRows, candCurrentRows };', context);
  const reported = reviewedEarlierCandidate();
  const unresolved = [{ id: 'B-high', formula: 'NbB2', tc: 20, prior: true, novelty: .2 },
    { id: 'C-low', formula: 'TaC', tc: 3, supercon: 'formula-only record', outside: true },
    { id: 'BC-unknown', formula: 'MoBC', tc: null, outside: true }];
  const screen = { candidates: [reported, ...unresolved], hurricane: { candidates: [{ ...unresolved[0], tc_sc: 40 }, ...unresolved.slice(1)] },
    tracks: { storm_in_domain: ['JVASP-reviewed', 'B-high'], storm_exploration: ['BC-unknown', 'C-low'],
      borides: ['BC-unknown', 'JVASP-reviewed', 'B-high'], carbides: ['BC-unknown', 'C-low'] } };
  assert.deepEqual(ids(context.views.candRows(screen, 'storm').rows), ['B-high', 'C-low', 'BC-unknown']);
  for (const [track, expected] of [['storm_in_domain', ['B-high']], ['storm_exploration', ['C-low', 'BC-unknown']],
    ['borides', ['B-high', 'BC-unknown']], ['carbides', ['C-low', 'BC-unknown']]]) {
    context.candState.track = track;
    assert.deepEqual(ids(context.views.candCurrentRows(screen, 'storm').rows), expected);
  }
  context.candState.archive = true;
  context.candState.track = 'borides';
  assert.deepEqual(ids(context.views.candCurrentRows(screen, 'storm').rows), [reported.id]);
  context.candState.archive = false;
  assert.deepEqual(ids(context.views.candCurrentRows(screen, 'hurricane').rows), ['B-high', 'C-low', 'BC-unknown']);
});

test('current source audit confirms zero exact earlier positives and keeps conditional negatives and unknowns', () => {
  const audit = JSON.parse(fs.readFileSync(new URL('../data/candidate_literature_audit.json', import.meta.url), 'utf8'));
  assert.equal(audit.summary.exact_candidate_intrinsic_superconductors_confirmed, 0);
  const checks = JSON.parse(fs.readFileSync(new URL('../data/checks.json', import.meta.url), 'utf8')).materials;
  const inputs = checks.map((check, i) => ({ id: 'check-' + i, formula: check.formula, check, tc: i }));
  assert.equal(candidates.partitionCandidates(inputs, 'hurricane').reported.length, 0);
  assert.equal(candidates.partitionCandidates(inputs, 'hurricane').rows.length, checks.length);
  const negative = candidates.checkEvidenceLines(checks.find(check => check.formula === 'YbRhIn5')).join(' ');
  assert.match(negative, /Three-unit-cell/);
  assert.match(negative, /pressure: unspecified here/);
  assert.match(negative, /negative result applies only to the measured sample and conditions/);
  const ce = candidates.checkEvidenceLines(checks.find(check => check.formula === 'Ce2NiGa12')).join(' ');
  assert.match(ce, /minimum temperature \(K\): 0.35/);
  assert.match(ce, /resistivity\/magnetoresistance; minimum temperature \(K\): unknown/);
});

test('split frontend retains initialization order, function ASTs, references and reviewable resource sizes', () => {
  const script = new URL('../app/scripts/verify-split.cjs', import.meta.url);
  const result = spawnSync(process.execPath, ['--expose-internals', fileURLToPath(script)], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.equal(JSON.parse(result.stdout.trim()).astEquivalent, true);
});

test('a real LF-only checkout copy passes the same frontend verifier', () => {
  const app = fileURLToPath(new URL('../app/', import.meta.url));
  const temporaryBase = fs.realpathSync(os.tmpdir());
  const temporary = fs.mkdtempSync(path.join(temporaryBase, 'supercon-frontend-lf-'));
  try {
    const assets = JSON.parse(fs.readFileSync(path.join(app, 'dist/assets.json'), 'utf8'));
    const baseline = JSON.parse(fs.readFileSync(path.join(app, 'scripts/inline-source-manifest.json'), 'utf8'));
    const files = ['dist/index.html', 'dist/assets.json', ...assets.scripts.map((f) => 'dist/' + f),
      ...assets.styles.map((f) => 'dist/' + f), 'scripts/verify-split.cjs', 'scripts/split-inline.cjs', 'scripts/inline-source-manifest.json',
      ...(baseline.reviewed_revision_history_files || []).map((entry) => 'scripts/' + entry.path)];
    for (const file of files) {
      assert.equal(path.isAbsolute(file) || file.split('/').includes('..'), false);
      const destination = path.join(temporary, file);
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      const source = fs.readFileSync(path.join(app, file), 'utf8').replace(/\r\n/g, '\n');
      assert.equal(source.includes('\r\n'), false);
      fs.writeFileSync(destination, source);
    }
    const result = spawnSync(process.execPath, ['--expose-internals', path.join(temporary, 'scripts/verify-split.cjs')], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr || result.stdout);
    const verified = JSON.parse(result.stdout.trim());
    assert.equal(verified.astEquivalent, true);
    assert.equal(verified.reviewedRevisionCount, baseline.reviewed_revision_count);
    assert.equal(verified.verifiedHistoryFiles, baseline.reviewed_revision_history_files.length);
  } finally {
    const resolved = fs.realpathSync(temporary);
    assert.ok(resolved.startsWith(temporaryBase + path.sep) && path.basename(resolved).startsWith('supercon-frontend-lf-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('old candidate data separates established domain coverage from exploration', () => {
  assert.deepEqual(ids(candidates.trackRows(rows, null, 'storm_in_domain')), ['in', 'both']);
  assert.deepEqual(ids(candidates.trackRows(rows, null, 'storm_exploration')), ['out', 'unknown']);
});

test('chemical subrankings match element symbols, not Ba or Ca substrings', () => {
  assert.deepEqual(ids(candidates.trackRows(rows, null, 'borides')), ['in', 'both']);
  assert.deepEqual(ids(candidates.trackRows(rows, null, 'carbides')), ['out', 'both']);
});

test('published tracks preserve their ranking, omit unavailable rows and deduplicate ids', () => {
  const tracks = { borides: ['both', 'missing', 'in', 'both'], carbides: [] };
  assert.deepEqual(ids(candidates.trackRows(rows, tracks, 'borides')), ['both', 'in']);
  assert.deepEqual(candidates.trackRows(rows, tracks, 'carbides'), []);
});

test('candidate links choose a published subranking when the domain top list omits the candidate', () => {
  const tracks = { storm_in_domain: ['in'], storm_exploration: ['out'], borides: ['both'], carbides: [] };
  assert.equal(candidates.trackForId(rows, tracks, 'both', 'storm_in_domain'), 'borides');
  assert.equal(candidates.trackForId(rows, tracks, 'out', 'storm_in_domain'), 'storm_exploration');
});

test('negative literature checks describe the reported temperature and conditions', () => {
  assert.match(candidates.checkText({ kind: 'experiment', superconducts: false, below: 0.02 }), /no superconducting transition reported down to 0.02 K/);
  assert.match(candidates.checkText({ kind: 'experiment', superconducts: false }), /under the studied conditions/);
  assert.doesNotMatch(candidates.checkText({ kind: 'experiment', superconducts: false }), /not superconducting|never/);
});

test('reviewed check corrections match the exact candidate and original paper without mutating old results', () => {
  const previous = globalThis.SuperconLiterature;
  const original = { kind: 'experiment', superconducts: false, below: .35, doi: '10.1021/cm801693t' };
  const reviewed = { kind: 'experiment', superconducts: null, doi: original.doi, note: 'Heat capacity measured to 0.35 K; superconductivity outcome unknown.' };
  try {
    globalThis.SuperconLiterature = { by_id: { 'JVASP-165558': { status: 'structure-only',
      check_correction: { replaces_doi: original.doi, check: reviewed } } } };
    assert.equal(candidates.checkFor({ id: 'JVASP-165558', check: original }), reviewed);
    assert.equal(candidates.checkFor({ id: 'JVASP-165558', check: original, literature_audit: { status: 'needs-full-text' } }), reviewed);
    assert.equal(original.superconducts, false, 'The downloaded scientific result stays unchanged');
    assert.equal(candidates.checkFor({ id: 'JVASP-1655580', check: original }), original);
    assert.equal(candidates.checkFor({ formula: 'JVASP-165558', check: original }), original);
    assert.equal(candidates.checkFor({ id: 'JVASP-165558' }), undefined, 'An audit must not manufacture a matching experiment');
    const anotherPaper = { ...original, doi: '10.1234/another-paper' };
    assert.equal(candidates.checkFor({ id: 'JVASP-165558', check: anotherPaper }), anotherPaper);
    for (const check of [{ ...reviewed, kind: 'dft' }, { ...reviewed, doi: '10.1234/another-paper' }]) {
      assert.equal(candidates.checkFor({ id: 'JVASP-165558', check: original, literature_audit: { status: 'structure-only',
        check_correction: { replaces_doi: original.doi, check } } }), original);
    }
    assert.match(candidates.checkText(reviewed), /superconductivity outcome unknown/);
    assert.doesNotMatch(candidates.checkText(reviewed), /no superconducting transition|reported down to/);
  } finally { globalThis.SuperconLiterature = previous; }
});

test('published Ce corrections remove obsolete exclusions from table, remarks and experiment-worthiness logic', () => {
  const previous = globalThis.SuperconLiterature;
  const source = fs.readFileSync(new URL('../app/dist/js/definitions/candidates.js', import.meta.url), 'utf8');
  const makeElement = (tag, attrs, ...children) => ({ tag, attrs: attrs || {}, children });
  const context = { candidateData: candidates, CHECK_LABEL: { experiment: 'Measured' }, candNum: Number.isFinite,
    MCMILLAN_K: 40, WORTH_P: .5, WORTH_HULL: .05, candRange: () => '', candPct: String,
    cText: (s, n) => String(s).slice(0, n), h: makeElement, richText: (el, text) => ({ ...el, text }) };
  try {
    const table = {};
    vm.runInNewContext(fs.readFileSync(new URL('../app/dist/literature-audit.js', import.meta.url), 'utf8'), table);
    globalThis.SuperconLiterature = table.SuperconLiterature;
    vm.runInNewContext(source + '\nglobalThis.reviewedRules = { candChecked, candWorthTests, candRemarks, candCheck };', context);
    const checks = JSON.parse(fs.readFileSync(new URL('../data/checks.json', import.meta.url), 'utf8')).materials;
    for (const [id, formula] of [['JVASP-165558', 'Ce2CuGa12'], ['JVASP-165420', 'Ce2NiGa12']]) {
      const c = { id, check: { kind: 'experiment', superconducts: false, below: .35, doi: '10.1021/cm801693t' } };
      const corrected = context.reviewedRules.candChecked(c);
      const authoritative = checks.find(check => check.formula === formula);
      assert.equal(corrected.superconducts, null);
      assert.equal(corrected.below, undefined);
      assert.equal(corrected.note, authoritative.note, 'The displayed interpretation matches reviewed source data');
      assert.equal(context.reviewedRules.candWorthTests(c, true).settled, false);
      const remarks = context.reviewedRules.candRemarks(c, true, null).map(row => typeof row[1] === 'string' ? row[1] : '').join(' ');
      assert.match(remarks, /superconductivity outcome unknown/);
      assert.doesNotMatch(remarks, /no superconducting transition reported down to 0\.35|no superconducting transition is reported in that range/);
      const rendered = context.reviewedRules.candCheck(c);
      const span = rendered.tag === 'a' ? rendered.children[0] : rendered;
      assert.doesNotMatch(span.attrs.class, /\b(?:hit|miss)\b/, 'Unknown check has neutral presentation');
    }
  } finally { globalThis.SuperconLiterature = previous; }
});

test('literature statuses preserve unknown outcomes and a missing record stays unsearched', () => {
  assert.match(candidates.literatureText({ id: 'missing' }), /Literature searched: unsearched/);
  for (const status of ['structure-only', 'needs-full-text', 'not-found-in-this-search']) {
    const c = { literature_audit: { status, searched_on: '2026-10-31' } };
    assert.match(candidates.literatureText(c), /superconductivity unknown/);
    assert.match(candidates.literatureText(c), /2026-10-31/);
    assert.doesNotMatch(candidates.literatureText(c), /never|no one|not superconducting|confirmed/);
  }
  assert.match(candidates.literatureText({ literature_audit: { status: 'reported-nonsuperconducting' } }), /source’s stated conditions; other conditions remain unknown/);
  assert.match(candidates.literatureLines({ literature_audit: { status: 'structure-only' } }).join(' '), /separate from a matching DFT or experimental check and does not confirm Tc/);
});

test('literature lookup uses exact ids and gives inline records precedence over the static table', () => {
  const previous = globalThis.SuperconLiterature;
  try {
    const stored = { status: 'structure-only' }, inline = { status: 'needs-full-text' };
    globalThis.SuperconLiterature = { by_id: { 'JVASP-1': stored } };
    assert.equal(candidates.literatureFor({ id: 'JVASP-1' }), stored);
    assert.equal(candidates.literatureFor({ id: 'JVASP-1', literature_audit: inline }), inline);
    for (const c of [{ id: 'JVASP-10' }, { formula: 'JVASP-1' }, { id: 'toString' }, { id: '__proto__' }]) {
      assert.equal(candidates.literatureFor(c), null);
    }
  } finally { globalThis.SuperconLiterature = previous; }
});

test('literature sources accept only explicit HTTPS links without credentials or control characters', () => {
  const urls = ['https://doi.org/10.1234/example', 'javascript:alert(1)', 'data:text/html,x', 'http://example.test',
    '//example.test', '/relative', 'https://user:password@example.test', 'https://example.test/\nx', 'not a URL'];
  const c = { literature_audit: { status: 'structure-only', sources: urls.map(url => ({ url, cite: '<img src=x onerror=alert(1)>' })) } };
  assert.deepEqual(candidates.literatureSources(c), [{ url: urls[0], cite: '<img src=x onerror=alert(1)>' }]);
});

test('literature findings and citations render as text nodes in candidate remarks', () => {
  const malicious = '<img src=x onerror=alert(1)> [unsafe](javascript:alert(1))';
  const makeElement = (tag, attrs, ...children) => ({ tag, attrs: attrs || {}, children,
    appendChild(node) { this.children.push(node); }, querySelectorAll() { return []; }, addEventListener() {} });
  const context = { candidateData: candidates, CHECK_LABEL: {}, candState: { notesOpen: false },
    h: makeElement, cText: (value, max) => String(value).slice(0, max),
    richText: (el, value) => { assert.equal(String(value).includes(malicious), false, 'Audit text must not enter the rich-text parser'); el.text = value; return el; } };
  const source = fs.readFileSync(new URL('../app/dist/js/definitions/candidates.js', import.meta.url), 'utf8');
  vm.runInNewContext(source + '\nglobalThis.renderRemarks = candRemarksEl;', context);
  const box = context.renderRemarks({ id: 'JVASP-1', literature_audit: { status: 'not-found-in-this-search',
    conclusion: malicious, sources: [{ url: 'https://doi.org/10.1234/example', cite: malicious }, { url: 'javascript:alert(1)' }] } }, false, null, true);
  const nodes = [];
  const visit = node => { if (node && typeof node === 'object') { nodes.push(node); node.children.forEach(visit); } };
  visit(box);
  assert.ok(nodes.some(node => node.tag === 'li' && node.attrs.text === 'Search finding: ' + malicious));
  const links = nodes.filter(node => node.tag === 'a');
  assert.equal(links.length, 1);
  assert.equal(links[0].attrs.href, 'https://doi.org/10.1234/example');
  assert.equal(links[0].attrs.text, malicious);
});

test('archived experimental conditions and both provenance citations render as text without executing markup', () => {
  const malicious = '<img src=x onerror=alert(1)> [unsafe](javascript:alert(1))';
  const makeElement = (tag, attrs, ...children) => ({ tag, attrs: attrs || {}, children,
    appendChild(node) { this.children.push(node); }, querySelectorAll() { return []; }, addEventListener() {} });
  const context = { candidateData: candidates, CHECK_LABEL: { experiment: 'Measured' }, candState: { notesOpen: false },
    h: makeElement, cText: (value, max) => String(value).slice(0, max),
    richText: (el, value) => { assert.equal(String(value).includes(malicious), false); el.text = value; return el; } };
  vm.runInNewContext(fs.readFileSync(new URL('../app/dist/js/definitions/candidates.js', import.meta.url), 'utf8') + '\nglobalThis.renderRemarks = candRemarksEl;', context);
  const c = reviewedEarlierCandidate();
  Object.assign(c.prior_superconductivity, { note: malicious, cite: malicious, pressure_gpa: 0,
    measurement_conditions: [{ quantity: 'resistivity', tmin_k: null, field_t: 0, note: malicious }] });
  const box = context.renderRemarks(c, false, null, true), nodes = [];
  const visit = node => { if (node && typeof node === 'object') { nodes.push(node); node.children.forEach(visit); } };
  visit(box);
  const text = nodes.map(node => node.attrs.text || '').join(' ');
  assert.match(text, /Reported pressure: 0 GPa/);
  assert.match(text, /minimum temperature \(K\): unknown; field \(T\): 0/);
  assert.ok(nodes.some(node => node.attrs.text === 'Reported conditions and findings: ' + malicious));
  const links = nodes.filter(node => node.tag === 'a');
  assert.deepEqual(links.map(node => node.attrs.href), ['https://doi.org/10.1234/measured', 'https://example.org/frozen-prediction.json']);
  assert.equal(links[0].attrs.text, malicious);
});

test('probability spread states model disagreement and distinguishes same-fold seeds', () => {
  const c = { p_lo: 0.1, p_hi: 0.3, p_spread_method: 'same-held-out-fold-seeds' };
  assert.match(candidates.disagreement(c), /same held-out fold excluded/);
  assert.match(candidates.disagreement(c), /model disagreement describing training-data sensitivity, not a confidence interval/);
  assert.doesNotMatch(candidates.disagreement({ p_lo: 0.1, p_hi: 0.3 }), /same held-out fold/);
  assert.match(candidates.disagreement({ ...c, p_spread_method: 'same-background-fold-training-fold-ensemble' }),
    /Five training-fold models, all excluding this candidate’s background fold/);
});

test('display order is conditional Tc while original ensemble joint predictions remain unchanged', () => {
  const block = { design: { jackknife: { method: 'same-background-fold-training-fold-ensemble' } } };
  assert.match(candidates.rankingText(block), /predicted Tc if superconducting, highest first; unknown Tc comes last/);
  assert.match(candidates.rankingText(block), /original screening score remains the mean/);
  assert.match(candidates.rankingText(block), /multiplying the two displayed means can give a different value/);
  assert.doesNotMatch(candidates.rankingText({}), /Each ensemble member/);
  const published = [{ id: 'joint-first', tc: 1.64 }, { id: 'second', tc: 1.06 }];
  assert.deepEqual(ids(candidates.trackRows(published, { storm_exploration: ['joint-first', 'second'] }, 'storm_exploration')), ['joint-first', 'second']);
});

test('phonon overview reads the current plural field, retains legacy support and reports actual outcomes', () => {
  const materials = [{ status: 'completed', verdict: 'imaginary_modes_sampled' },
    { status: 'completed', verdict: 'no_significant_imaginary_modes_sampled' }, { status: 'inconclusive' }];
  const summary = { enabled: true, selected: 3, not_selected: 47, materials };
  const lines = candidates.phononSummaryLines({ phonon_checks: summary });
  assert.match(lines.join(' '), /3 candidates selected; 47 eligible candidates not selected/);
  assert.match(lines.join(' '), /significant imaginary modes detected/);
  assert.match(lines.join(' '), /no significant imaginary modes detected among the sampled q points/);
  assert.match(lines.join(' '), /inconclusive; not assessed/);
  assert.match(lines.join(' '), /cannot replace DFT/);
  assert.deepEqual(candidates.phononSummaryLines({ phonon_check: summary }), lines);
  assert.deepEqual(candidates.phononSummaryLines({ phonon_checks: summary, phonon_check: { enabled: false } }), lines);
  assert.match(candidates.phononSummaryLines({ phonon_checks: { enabled: false } })[0], /Not requested/);
  assert.deepEqual(candidates.phononSummaryLines(null), []);
});

test('phonon details retain sampled energies and settings without claiming full stability', () => {
  const lines = candidates.phononLines({ status: 'completed', verdict: 'no_significant_imaginary_modes_sampled', model: 'MACE-MP-0',
    min_signed_mode_energy_mev: -1.2345, min_mode_q_fractional: [0.5, 0, 0], max_residual_force_ev_angstrom: 0.002,
    finite_displacement: { supercell: [2, 2, 2], q_mesh: [2, 2, 2], relaxed: false } });
  assert.match(lines.join(' '), /no significant imaginary modes detected among the sampled q points/);
  assert.match(lines.join(' '), /-1.234 meV/);
  assert.match(lines.join(' '), /2 × 2 × 2/);
  assert.match(lines.join(' '), /does not compute electron–phonon coupling or Tc/);
  assert.match(lines.join(' '), /does not establish superconductivity/);
  assert.match(lines.join(' '), /not DFT or a full Brillouin-zone validation/);
  assert.doesNotMatch(lines[0], /stable|validated/);
  assert.deepEqual(candidates.phononLines(null), []);
});

test('unavailable and inconclusive phonon runs never become successful stability checks', () => {
  for (const status of ['inconclusive', 'unavailable', 'unsupported', 'timeout', 'budget_exceeded', 'invalid_structure', 'failed']) {
    const lines = candidates.phononLines({ status, verdict: 'no_significant_imaginary_modes_sampled', reason: 'Example reason.' });
    assert.match(lines[0], /not assessed/);
    assert.doesNotMatch(lines[0], /no significant imaginary modes|stable/);
    assert.match(lines.join(' '), /Example reason/);
  }
});

test('service-worker activation only removes this application’s old caches', async () => {
  const handlers = {}, deleted = [];
  const workerSource = fs.readFileSync(new URL('../app/dist/sw.js', import.meta.url), 'utf8');
  const currentCache = /const CACHE = '([^']+)'/.exec(workerSource)[1];
  const context = {
    self: { addEventListener: (event, callback) => { handlers[event] = callback; }, clients: { claim: async () => {} } },
    caches: {
      keys: async () => ['supercon-old-test-version', currentCache, 'other-project-v1', 'superconductor-v1'],
      delete: async (key) => { deleted.push(key); return true; },
    },
    URL,
  };
  vm.runInNewContext(workerSource, context);
  let activation;
  handlers.activate({ waitUntil: (p) => { activation = p; } });
  await activation;
  assert.deepEqual(deleted, ['supercon-old-test-version']);
});

test('service-worker installation precaches the entire split frontend before activation', async () => {
  const handlers = {}, requested = [];
  let activated = false, installation;
  const manifest = JSON.parse(fs.readFileSync(new URL('../app/dist/assets.json', import.meta.url), 'utf8'));
  const base = 'https://example.test/supercon-ml/sw.js';
  const context = {
    self: { location: { href: base }, addEventListener: (event, callback) => { handlers[event] = callback; },
      skipWaiting: async () => { activated = true; } },
    fetch: async () => ({ ok: true, json: async () => manifest }),
    caches: { open: async () => ({ addAll: async (files) => { requested.push(...files); } }) }, URL, Request,
  };
  vm.runInNewContext(fs.readFileSync(new URL('../app/dist/sw.js', import.meta.url), 'utf8'), context);
  handlers.install({ waitUntil: (promise) => { installation = promise; } });
  await installation;
  for (const asset of [...manifest.styles, ...manifest.scripts]) {
    assert.ok(requested.some(request => request.url === new URL(asset, base).href), 'Missing offline asset: ' + asset);
  }
  assert.ok(requested.every(request => request instanceof Request && request.cache === 'reload' && request.method === 'GET'),
    'Every install request must fetch current public bytes instead of reusing a stale browser HTTP-cache entry');
  assert.equal(new Set(requested.map(request => request.url)).size, requested.length);
  assert.equal(activated, true);
});

test('service-worker refuses nonlocal asset manifest entries', () => {
  const context = { self: { addEventListener() {}, location: { href: 'https://example.test/project/sw.js' } }, URL };
  vm.runInNewContext(fs.readFileSync(new URL('../app/dist/sw.js', import.meta.url), 'utf8'), context);
  for (const asset of ['https://other.test/code.js', '../other-project/code.js', '/outside.js']) {
    assert.throws(() => context.shellFiles({ styles: [], scripts: [asset] }), /local relative paths/);
  }
});

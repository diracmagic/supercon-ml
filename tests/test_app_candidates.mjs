import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import candidates from '../app/dist/candidates.js';

const rows = [
  { id: 'in', formula: 'NbB2', novelty: 0.8, outside: false },
  { id: 'out', formula: 'TaC', novelty: 1.2, outside: true },
  { id: 'unknown', formula: 'BaCa2', outside: false },
  { id: 'both', formula: 'MoBC', novelty: 0.4 },
];
const ids = (xs) => xs.map(candidates.id);

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

test('probability spread states model disagreement and distinguishes same-fold seeds', () => {
  const c = { p_lo: 0.1, p_hi: 0.3, p_spread_method: 'same-held-out-fold-seeds' };
  assert.match(candidates.disagreement(c), /same held-out fold excluded/);
  assert.match(candidates.disagreement(c), /model disagreement describing training-data sensitivity, not a confidence interval/);
  assert.doesNotMatch(candidates.disagreement({ p_lo: 0.1, p_hi: 0.3 }), /same held-out fold/);
  assert.match(candidates.disagreement({ ...c, p_spread_method: 'same-background-fold-training-fold-ensemble' }),
    /Five training-fold models, all excluding this candidate’s background fold/);
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
  const context = {
    self: { addEventListener: (event, callback) => { handlers[event] = callback; }, clients: { claim: async () => {} } },
    caches: {
      keys: async () => ['supercon-0.3.8', 'supercon-0.3.9', 'other-project-v1', 'superconductor-v1'],
      delete: async (key) => { deleted.push(key); return true; },
    },
    URL,
  };
  vm.runInNewContext(fs.readFileSync(new URL('../app/dist/sw.js', import.meta.url), 'utf8'), context);
  let activation;
  handlers.activate({ waitUntil: (p) => { activation = p; } });
  await activation;
  assert.deepEqual(deleted, ['supercon-0.3.8']);
});

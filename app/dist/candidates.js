/* Shared candidate data rules. Kept independent of the DOM so the rankings can be checked directly. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SuperconCandidates = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  var TRACKS = ['storm_in_domain', 'storm_exploration', 'borides', 'carbides'];
  function number(n) { return typeof n === 'number' && isFinite(n); }
  function id(c) { return String(c.id || c.formula); }
  function inside(c) { return c.outside !== true && number(c.novelty) && c.novelty <= 1; }
  function hasElement(c, symbol) { return (String(c.formula || '').match(/[A-Z][a-z]?/g) || []).indexOf(symbol) >= 0; }
  function trackRows(rows, tracks, track) {
    if (TRACKS.indexOf(track) < 0) track = TRACKS[0];
    if (tracks && Array.isArray(tracks[track])) {
      var byId = Object.create(null), seen = Object.create(null);
      rows.forEach(function (c) { byId[id(c)] = c; });
      return tracks[track].reduce(function (out, key) {
        key = String(key);
        if (byId[key] && !seen[key]) { out.push(byId[key]); seen[key] = true; }
        return out;
      }, []);
    }
    return rows.filter(function (c) {
      if (track === 'storm_in_domain') return inside(c);
      if (track === 'storm_exploration') return !inside(c);
      return hasElement(c, track === 'borides' ? 'B' : 'C');
    });
  }
  function trackForId(rows, tracks, key, current) {
    var row = rows.filter(function (c) { return id(c) === String(key); })[0];
    var preferred = row && inside(row) ? 'storm_in_domain' : 'storm_exploration';
    return [current, preferred].concat(TRACKS).filter(function (track) { return TRACKS.indexOf(track) >= 0; })
      .filter(function (track) { return trackRows(rows, tracks, track).some(function (c) { return id(c) === String(key); }); })[0] || TRACKS[0];
  }
  function clean(s, max) { return typeof s === 'string' ? s.replace(/[\u0000-\u001f]/g, ' ').slice(0, max || 600) : ''; }
  function k(n) { return number(n) ? String(Number(n.toPrecision(3))) + ' K' : ''; }
  function checkText(check) {
    var label = check.kind === 'dft' ? 'DFT check' : 'Measured';
    if (check.superconducts === false) return label + ': ' +
      (number(check.below) ? 'no superconducting transition reported down to ' + k(check.below) : 'no superconductivity reported under the studied conditions');
    return label + (number(check.tc) ? ': Tc ' + k(check.tc) : ': see the reported measurement and conditions');
  }
  function disagreement(c) {
    if (!number(c.p_lo) || !number(c.p_hi)) return '';
    var models = c.p_spread_method === 'same-background-fold-training-fold-ensemble' ?
      'Five training-fold models, all excluding this candidate’s background fold, give chances from ' : c.p_spread_method === 'same-held-out-fold-seeds' ?
      'Models trained with different random seeds, with the same held-out fold excluded, give chances from ' : 'The fitted models give chances from ';
    return models + (100 * c.p_lo).toFixed(1) + '% to ' + (100 * c.p_hi).toFixed(1) +
      '%. This is model disagreement describing training-data sensitivity, not a confidence interval or a calibrated probability range.';
  }
  function phononLines(check) {
    if (!check || typeof check !== 'object') return [];
    var labels = { not_run: 'not run', queued: 'queued', running: 'running', failed: 'failed; not assessed', skipped: 'skipped; not assessed',
      inconclusive: 'inconclusive; not assessed', unavailable: 'dependencies or model unavailable; not assessed', unsupported: 'unsupported; not assessed',
      timeout: 'timed out; not assessed', budget_exceeded: 'budget exceeded; not assessed', invalid_structure: 'invalid structure; not assessed' };
    var verdicts = { imaginary_modes_sampled: 'significant imaginary modes detected among the sampled q points',
      no_significant_imaginary_modes_sampled: 'no significant imaginary modes detected among the sampled q points' };
    var result = check.status === 'completed' ? verdicts[check.verdict] || 'completed; interpretation unavailable' : labels[check.status] || 'not assessed';
    var out = ['MACE finite-mesh phonon screen: ' + result + '.'];
    if (check.model) out.push('Potential: ' + clean(check.model, 180) + (check.model_size ? ' (' + clean(String(check.model_size), 40) + ')' : '') + '.');
    if (number(check.min_signed_mode_energy_mev)) out.push('Minimum signed mode energy: ' + check.min_signed_mode_energy_mev.toFixed(3) + ' meV' +
      (Array.isArray(check.min_mode_q_fractional) ? ' at fractional q = [' + check.min_mode_q_fractional.map(function (v) { return number(v) ? String(Number(v.toPrecision(4))) : '?'; }).join(', ') + ']' : '') + '.');
    if (number(check.significant_imaginary_modes)) out.push(check.significant_imaginary_modes + ' significant imaginary modes in ' +
      (number(check.sampled_q_points) ? check.sampled_q_points : 'the sampled') + ' q points.');
    if (number(check.max_residual_force_ev_angstrom)) out.push('Maximum residual force: ' + check.max_residual_force_ev_angstrom.toFixed(4) + ' eV/Å.');
    var fd = check.finite_displacement;
    if (fd && typeof fd === 'object') {
      if (Array.isArray(fd.supercell)) out.push('Supercell: ' + fd.supercell.map(function (v) { return clean(String(v), 8); }).join(' × ') + '.');
      if (Array.isArray(fd.q_mesh)) out.push('Sampled q mesh: ' + fd.q_mesh.map(function (v) { return clean(String(v), 8); }).join(' × ') + '.');
      if (number(fd.displacement_angstrom)) out.push('Finite displacement: ' + fd.displacement_angstrom + ' Å.');
      if (fd.relaxed === false) out.push('The structure was not relaxed with this potential. High residual forces make the phonon interpretation inconclusive.');
    }
    if (check.reason) out.push('Reason: ' + clean(check.reason, 900));
    if (check.note) out.push(clean(check.note, 900));
    (Array.isArray(check.limitations) ? check.limitations : []).slice(0, 6).forEach(function (s) { if (typeof s === 'string') out.push(clean(s, 500)); });
    out.push('This is a MACE potential-based finite-mesh prescreen, not DFT or a full Brillouin-zone validation. It does not compute electron–phonon coupling or Tc, and does not establish superconductivity.');
    return out;
  }
  return { tracks: TRACKS, id: id, inside: inside, trackRows: trackRows, trackForId: trackForId, checkText: checkText,
    disagreement: disagreement, phononLines: phononLines };
});

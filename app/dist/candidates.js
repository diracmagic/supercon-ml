/* Shared candidate data rules. Kept independent of the DOM so the rankings can be checked directly. */
(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SuperconCandidates = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';
  var TRACKS = ['storm_in_domain', 'storm_exploration', 'borides', 'carbides'];
  function number(n) { return typeof n === 'number' && isFinite(n); }
  function id(c) { return String(c.id || c.formula); }
  function predictedTc(c, kind) { return kind === 'hurricane' ? (number(c.tc_sc) ? c.tc_sc : null) : number(c.tc) ? c.tc : null; }
  function sortByPredictedTc(rows, kind) {
    return rows.map(function (c, i) { return { row: c, index: i, tc: predictedTc(c, kind) }; }).sort(function (a, b) {
      if (a.tc === null || b.tc === null) return a.tc === b.tc ? a.index - b.index : a.tc === null ? 1 : -1;
      return b.tc - a.tc || a.index - b.index;
    }).map(function (entry) { return entry.row; });
  }
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
  function sourceLink(source) {
    if (!source || typeof source !== 'object') return null;
    var url = typeof source.doi === 'string' && /^10\.\d{4,9}\/[^\s\u0000-\u001f\u007f]+$/.test(source.doi) ? 'https://doi.org/' + source.doi : source.url;
    if (typeof url !== 'string' || /[\u0000-\u0020\u007f]/.test(url)) return null;
    try {
      var parsed = new URL(url);
      return parsed.protocol === 'https:' && parsed.hostname && !parsed.username && !parsed.password ?
        { url: parsed.href, cite: clean(source.cite, 500) || 'Read the reported source' } : null;
    } catch (_) { return null; }
  }
  function dateBound(value, end) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z)?$/.test(value)) return null;
    var day = value.slice(0, 10), start = Date.parse(day + 'T00:00:00Z'), stamp = Date.parse(value);
    if (!isFinite(start) || !isFinite(stamp) || new Date(start).toISOString().slice(0, 10) !== day || new Date(stamp).toISOString().slice(0, 10) !== day) return null;
    return value.length === 10 ? start + (end ? 86399999 : 0) : stamp;
  }
  // A reviewed positive report is not inferred from a formula, an AI/news mention, a DFT result or a search status.
  // Optional prior_superconductivity evidence can live on a row or its exact-ID audit. All identity matches below
  // must be explicit true; unknown conditions do not establish a match. prediction_provenance must cite the frozen
  // prediction, not merely the latest screening date. Date-only reports must precede the whole prediction day.
  function earlierReport(c) {
    var audit = literatureFor(c), evidence = c && c.prior_superconductivity || audit && audit.prior_superconductivity || checkFor(c);
    var unknown = { status: 'unknown', evidence: evidence || null, source: null, prediction: null };
    if (!evidence || evidence.kind !== 'experiment' || evidence.superconducts !== true) return unknown;
    var match = evidence.identity_match, frozen = c && c.prediction_provenance, source = sourceLink(evidence), prediction = sourceLink(frozen);
    if (!c || typeof c.id !== 'string' || evidence.candidate_id !== c.id || evidence.reviewed !== true || !match ||
      !['composition', 'structure', 'phase', 'pressure', 'doping', 'sample_form'].every(function (key) { return match[key] === true; }) ||
      !source || !clean(evidence.locator) || !clean(evidence.sample_context) || !prediction ||
      frozen.reviewed !== true || frozen.candidate_id !== c.id) return unknown;
    var reported = dateBound(evidence.published_at, true), proposed = dateBound(frozen.frozen_at, false);
    if (reported === null || proposed === null || reported >= proposed) return unknown;
    return { status: 'confirmed', evidence: evidence, source: source, prediction: prediction };
  }
  function partitionCandidates(rows, kind) {
    var current = [], reported = [];
    rows.forEach(function (c) { (earlierReport(c).status === 'confirmed' ? reported : current).push(c); });
    return { rows: sortByPredictedTc(current, kind), reported: sortByPredictedTc(reported, kind), hidden: reported.length };
  }
  function priorReportLines(c) {
    var report = earlierReport(c);
    if (report.status === 'confirmed') return ['Earlier superconductivity report: experimentally reported on ' + clean(report.evidence.published_at, 40) +
      ', before the frozen prediction on ' + clean(c.prediction_provenance.frozen_at, 40) + '. Reviewed composition, crystal structure, phase, pressure, doping and sample form match this candidate. Retained in the reported archive.'];
    return ['Earlier superconductivity report: not established for this exact candidate and its prediction date. Formula matches, theoretical predictions and an unsuccessful literature search do not establish novelty or justify removing this candidate.'];
  }
  function checkEvidenceLines(check) {
    if (!check || typeof check !== 'object') return [];
    var lines = [];
    if (clean(check.sample_context)) lines.push('Reported sample: ' + clean(check.sample_context, 1800));
    if (clean(check.note)) lines.push('Reported conditions and findings: ' + clean(check.note, 1800));
    if (clean(check.locator)) lines.push('Source location: ' + clean(check.locator, 900));
    if (check.kind === 'experiment') {
      lines.push('Reported pressure: ' + (number(check.pressure_gpa) ? check.pressure_gpa + ' GPa.' : 'unspecified here; not assumed to be ambient.'));
      lines.push('A composition-level literature association is not a validation of the predicted crystal, phase or tuning conditions. A negative result applies only to the measured sample and conditions.');
    }
    var labels = { quantity: 'quantity', tmin_k: 'minimum temperature (K)', tmax_k: 'maximum temperature (K)',
      temperature_k: 'temperature (K)', field_t: 'field (T)', max_field_t: 'maximum field (T)',
      pressure_gpa: 'pressure (GPa)', protocol: 'protocol', method: 'method', locator: 'source location', note: 'note' };
    (Array.isArray(check.measurement_conditions) ? check.measurement_conditions : []).slice(0, 20).forEach(function (measurement) {
      if (!measurement || typeof measurement !== 'object') return;
      var parts = Object.keys(labels).filter(function (key) { return Object.prototype.hasOwnProperty.call(measurement, key); }).map(function (key) {
        var value = measurement[key];
        return labels[key] + ': ' + (number(value) ? value : clean(value, 900) || 'unknown');
      });
      if (parts.length) lines.push('Measurement conditions: ' + parts.join('; ') + '.');
    });
    return lines;
  }
  var LITERATURE = {
    'reported-superconducting': 'a superconductivity report was located; exact candidate identity and chronology require separate review',
    'reported-nonsuperconducting': 'no superconductivity reported under the source’s stated conditions; other conditions remain unknown',
    'structure-only': 'structure evidence only; superconductivity unknown',
    'needs-full-text': 'full text needed; superconductivity unknown',
    'not-found-in-this-search': 'no matching test recorded in this search; superconductivity unknown'
  };
  function literatureFor(c) {
    var audit = c && c.literature_audit;
    if (!audit || typeof audit !== 'object' || Array.isArray(audit)) {
      var table = root.SuperconLiterature && root.SuperconLiterature.by_id;
      audit = table && c && typeof c.id === 'string' && Object.prototype.hasOwnProperty.call(table, c.id) ? table[c.id] : null;
    }
    return audit && typeof audit === 'object' && !Array.isArray(audit) &&
      Object.prototype.hasOwnProperty.call(LITERATURE, audit.status) ? audit : null;
  }
  function checkFor(c) {
    var original = c && c.check;
    if (!original || typeof original !== 'object' || !c || typeof c.id !== 'string') return original;
    var audit = literatureFor(c), correction = audit && audit.check_correction;
    if (!correction) {
      var table = root.SuperconLiterature && root.SuperconLiterature.by_id;
      var stored = table && Object.prototype.hasOwnProperty.call(table, c.id) && table[c.id];
      correction = stored && stored.check_correction;
    }
    var reviewed = correction && correction.check;
    return correction && typeof correction.replaces_doi === 'string' && original.doi === correction.replaces_doi &&
      reviewed && typeof reviewed === 'object' && !Array.isArray(reviewed) && reviewed.kind === original.kind && reviewed.doi === original.doi ? reviewed : original;
  }
  function literatureText(c) {
    var audit = literatureFor(c);
    if (!audit) return 'Literature searched: unsearched; no audit recorded.';
    var date = typeof audit.searched_on === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(audit.searched_on) ? ' (' + audit.searched_on + ')' : '';
    return 'Literature searched: ' + LITERATURE[audit.status] + date + '.';
  }
  function literatureLines(c) {
    var audit = literatureFor(c), out = [literatureText(c)];
    if (!audit) return out;
    if (clean(audit.scope)) out.push('Search scope: ' + clean(audit.scope, 1200));
    if (clean(audit.conclusion) && clean(audit.conclusion).toLowerCase() !== 'unknown') out.push('Search finding: ' + clean(audit.conclusion, 1800));
    var limits = Array.isArray(audit.limitations) ? audit.limitations.filter(function (s) { return typeof s === 'string'; }).join(' ') : audit.limitations;
    if (clean(limits)) out.push('Search limitations: ' + clean(limits, 1800));
    out.push('A literature search record is separate from a matching DFT or experimental check and does not confirm Tc.');
    return out;
  }
  function literatureSources(c) {
    var audit = literatureFor(c);
    return (audit && Array.isArray(audit.sources) ? audit.sources : []).slice(0, 20).reduce(function (out, source) {
      if (!source || typeof source.url !== 'string' || /[\u0000-\u0020\u007f]/.test(source.url)) return out;
      try {
        var url = new URL(source.url);
        if (url.protocol === 'https:' && url.hostname && !url.username && !url.password) {
          out.push({ url: url.href, cite: clean(source.cite, 500) || 'Read literature source' });
        }
      } catch (_) { /* Invalid or relative links are not sources. */ }
      return out;
    }, []);
  }
  function checkText(check) {
    var label = check.kind === 'dft' ? 'DFT check' : 'Measured';
    if (check.superconducts === false) return label + ': ' +
      (number(check.below) ? 'no superconducting transition reported down to ' + k(check.below) : 'no superconductivity reported under the studied conditions');
    if (check.superconducts === null) return label + ': superconductivity outcome unknown; see the reported measurement and conditions';
    return label + (number(check.tc) ? ': Tc ' + k(check.tc) : ': see the reported measurement and conditions');
  }
  function disagreement(c) {
    if (!number(c.p_lo) || !number(c.p_hi)) return '';
    var models = c.p_spread_method === 'same-background-fold-training-fold-ensemble' ?
      'Five training-fold models, all excluding this candidate’s background fold, give model scores from ' : c.p_spread_method === 'same-held-out-fold-seeds' ?
      'Models trained with different random seeds, with the same held-out fold excluded, give model scores from ' : 'The fitted models give model scores from ';
    return models + (100 * c.p_lo).toFixed(1) + '% to ' + (100 * c.p_hi).toFixed(1) +
      '%. This is model disagreement describing training-data sensitivity, not a confidence interval or a calibrated probability range.';
  }
  function rankingText(block) {
    var ensemble = block && block.design && block.design.jackknife;
    return 'Displayed order is predicted Tc if superconducting, highest first; unknown Tc comes last. ' +
      (ensemble && (ensemble.method === 'same-background-fold-training-fold-ensemble' || ensemble.method === 'training-fold-ensemble') ?
        'The original screening score remains the mean of the ensemble’s classifier-score-times-Tc predictions; multiplying the two displayed means can give a different value.' :
        'The original classifier-score-times-Tc screening value is preserved; it does not set this display order.');
  }
  function phononSummaryLines(screen) {
    var check = screen && (screen.phonon_checks || screen.phonon_check);
    if (!check || typeof check !== 'object') return [];
    var out = ['Optional MACE phonon prescreen. ' + (check.enabled ?
      (number(check.selected) ? check.selected + ' candidates selected' : 'Enabled') +
      (number(check.not_selected) ? '; ' + check.not_selected + ' eligible candidates not selected' : '') + '.' :
      'Not requested for this screening run.')];
    var counts = Object.create(null);
    (check.enabled && Array.isArray(check.materials) ? check.materials : []).forEach(function (material) {
      var status = phononLines(material)[0];
      if (status) counts[status] = (counts[status] || 0) + 1;
    });
    Object.keys(counts).forEach(function (status) { out.push(counts[status] + ' result(s): ' + status); });
    out.push('A finite q mesh and a learned potential cannot replace DFT, a full Brillouin-zone check or a superconductivity measurement. See each candidate’s Remarks for settings and limitations.');
    return out;
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
  /* A correction to the pools of screening rounds 1 to 6. They kept a JARVIS-DFT entry if the file's ehull field was at
     most 50 meV/atom, and that field does not follow the convex hull of the file's own formation energies. A list of one
     of those rounds is described as selected with the field. The published record screen.hull gives each candidate's
     distance to the hull computed from those energies; a list's part of it is used only for the list it was computed
     for: the same screening round and the same number of candidates. Nothing here changes a list, a rank or a score. */
  var FIELD_POOL_LAST_ROUND = 6;
  function listRound(screen, kind) {
    var block = kind === 'hurricane' ? screen && screen.hurricane : screen;
    return block && number(block.round) ? block.round : screen && number(screen.round) ? screen.round : null;
  }
  function fieldPool(screen, kind) {
    var round = listRound(screen, kind);
    return round !== null && round <= FIELD_POOL_LAST_ROUND;
  }
  function hullRecord(screen, kind) {
    if (!screen || typeof screen !== 'object' || !fieldPool(screen, kind)) return null;
    var hull = screen.hull && typeof screen.hull === 'object' ? screen.hull : null, s = hull ? hull[kind === 'hurricane' ? 'hurricane' : 'storm'] : null;
    var block = kind === 'hurricane' ? screen.hurricane : screen, rows = block && Array.isArray(block.candidates) ? block.candidates : [];
    var d = s && typeof s === 'object' ? s.distance_eV_per_atom : null;
    if (!d || typeof d !== 'object' || Array.isArray(d)) return null;
    if (s.round !== listRound(screen, kind) || !number(s.listed) || s.listed !== rows.length || s.found !== s.listed) return null;
    if (![s.beyond_50_meV, s.beyond_200_meV].every(function (n) { return number(n) && n >= 0 && n <= s.listed; }) || s.beyond_200_meV > s.beyond_50_meV) return null;
    if (!rows.every(function (c) { return c && Object.prototype.hasOwnProperty.call(d, id(c)) && number(d[id(c)]) && d[id(c)] >= 0; })) return null;
    return s;
  }
  function hullDistance(screen, kind, c) {
    var s = hullRecord(screen, kind);
    return s && c ? s.distance_eV_per_atom[id(c)] : null;
  }
  // a candidate that the record puts beyond the 50 meV/atom the pools were meant to keep within: its distance in meV/atom
  function hullBeyond(screen, kind, c) {
    var d = hullDistance(screen, kind, c);
    return number(d) && d > 0.05 ? Math.round(1000 * d) : null;
  }
  function hullRecordPath(screen) {
    var path = screen && screen.hull && typeof screen.hull.record === 'string' ? screen.hull.record : '';
    return /^results\/validation\/[\w.-]+\.md$/.test(path) ? path : 'results/validation/screening-pools-hull-correction.md';
  }
  return { tracks: TRACKS, id: id, inside: inside, trackRows: trackRows, trackForId: trackForId, checkText: checkText,
    fieldPool: fieldPool, hullRecord: hullRecord, hullDistance: hullDistance, hullBeyond: hullBeyond, hullRecordPath: hullRecordPath,
    predictedTc: predictedTc, sortByPredictedTc: sortByPredictedTc, partitionCandidates: partitionCandidates, earlierReport: earlierReport,
    priorReportLines: priorReportLines, sourceLink: sourceLink, checkEvidenceLines: checkEvidenceLines,
    literatureFor: literatureFor, literatureText: literatureText, literatureLines: literatureLines, literatureSources: literatureSources, checkFor: checkFor,
    disagreement: disagreement, rankingText: rankingText, phononSummaryLines: phononSummaryLines, phononLines: phononLines };
});

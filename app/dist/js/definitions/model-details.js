'use strict';
// model-details: shared lexical function definitions; no startup side effects.

  const featLabel = function featLabel(n) {
    n = String(n || '');
    if (FEAT_LABEL[n]) return FEAT_LABEL[n];
    var m = /^x_([A-Z][a-z]?)$/.exec(n);
    if (m) return m[1] + ' share';
    m = /^cs_(.+)$/.exec(n);
    if (m) return m[1] + ' crystal';
    m = /^ct_(.+)$/.exec(n);
    if (m) return m[1] + ' lattice';
    m = /^(.+)_(mean|std|min|max)$/.exec(n);
    if (m && PROP_LABEL[m[1]]) return STAT_LABEL[m[2]] + ' ' + PROP_LABEL[m[1]];
    return n.replace(/_/g, ' ');
  };

  const famLabel = function famLabel(f) { return { 'cuprate': 'Cuprates', 'iron-based': 'Iron- and nickel-based', 'heavy-fermion': 'Heavy-fermion', 'other oxide': 'Other oxides' }[f] || f; };

  const k1 = function k1(x) { return typeof x === 'number' ? (Math.abs(x) >= 10 ? x.toFixed(0) : x.toFixed(1)) + ' K' : '—'; };

  const k2 = function k2(x) { return typeof x === 'number' ? x.toFixed(x >= 10 ? 1 : 2) + ' K' : '—'; };

  const barRow = function barRow(label, sub, vals, max) {
    var bars = h('div', { class: 'dt-bars' });
    vals.forEach(function (v) {
      bars.appendChild(h('div', { class: 'dt-bar ' + v.cls },
        h('span', { class: 'dt-fill', style: 'width:' + Math.max(2, Math.min(100, 100 * v.val / (max || 1))).toFixed(1) + '%' }),
        h('span', { class: 'dt-val', text: v.text })));
    });
    return h('div', { class: 'dt-row' }, h('div', { class: 'dt-label' }, h('b', { text: label }), sub ? h('span', { text: sub }) : null), bars);
  };

  const statTile = function statTile(label, value, sub) {
    return h('div', { class: 'dt-tile' }, h('p', { class: 'dt-tile-label', text: label }), h('p', { class: 'dt-tile-value', text: value }), sub ? h('p', { class: 'dt-tile-sub', text: sub }) : null);
  };

  const smallTable = function smallTable(head, rows) {
    var tb = h('tbody');
    rows.forEach(function (r) { tb.appendChild(h('tr', null, r.map(function (c, i) { return h('td', { class: i ? 'num' : null }, c); }))); });
    return h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl dt-tbl' },
      h('thead', null, h('tr', null, head.map(function (c, i) { return h('th', { class: i ? 'num' : null }, c); }))), tb));
  };


  const renderDetails = function renderDetails(d) {
    var el = $('#details-card');
    if (!el) return;
    clear(el);
    var hu = d && d.hurricane, hvs = hu ? list(hu.versions).filter(function (v) { return v && v.scores; }) : [];
    var hv = hvs.length ? (hvs.filter(function (v) { return v.version === hu.current; })[0] || hvs[hvs.length - 1]) : null;
    var cal = d && d.ai_model && d.ai_model.calibration && d.ai_model.calibration.scores ? d.ai_model.calibration : null;
    var ens = d && d.ai_model && d.ai_model.ensemble && d.ai_model.ensemble.scores ? d.ai_model.ensemble : null;
    var unc = d && d.ai_model && d.ai_model.uncertainty && d.ai_model.uncertainty.scores ? d.ai_model.uncertainty : null;
    var ri = radInfo(), gn = d && d.gnn && typeof d.gnn.tc_mae === 'number' ? d.gnn : null;
    el.hidden = !hv && !cal && !ri && !gn && !ens && !unc;
    if (el.hidden) return;
    var parts = [cardHead('Model details', 'What the latest training rounds found, read from the live progress data.')];
    if (hv) parts.push(hurricaneDetails(hu, hv));
    if (ri) parts.push(radarDetails(ri));
    if (unc) parts.push(uncertaintyDetails(unc));
    if (ens) parts.push(ensembleDetails(ens));
    if (cal) parts.push(calibrationDetails(cal));
    if (gn) parts.push(gnnDetails(gn));
    append(el, parts);
  };

  const pct = function pct(x) { return typeof x === 'number' ? radPct(x) : '—'; };


  const radarDetails = function radarDetails(ri) {
    var v = ri.v, sc = v.scores || {}, dd = ri.data || {}, box = h('div', { class: 'dt-block' });
    box.appendChild(h('h3', { class: 'dt-title' }, radTitle(ri) + ' · which model to ask',
      h('span', { class: 'mf-status', text: v.status === 'adopted' ? 'in use' : 'experimental' })));
    box.appendChild(h('p', { class: 'dt-lead', text: 'Learns from ' + fmtInt(dd.n) + ' SuperCon entries in 3DSC labelled by their chemical class: ' + fmtInt(dd.n_unconventional) +
      ' in Hurricane’s four unconventional families and ' + fmtInt(dd.n_conventional) + ' conventional ones for Storm. It gives the probability of an unconventional family and sends the material to Hurricane at one half or more. Cross-validation holds out whole Materials Project chemical-system groups.' }));
    box.appendChild(h('div', { class: 'dt-tiles' },
      statTile('Right model', pct(sc.balanced_accuracy), 'baseline ' + pct(sc.reference_balanced_accuracy) + ' (balanced accuracy)'),
      statTile('Unconventional to Hurricane', pct(sc.to_hurricane), 'conventional to Storm: ' + pct(sc.to_storm)),
      statTile('Better than baseline', (sc.folds_better || 0) + ' of ' + list(sc.folds).length + ' folds', 'log loss ' + (typeof sc.log_loss === 'number' ? sc.log_loss.toFixed(3) : '—') + ' against ' + (typeof sc.reference_log_loss === 'number' ? sc.reference_log_loss.toFixed(3) : '—'))));
    var lo = list(v.lofo), bc = sc.by_class || {};
    if (lo.length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Leave one family out: how much of a family goes to the right model when Radar is trained without it, and when the family is in training?' }));
      box.appendChild(smallTable(['Family', 'Right model', 'Left out', 'In training'],
        lo.map(function (r) { return [(r.label || r.family) + ' (' + fmtInt(r.n) + ')', r.model, pct(r.right), bc[r.family] ? pct(bc[r.family].right) : '—']; })));
    }
    var imp = list(v.importance).slice(0, 8);
    if (imp.length) {
      var ul = h('ul', { class: 'dt-chips' });
      imp.forEach(function (i) { ul.appendChild(h('li', null, featLabel(i.name), h('span', { text: ' +' + (+i.gain).toFixed(3) }))); });
      box.appendChild(h('p', { class: 'dt-sub', text: 'What it relies on most (how much the log loss grows when one input is shuffled):' }));
      box.appendChild(ul);
    }
    var kn = list(v.known).filter(function (k) { return k.list === 'anchors' || /^(MgB2|Nb3Sn|NbSe2|H3S|LaH10|Pb|Nb)$/.test(k.name); });
    if (kn.length) {
      var seen = kn.some(function (k) { return k.in_training; });
      box.appendChild(h('p', { class: 'dt-sub', text: 'Graded materials, each scored by a Radar that never saw it' + (seen ? ' (those also in 3DSC out of fold, with their chemical-system group held out)' : '') +
        ', with the probability that each belongs to an unconventional family:' }));
      box.appendChild(smallTable(['Material', 'Probability', 'Goes to'], kn.map(function (k) {
        return [hurSub(k.name) + (k.in_training ? ' (in 3DSC)' : ''), k.p_unconventional.toFixed(2), k.model];
      })));
    }
    if (list(v.changes).length) box.appendChild(h('p', { class: 'note', text: 'Design: ' + prettyMath(list(v.changes).join('; ')) + '.' }));
    box.appendChild(h('p', { class: 'note dt-data' }, 'Data: ', h('a', { href: 'https://doi.org/10.1038/s41597-023-02721-y', text: '3DSC' }),
      ' (T. Sommer et al., Sci. Data 10, 816 (2023)), used under ', h('a', { href: 'https://creativecommons.org/licenses/by/4.0/', text: 'CC BY 4.0' }),
      '. The labels are SuperCon’s chemical classes, a proxy for the pairing mechanism rather than a measurement of it.'));
    return box;
  };


  const gnnDetails = function gnnDetails(g) {
    var box = h('div', { class: 'dt-block' }), ver = g.current ? ' ' + g.current : '';
    var vs = list(g.versions), cur = vs.filter(function (x) { return x.version === g.current; })[0];
    box.appendChild(h('h3', { class: 'dt-title' }, (g.name || 'Graph neural network') + ver + ' · learns from the crystal graph',
      h('span', { class: 'mf-status', text: g.status === 'done' ? 'trained' : g.status || '' })));
    // a hybrid design (round 2 and later) adds Storm 1.0's descriptors to the readout, so it is no longer free of hand-made features
    var hybrid = /descriptors/.test(String((g.spec || {}).readout || ''));
    box.appendChild(h('p', { class: 'dt-lead', text: 'Atoms are the nodes and each atom is joined to its 12 nearest neighbours; gated message passing turns the graph into a prediction of Tc, λ and ω_log' +
      (hybrid ? ', and Storm 1.0’s 54 crystal descriptors join the learned graph vector before the final layers' : ', with no hand-made features') + '. Scored on the same five folds as Storm, grouped by chemical system.' }));
    box.appendChild(h('div', { class: 'dt-tiles' },
      statTile('Tc error (DFT)', k2(g.tc_mae), typeof g.storm1_mae === 'number' ? 'Storm 1.0 ' + k2(g.storm1_mae) : null),
      statTile('Averaged with Storm 1.0', g.blend ? k2(g.blend.tc_mae) : '—', g.blend ? 'better than Storm 1.0 in ' + g.blend.folds_better_storm1 + ' of 5 folds' : null),
      statTile('λ and ω_log', typeof g.lambda_mae === 'number' ? g.lambda_mae.toFixed(3) : '—', typeof g.wlog_mae === 'number' ? 'ω_log ' + g.wlog_mae.toFixed(1) + ' K' : null)));
    var r2 = vs.filter(function (x) { return x.round === 2 && x.search; })[0];
    if (r2) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Round 2: designs the AI agent proposed (one seed each; Tc error in K):' }));
      box.appendChild(smallTable(['Design', 'Tc error', 'Better folds', 'With Storm 1.0'], list(r2.search.leaderboard).map(function (r) {
        return [r.id + ' ' + r.name, k2(r.tc_mae), (r.folds_better || 0) + ' of 5', typeof r.blend_mae === 'number' ? k2(r.blend_mae) : '—'];
      })));
      box.appendChild(h('p', { class: 'note', text: gnnRound2Note(r2) }));
    }
    return box;
  };


  // The search trains one seed per design; the selected one is then retrained like version 1.0 before any release.
  const gnnRound2Note = function gnnRound2Note(r2) {
    var best = String(r2.summary || '').replace(/^\+ /, '');
    var like = 'retrained like version 1.0 (' + (r2.seeds || 2) + ' seeds averaged, ' + (r2.epochs || 200) + ' epochs)';
    // "checked" is written by the final check; until then a selected design is only a candidate
    if (!r2.checked && (r2.status === 'selected' || r2.status === 'adopted'))
      return 'The best design, ' + best + ', beat the round-1 design trained the same way; it is being ' + like + ' before it can be released.';
    if (r2.checked && r2.status === 'adopted') return 'The best design, ' + best + ', ' + like + ', is off by ' + k2(r2.tc_mae) + ' against ' + k2(r2.reference_mae) +
      ' for version 1.0 and better in ' + r2.folds_better + ' of 5 folds, so it was released as version ' + r2.version + '.';
    if (r2.checked) return 'The best design, ' + best + ', ' + like + ', is off by ' + k2(r2.tc_mae) + ' against ' + k2(r2.reference_mae) +
      ' for version 1.0 and better in only ' + r2.folds_better + ' of 5 folds, so version 1.0 stays.';
    return 'No design beat the round-1 design trained the same way on average and in at least 4 of 5 folds, so version 1.0 stays.';
  };


  const ensembleDetails = function ensembleDetails(e) {
    var sc = e.scores || {}, ca = e.calibration || {}, box = h('div', { class: 'dt-block' });
    box.appendChild(h('h3', { class: 'dt-title' }, 'Storm round 4 · trees and a graph network together',
      h('span', { class: 'mf-status', text: e.status === 'adopted' ? 'Storm ' + e.version + (stormUnc() ? ', now with ranges (' + stormUnc().version + ')' : ' in use') : 'experimental' })));
    box.appendChild(h('p', { class: 'dt-lead', text: 'Storm 1.0’s boosted trees learn from hand-made features, the graph network from the atoms and their neighbours, and their mistakes only partly overlap. Round 4 averages Storm 1.0 with the ' + (e.gnn && e.gnn.design ? e.gnn.design : 'graph network') + ', then calibrates the result to measured Tc as in round 3.' }));
    box.appendChild(h('div', { class: 'dt-tiles' },
      statTile('Tc error (DFT)', k2(sc.tc_mae), 'Storm 1.0 ' + k2(sc.reference_mae)),
      statTile('Better than Storm 1.0', (sc.folds_better || 0) + ' of ' + list(sc.folds).length + ' folds', e.summary || null),
      statTile('Against measured Tc', typeof ca.mae === 'number' ? k2(ca.mae) : '—', typeof ca.mae_storm3 === 'number' ? 'Storm 3.0 ' + k2(ca.mae_storm3) : null)));
    if (list(e.leaderboard).length) box.appendChild(smallTable(['Combination', 'Tc error (DFT)', 'Better folds'], list(e.leaderboard).map(function (r) {
      return [r.id + ' ' + r.name, k2(r.tc_mae), (r.folds_better || 0) + ' of 5'];
    })));
    box.appendChild(h('p', { class: 'note', text: e.status === 'adopted' ? 'Released as Storm ' + e.version + ': better than Storm 1.0 on the DFT labels in ' + (sc.folds_better || 0) + ' of ' + list(sc.folds).length + ' folds and, after calibration, closer to measured Tc than Storm 3.0 on average' +
      (typeof ca.folds_better_storm3 === 'number' ? ' (in ' + ca.folds_better_storm3 + ' of ' + list(ca.folds).length + ' folds)' : '') + '.' : 'Not released, so Storm 3.0 stays in use.' + (e.rule ? ' The rule: ' + e.rule + '.' : '') }));
    return box;
  };


  // Storm round 5: a 90% range around every Storm 4.0 prediction (ai_model.uncertainty).
  const uncertaintyDetails = function uncertaintyDetails(u) {
    var sc = u.scores || {}, box = h('div', { class: 'dt-block' }), on = u.status === 'adopted' && stormUnc();
    var pct = function (x) { return typeof x === 'number' ? (100 * x).toFixed(1) + '%' : '—'; };   // coverages with one decimal throughout
    box.appendChild(h('h3', { class: 'dt-title' }, 'Storm round 5 · how sure is Storm?',
      h('span', { class: 'mf-status', text: on ? 'Storm ' + u.version + ' in use' : 'experimental' })));
    box.appendChild(h('p', { class: 'dt-lead', text: 'To pick materials for a calculation or an experiment, the range matters as much as the number. Round 5 puts a 90% range around every Storm 4.0 prediction; the prediction itself does not change. Each range is set by conformal prediction from the errors in the other four folds, so it never uses its own fold’s answers.' }));
    box.appendChild(h('div', { class: 'dt-tiles' },
      statTile('Range holds the computed Tc', pct(sc.coverage), '90% wanted, for materials it never saw'),
      statTile('For the highest-Tc tenth', pct(sc.tail_coverage), typeof sc.reference_tail_coverage === 'number' ? 'one width for all: ' + pct(sc.reference_tail_coverage) : null),
      statTile('Half the ranges narrower than', k2(sc.median_width), typeof sc.interval_score === 'number' ? 'interval score ' + k2(sc.interval_score) + ' against ' + k2(sc.reference_interval_score) : null)));
    if (list(u.leaderboard).length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Designs the AI agent proposed. Score: the interval score, the width plus 20 times any miss, lower is better; held: how often the range held the computed Tc, for all materials and for the highest-Tc tenth; width: half of the ranges are narrower.' }));
      var rel = on ? list(u.leaderboard).filter(function (r) { return r.name === u.summary; })[0] : null;
      box.appendChild(smallTable(['Design', 'Score', 'Held', 'Width'], list(u.leaderboard).map(function (r) {
        return [r.id + ' ' + r.name + (r === rel ? ' (released)' : ''), k2(r.interval_score),
          h('span', null, pct(r.coverage), h('br'), h('span', { class: 'dt-cell-sub', text: 'top tenth ' + pct(r.tail_coverage) })), k2(r.median_width)];
      })));
      // in round 5 a design also had to hold at least 80% of the highest-Tc tenth; say why a better interval score lost
      var beat = rel && u.round === 5 ? list(u.leaderboard).filter(function (r) { return r.id !== 'U0' && r.interval_score < rel.interval_score && r.tail_coverage < 0.8; }) : [];
      if (beat.length) box.appendChild(h('p', { class: 'note', text: beat.map(function (r) { return r.id; }).join(', ').replace(/, ([^,]*)$/, ' and $1') + (beat.length > 1 ? ' have' : ' has') +
        ' a better interval score but holds less than 80% of the highest-Tc tenth, where screening looks, so ' + rel.id + ' was released.' }));
    }
    var ex = list(u.examples);
    if (ex.length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'The highest predictions, with their ranges (computed Tc, out of fold):' }));
      box.appendChild(smallTable(['Material', 'Computed Tc', 'Storm', '90% range'], ex.map(function (r) {
        return [hurSub(r.name), k1(r.tc), k1(r.pred), r.lo.toFixed(1) + '–' + r.hi.toFixed(1) + ' K'];
      })));
    }
    var m = u.measured;
    if (m && m.one_width) box.appendChild(h('p', { class: 'note', text: 'Against measured Tc (' + fmtInt(m.n) + ' matched materials, after round 3’s calibration): one width for all holds ' + pct(m.one_width.coverage) +
      ' of them with a median width of ' + k2(m.one_width.median_width) + (m.log_width ? '; a width on log(1 + Tc) holds ' + pct(m.log_width.coverage) + ' with ' + k2(m.log_width.median_width) : '') + '. Reported, not used to choose.' }));
    box.appendChild(h('p', { class: 'note', text: on ? 'Released as Storm ' + u.version + ': ' + lcFirst(u.summary) + '. ' + (u.rule ? 'The rule: ' + u.rule + '.' : '')
      : 'Not released, so Storm 4.0 gives no range yet.' + (u.rule ? ' The rule: ' + u.rule + '.' : '') }));
    if (u.caveat) box.appendChild(h('p', { class: 'note', text: 'A range is for the computed Tc that Storm learns; measured Tc can lie further away.' }));
    return box;
  };


  // round 3 on: the false-alarm check that decides a release (v.reliability), with the background compounds behind it
  const hurRel = function hurRel(v) { return v && v.reliability && typeof v.reliability.false_alarms === 'number' ? v.reliability : null; };

  const hurRelNote = function hurRelNote(v, rl, pv, pvName) {
    var sc = v.scores || {};
    if (v.status === 'adopted') return 'Released as Hurricane ' + v.version + ': ' + (rl.false_alarms === 0 ? 'no false alarms' : pct(rl.false_alarms) + ' false alarms') + ' against ' + pct(rl.false_alarms_previous) + ' for ' + pvName +
      (typeof rl.folds_fewer === 'number' ? ', fewer in ' + rl.folds_fewer + ' of ' + list(rl.folds).length + ' folds' : '') + ', with a measured-Tc error of ' + kPair(sc.tc_mae, pv && pv.tc_mae)[0] +
      (pv ? ' against ' + kPair(sc.tc_mae, pv.tc_mae)[1] : '') + '. The rule: ' + v.rule + '.';
    var ck = rl.checks || {}, fail = Object.keys(HUR_CHECKS).filter(function (k) { return ck[k] === false; }).map(function (k) { return HUR_CHECKS[k]; });
    return 'Not released, so ' + (pvName || 'the previous version') + ' stays in use' + (fail.length ? ': the design with the fewest false alarms failed ' + (fail.length > 1 ? 'these tests: ' : 'the test of ') + fail.join(', ').replace(/, ([^,]*)$/, ' and $1') : '') + '. The rule: ' + v.rule + '.';
  };

  // round 4 on: "not known" far from the training data, and how many superconductors of a left-out family are called unlikely
  const hur4 = function hur4(rl) { return !!(rl && typeof rl.dismissed === 'number'); };

  // round 4 on: a share averaged over the left-out families ("found", "unknown", "found_reference", ...), or null if any is missing
  const hurLofoAvg = function hurLofoAvg(v, k) {
    var xs = list(v && v.lofo).map(function (r) { return r && r[k]; });
    return xs.length && xs.every(function (x) { return typeof x === 'number'; }) ? xs.reduce(function (a, b) { return a + b; }, 0) / xs.length : null;
  };

  // the left-out family that is still called unlikely most often, when the distance misses much of it
  const hurWorstLofo = function hurWorstLofo(v) {
    return list(v && v.lofo).filter(function (r) { return r && typeof r.dismissed === 'number' && r.dismissed >= 0.25; })
      .sort(function (a, b) { return b.dismissed - a.dismissed; })[0] || null;
  };

  const hurRelNote4 = function hurRelNote4(v, rl, pv, pvName) {
    var sc = v.scores || {}, ref = rl.reference_version ? 'Hurricane ' + rl.reference_version : '';
    if (v.status === 'adopted') return 'Released as Hurricane ' + v.version + ': trained without a whole family, it calls ' + pct(rl.dismissed) + ' of that family’s superconductors unlikely, against ' +
      pct(rl.dismissed_previous) + ' for ' + pvName + (ref ? ' and ' + pct(rl.dismissed_reference) + ' for ' + ref : '') + '; it raises ' + (rl.false_alarms === 0 ? 'no false alarms' : 'false alarms on ' + pct(rl.false_alarms)) +
      ' on the held-out compounds with no record and gives a chance to ' + pct(rl.coverage) + ' of the held-out 3DSC entries, with a measured-Tc error of ' + kPair(sc.tc_mae, pv && pv.tc_mae)[0] +
      (pv ? ' against ' + kPair(sc.tc_mae, pv.tc_mae)[1] : '') + '. The rule: ' + v.rule + '.';
    var ck = rl.checks || {}, fail = Object.keys(HUR_CHECKS4).filter(function (k) { return ck[k] === false; }).map(function (k) { return HUR_CHECKS4[k]; });
    return 'Not released, so ' + (pvName || 'the previous version') + ' stays in use' + (fail.length ? ': the design that calls the fewest of a left-out family unlikely failed ' + (fail.length > 1 ? 'these tests: ' : 'the test of ') + fail.join(', ').replace(/, ([^,]*)$/, ' and $1') : '') + '. The rule: ' + v.rule + '.';
  };

  // two errors in K, with a second decimal when one decimal would show them as equal
  const kPair = function kPair(a, b) {
    if (typeof a !== 'number' || typeof b !== 'number' || k2(a) !== k2(b) || a === b) return [k2(a), k2(b)];
    return [a.toFixed(2) + ' K', b.toFixed(2) + ' K'];
  };

  const hurSigned = function hurSigned(x) { return typeof x === 'number' ? (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(2) : '—'; };


  const hurricaneDetails = function hurricaneDetails(hu, v) {
    var sc = v.scores, data = v.data || hu.data || {}, box = h('div', { class: 'dt-block' }), rl = hurRel(v), bg = rl && rl.background ? rl.background : null, r4 = hur4(rl);
    var bgN = bg ? (typeof bg.n_used === 'number' ? bg.n_used : bg.n) : null;
    box.appendChild(h('h3', { class: 'dt-title' }, 'Hurricane ' + v.version + ' · unconventional superconductors',
      h('span', { class: 'mf-status', text: v.status === 'adopted' ? 'in use' : 'experimental' })));
    box.appendChild(h('p', { class: 'dt-lead', text: 'Trained on measured Tc of ' + (data.n || '?').toLocaleString('en-US') + ' cuprates, iron- and nickel-based, heavy-fermion compounds and other oxides (' +
      (data.n_sc || '?').toLocaleString('en-US') + ' of them superconducting) from 3DSC, which matches the SuperCon database to Materials Project structures.' +
      (typeof bgN === 'number' ? ' Its classifier also learns from ' + fmtInt(bgN) + ' compounds with no superconductivity record, counted as probably not superconducting.' : '') +
      (r4 && rl.abstain ? ' It gives a chance only to compounds near its training data and answers “not known” further away.' : '') +
      ' Zero-Tc entries are catalog labels whose measurement limits and conditions are not established here. Cross-validation holds out chemical-system groups; related structures with different element sets may remain in training.' }));
    // from round 2 on, a version is compared with the previous one retrained on the same folds (v.previous)
    var pv = v.previous && typeof v.previous.tc_mae === 'number' ? v.previous : null, pvName = pv ? 'Hurricane ' + pv.version : '';
    box.appendChild(h('div', { class: 'dt-tiles' },
      statTile('Average error', kPair(sc.tc_mae, pv && pv.tc_mae)[0], (pv ? pvName + ' ' + kPair(sc.tc_mae, pv.tc_mae)[1] + ', ' : '') + 'baseline ' + k2(sc.reference_mae)),
      statTile('Superconductors only', k2(sc.sc_mae), pv && typeof pv.sc_mae === 'number' ? pvName + ' ' + k2(pv.sc_mae) : sc.high_tc ? 'Tc ≥ ' + sc.high_tc + ' K: ' + k2(sc.high_tc_mae) : null),
      r4 ? statTile('Left-out families called unlikely', pct(rl.dismissed), (pvName ? pvName + ' ' + pct(rl.dismissed_previous) : '') + (rl.reference_version ? (pvName ? ', ' : '') + 'Hurricane ' + rl.reference_version + ' ' + pct(rl.dismissed_reference) : ''))
        : rl ? statTile('False alarms', pct(rl.false_alarms), (pvName ? pvName + ' ' + pct(rl.false_alarms_previous) + ', ' : '') + 'on compounds with no record')
        : pv ? statTile('Better than ' + pvName, (pv.folds_better || 0) + ' of ' + list(pv.folds).length + ' folds', 'retrained on the same folds')
        : statTile('Better than baseline', (sc.folds_better || 0) + ' of ' + list(sc.folds).length + ' folds', 'composition-only model')));
    if (pv && sc.high_tc && typeof sc.high_tc_mae === 'number' && typeof pv.high_tc_mae === 'number')
      box.appendChild(h('p', { class: 'note', text: 'For Tc ≥ ' + sc.high_tc + ' K the average error is ' + k2(sc.high_tc_mae) + ', against ' + k2(pv.high_tc_mae) + ' for ' + pvName + '.' }));
    var fam = sc.by_family || {}, keys = Object.keys(fam), max = 0;
    keys.forEach(function (f) { max = Math.max(max, fam[f].mae || 0, fam[f].mae_ref || 0); });
    if (keys.length) {
      var fb = h('div', { class: 'dt-chart', role: 'img', 'aria-label': 'Average error by family, Hurricane against the baseline' },
        h('p', { class: 'dt-sub' }, 'Average error by family: ', h('span', { class: 'dt-key k-a', text: 'Hurricane' }), ' ', h('span', { class: 'dt-key k-b', text: 'baseline' })));
      keys.forEach(function (f) {
        fb.appendChild(barRow(famLabel(f), fam[f].n + ' entries', [{ cls: 'a', val: fam[f].mae, text: k1(fam[f].mae) }, { cls: 'b', val: fam[f].mae_ref, text: k1(fam[f].mae_ref) }], max));
      });
      box.appendChild(fb);
    }
    var srch = v.search && list(v.search.leaderboard).length && v.search.previous_id ? v.search : null;
    if (srch) {
      var dName = function (r) { return r.id === srch.previous_id ? r.id + ' ' + pvName + ', retrained' : r.id === srch.version_reference_id ? r.id + ' ' + r.name + ', retrained' : r.id + ' ' + r.name + (r.settings && r.settings !== 'default' ? ', ' + r.settings : ''); };
      var tcCell = function (r) { return h('span', null, k2(r.tc_mae), h('br'), h('span', { class: 'dt-cell-sub dt-wrap', text: 'SC ' + k2(r.sc_mae).replace(' ', '\u00a0') })); };
      if (r4) {
        box.appendChild(h('p', { class: 'dt-sub', text: 'Round ' + v.round + ': designs the AI agent proposed, next to ' + pvName + (rl.reference_version ? ', Hurricane ' + rl.reference_version : '') + ' and the baseline retrained on the same folds. Called unlikely: trained without a whole family, the share of its superconductors given a chance under one half, averaged over the four families (not known is not counted); false alarms: held-out compounds with no superconductivity record, sent to Hurricane by Radar, given at least an even chance; rule: whether the design passed every test of the release rule.' }));
        box.appendChild(smallTable(['Design', 'Tc error', 'False alarms', 'Called unlikely', 'Rule'], list(srch.leaderboard).map(function (r) {
          return [dName(r), tcCell(r), pct(r.false_alarms), pct(r.dismissed), r.id === srch.previous_id || r.id === srch.reference_id || r.id === srch.version_reference_id ? '—' : r.passed ? 'passed' : 'failed'];
        })));
        box.appendChild(h('p', { class: 'note', text: hurRelNote4(v, rl, pv, pvName) }));
      } else if (rl) {
        box.appendChild(h('p', { class: 'dt-sub', text: 'Round ' + v.round + ': designs the AI agent proposed, next to ' + pvName + ' and the baseline retrained on the same folds. Tc error for all compounds, and for the superconducting ones below it; false alarms: held-out compounds with no superconductivity record, sent to Hurricane by Radar, that a design gives at least an even chance; rule: whether it passed every test of the release rule.' }));
        box.appendChild(smallTable(['Design', 'Tc error', 'False alarms', 'Rule'], list(srch.leaderboard).map(function (r) {
          return [dName(r), tcCell(r), pct(r.false_alarms), r.id === srch.previous_id || r.id === srch.reference_id ? '—' : r.passed ? 'passed' : 'failed'];
        })));
        box.appendChild(h('p', { class: 'note', text: hurRelNote(v, rl, pv, pvName) }));
      } else {
        box.appendChild(h('p', { class: 'dt-sub', text: 'Round ' + v.round + ': designs the AI agent proposed, next to ' + pvName + ' and the baseline retrained on the same folds. Tc error for all compounds, and for the superconducting ones below it; better folds: against ' + pvName + '.' }));
        box.appendChild(smallTable(['Design', 'Tc error', 'Better folds'], list(srch.leaderboard).map(function (r) {
          return [dName(r), tcCell(r), r.id === srch.previous_id || r.id === srch.reference_id ? '—' : (r.folds_better_previous || 0) + ' of 5'];
        })));
        box.appendChild(h('p', { class: 'note', text: v.status === 'adopted' ? 'Released as Hurricane ' + v.version + ': better than ' + pvName + ' on average and in ' + (pv ? pv.folds_better : '?') + ' of 5 folds' +
          (pv && typeof pv.sc_mae === 'number' && sc.sc_mae <= pv.sc_mae ? ', and on the superconducting entries too.' : '.')
          : 'Not released, so ' + (pvName || 'the previous version') + ' stays in use.' + (v.rule ? ' The rule: ' + v.rule + '.' : '') }));
      }
    }
    if (r4) {
      var pvC = pvName || 'Before', refC = rl.reference_version ? 'Hurricane ' + rl.reference_version : '—', f3 = function (x) { return typeof x === 'number' ? x.toFixed(3) : '—'; };
      box.appendChild(h('p', { class: 'dt-sub', text: 'Outside the training data: false alarms, and what happens to a family it has never seen.' }));
      var verHead = function (t) { var m = /^Hurricane (\S+)$/.exec(t); return m ? h('span', null, h('span', { class: 'dt-hide-narrow', text: 'Hurricane ' }), m[1]) : t; };
      box.appendChild(smallTable(['Test', verHead('Hurricane ' + v.version), verHead(pvC), verHead(refC)], [
        ['A left-out family’s superconductors called unlikely', pct(rl.dismissed), pct(rl.dismissed_previous), pct(rl.dismissed_reference)],
        ['False alarms: compounds with no record, sent by Radar, given an even chance or more', pct(rl.false_alarms), pct(rl.false_alarms_previous), pct(rl.false_alarms_reference)],
        ['Compounds with no record, sent by Radar, marked not known (abstained)', pct(rl.unknown_sent), pct(0), pct(0)],
        ['Held-out 3DSC entries given a chance', pct(rl.coverage), pct(rl.coverage_previous), '—'],
        ['Brier score of the chance on 3DSC (lower is better)', f3(rl.brier), f3(rl.brier_previous), '—'],
        ['Change of the chance when a 3DSC compound’s structure comes from JARVIS' + (typeof rl.n_matched === 'number' ? ' (' + fmtInt(rl.n_matched) + ' compounds)' : ''), hurSigned(rl.shift), hurSigned(rl.shift_previous), '—']
      ]));
      box.appendChild(h('p', { class: 'note', text: 'Not known: ' + (rl.abstain && rl.abstain !== 1 ? 'more than ' + rl.abstain + ' times as far from every training compound, in the model’s own inputs, as 95% of the training compounds are from their nearest neighbour in another chemical-system group. ' :
        'further from every training compound, in the model’s own inputs, than 95% of the training compounds are from their nearest neighbour in another chemical-system group, which is when the app marks a candidate as outside the training data. ') +
        (bg && typeof bgN === 'number' ? 'The classifier learns from ' + fmtInt(bgN) + ' of the ' + fmtInt(bg.n) + ' compounds with no record in Hurricane’s screening pool' + (bg.radius ? ', those within ' + (bg.radius === 1 ? 'the training data' : bg.radius + ' times that distance') : '') + ', given weak zero labels, following the background-label approach of Konno et al. (2021). Missing records are not experimental negatives. “False alarms” here denotes scores above the threshold on this unlabelled background, not measured experimental false positives.' : '') }));
      if (rl.caveat) box.appendChild(h('p', { class: 'note', text: rl.caveat }));
    } else if (rl) {
      var pvCol = pvName || 'Before';
      box.appendChild(h('p', { class: 'dt-sub', text: 'Outside the training data: how often it raises a false alarm, and what that costs.' }));
      box.appendChild(smallTable(['Test', 'Hurricane ' + v.version, pvCol], [
        ['False alarms: compounds with no record, sent by Radar, given an even chance or more', pct(rl.false_alarms), pct(rl.false_alarms_previous)],
        ['The same for all compounds with no record', pct(rl.false_alarms_all), pct(rl.false_alarms_all_previous)],
        ['3DSC superconductors given an even chance or more', pct(rl.recall), pct(rl.recall_previous)],
        ['Brier score of the chance on 3DSC (lower is better)', typeof rl.brier === 'number' ? rl.brier.toFixed(3) : '—', typeof rl.brier_previous === 'number' ? rl.brier_previous.toFixed(3) : '—'],
        ['Change of the chance when a 3DSC compound’s structure comes from JARVIS' + (typeof rl.n_matched === 'number' ? ' (' + fmtInt(rl.n_matched) + ' compounds)' : ''), hurSigned(rl.shift), hurSigned(rl.shift_previous)]
      ].concat(rl.top && typeof rl.top.kept === 'number' ? [['Of ' + pvCol + '’s top ' + rl.top.n + ' compounds with no record, still at an even chance or more', String(rl.top.kept), String(rl.top.kept_previous)]] : [])));
      if (bg) box.appendChild(h('p', { class: 'note' }, 'The background: ' + fmtInt(bg.n) + ' JARVIS-DFT compounds from Hurricane’s screening pool' + (typeof bg.n_sent === 'number' ? ' (' + fmtInt(bg.n_sent) + ' of them sent to Hurricane by Radar)' : '') +
        ', none with a superconductivity record, counted as not superconducting' + (typeof bg.weight === 'number' ? ' at weight ' + bg.weight : '') + ', as ',
        bg.doi ? h('a', { href: 'https://doi.org/' + bg.doi, text: bg.cite || 'Konno et al. (2021)' }) : (bg.cite || 'Konno et al. (2021)'),
        ' did with crystal structures from the Crystallography Open Database. They are split into folds by chemical system, so every false alarm is counted on compounds the design never learned from, and a design must give 3DSC compounds about the same chance whether their structures come from the Materials Project or from JARVIS, so it cannot win by telling the two databases apart.'));
      if (rl.caveat) box.appendChild(h('p', { class: 'note', text: rl.caveat }));
    }
    var lofo = list(v.lofo), found = rl && lofo.some(function (r) { return typeof r.recall === 'number'; });
    var lofo4 = r4 && lofo.some(function (r) { return typeof r.dismissed === 'number'; });
    var sub2 = function (a, b, wrap) { return h('span', null, a, b !== null && b !== undefined ? h('br') : null, b !== null && b !== undefined ? h('span', { class: 'dt-cell-sub' + (wrap ? ' dt-wrap' : ''), text: b }) : null); };
    if (lofo.length && lofo4) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Leave one family out: trained without a whole family, then asked about it. Of the family’s superconductors: found, given at least an even chance; not known, too far from the training data for a chance; called unlikely, given a chance under one half' + (pvName ? ', with ' + pvName + '’s below it' : '') + '.' }));
      box.appendChild(smallTable(['Family left out', 'Error', 'Found', 'Not known', 'Called unlikely'],
        lofo.map(function (r) { return [famLabel(r.family) + ' (' + r.n + ')', sub2(k1(r.mae), 'in training ' + k1(r.mae_cv).replace(' ', '\u00a0'), true), sub2(pct(r.found), typeof r.found_previous === 'number' ? pct(r.found_previous) : null),
          pct(r.unknown), sub2(pct(r.dismissed), typeof r.dismissed_previous === 'number' ? pct(r.dismissed_previous) : null)]; })));
      var fA = hurLofoAvg(v, 'found'), fP = hurLofoAvg(v, 'found_previous'), fR = hurLofoAvg(v, 'found_reference'), uA = hurLofoAvg(v, 'unknown'), worst = hurWorstLofo(v);
      var note4 = 'Not known is not a hint that a compound superconducts: the model cannot tell.';
      if (typeof fA === 'number' && typeof uA === 'number') {
        var cmp4 = [typeof fP === 'number' && pvName ? pvName + ': ' + pct(fP) : null, typeof fR === 'number' && rl.reference_version ? 'Hurricane ' + rl.reference_version + ': ' + pct(fR) : null].filter(Boolean);
        var fewer4 = typeof rl.dismissed_previous === 'number' && rl.dismissed < rl.dismissed_previous,
          noMore4 = fA <= Math.max(typeof fP === 'number' ? fP : 0, typeof fR === 'number' ? fR : 0);
        note4 += ' Trained without a whole family, it finds ' + pct(fA) + ' of that family’s superconductors on average' + (cmp4.length ? ' (' + cmp4.join(', ') + ')' : '') +
          ' and answers “not known” for ' + pct(uA) + (fewer4 && noMore4 ? ': it calls fewer of them unlikely, but it does not find more of them.' : fewer4 ? ': it calls fewer of them unlikely.' : noMore4 ? ': it does not find more of them.' : '.');
      }
      if (worst) note4 += ' The distance does not catch every new family: ' + pct(worst.dismissed) + ' of the ' + (HUR_FAM_SC[worst.family] || famLabel(worst.family)) +
        ' are still called unlikely, because to its inputs ' + (typeof worst.unknown === 'number' && worst.unknown < 0.5 ? 'most' : 'many') + ' of them look like the families it learned from.';
      box.appendChild(h('p', { class: 'note', text: note4 + ' Finding a new family still needs physics and experiments.' }));
    } else if (lofo.length && found) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Leave one family out: trained without a whole family, then asked to predict it. Median guess: always guessing the median Tc of the other families; found: the share of the family’s superconductors given at least an even chance' + (pvName ? ', with ' + pvName + '’s below it' : '') + '.' }));
      box.appendChild(smallTable(['Family left out', 'Error', 'Median guess', 'Found'],
        lofo.map(function (r) { return [famLabel(r.family) + ' (' + r.n + ')', h('span', null, k1(r.mae), h('br'), h('span', { class: 'dt-cell-sub', text: 'in training ' + k1(r.mae_cv) })), k1(r.mae_median),
          h('span', null, pct(r.recall), typeof r.recall_previous === 'number' ? h('br') : null, typeof r.recall_previous === 'number' ? h('span', { class: 'dt-cell-sub', text: pct(r.recall_previous) }) : null)]; })));
      if (lofo.some(function (r) { return typeof r.recall === 'number' && typeof r.recall_previous === 'number' && r.recall < r.recall_previous; }))
        box.appendChild(h('p', { class: 'note', text: 'Counting compounds with no record as not superconducting makes Hurricane more cautious with a family it has never seen, so it finds fewer of that family’s superconductors: the price of fewer false alarms.' }));
    } else if (lofo.length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Leave one family out: trained without a whole family, then asked to predict it. Median guess: always guessing the median Tc of the other families; in training: the error with the family in training.' }));
      box.appendChild(smallTable(['Family left out', 'Error', 'Median guess', 'In training'],
        lofo.map(function (r) { return [famLabel(r.family) + ' (' + r.n + ')', k1(r.mae), k1(r.mae_median), k1(r.mae_cv)]; })));
    }
    if (lofo.length) {
      var flat = lofo.filter(function (r) { return r.mae >= 0.9 * r.mae_median; }).map(function (r) { return hurFamText(r.family); });
      if (flat.length) box.appendChild(h('p', { class: 'note', text: 'For ' + flat.join(', ').replace(/, ([^,]*)$/, ' and $1') +
        ', the error without any member of the family in training is about that of always guessing the median Tc of the other families. These tests do not establish reliable discovery of new high-Tc families; additional physical information and independent experiments are needed.' }));
    }
    var imp = list(v.importance).slice(0, 8);
    if (imp.length) {
      var ul = h('ul', { class: 'dt-chips' });
      imp.forEach(function (i) { ul.appendChild(h('li', null, featLabel(i.name), h('span', { text: ' +' + (+i.gain).toFixed(2) + ' K' }))); });
      box.appendChild(h('p', { class: 'dt-sub', text: 'What it relies on most (how much the error grows when one input is shuffled):' }));
      box.appendChild(ul);
    }
    var an = v.anchors;
    if (an && list(an.table).length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Later measurements it never trained on, graded by reliability:' }));
      box.appendChild(smallTable(['Material', 'Measured', 'Predicted', 'Grade'], list(an.table).map(function (r) {
        var use = r.unknown === true ? 'abstained' : r.use === 'score' ? 'scored' : r.use === 'exclude' ? 'left out' : 'shown';
        var pr = r.unknown === true ? 'unknown' : typeof r.pred === 'number' ? r.pred.toFixed(r.pred >= 10 ? 0 : 1) + ' K' : '—';
        // Classifier outputs are model scores; abstention takes precedence over saved raw outputs.
        var ch = r.unknown === true ? 'not known: outside the training data' + (typeof r.p_sc_previous === 'number' ? ', previous score ' + pct(r.p_sc_previous) : '') :
          rl && typeof r.p_sc === 'number' ? 'classifier score ' + pct(r.p_sc) + (typeof r.p_sc_previous === 'number' ? ', previous score ' + pct(r.p_sc_previous) : '') : '';
        return [h('span', { class: 'dt-formula', title: r.note || '', text: hurSub(r.name) }), r.tc_exp === null || r.tc_exp === undefined ? '—' : r.tc_exp + ' K',
          ch ? h('span', null, pr, h('br'), h('span', { class: 'dt-cell-sub dt-wrap', text: ch })) : pr, h('span', { class: 'dt-wrap', text: r.status + ', ' + use })];
      })));
      if (typeof an.mae === 'number') box.appendChild(h('p', { class: 'note', text: 'Historical raw-output diagnostic: ' + an.n_scored + ' entries, average error ' + k2(an.mae) + (list(an.table).some(function (r) { return r.use === 'score' && r.unknown === true; }) ? '. This saved diagnostic includes internal outputs for abstained entries; those entries are displayed as unknown here' : '') + (an.scored_as_check ? '.' : '; too few to count as a check yet, so they are shown, not used to choose a design.') }));
    }
    if (list(v.changes).length) box.appendChild(h('p', { class: 'note', text: 'Design: ' + prettyMath(list(v.changes).join('; ')) + '.' }));
    box.appendChild(h('p', { class: 'note dt-data' }, 'Data: ', h('a', { href: 'https://doi.org/10.1038/s41597-023-02721-y', text: '3DSC' }),
      ' (T. Sommer et al., Sci. Data 10, 816 (2023)), which matches the SuperCon database (NIMS) to Materials Project structures, used under ',
      h('a', { href: 'https://creativecommons.org/licenses/by/4.0/', text: 'CC BY 4.0' }), '. We filter it, group folds by the Materials Project chemical-system label and add features; the models and predictions are ours.'));
    return box;
  };


  const calibrationDetails = function calibrationDetails(c) {
    var sc = c.scores, box = h('div', { class: 'dt-block' }), dd = c.data || {};
    box.appendChild(h('h3', { class: 'dt-title' }, 'Storm against measured Tc',
      // once a later Storm is released (round 4), round 3's Storm 3.0 is no longer the one in use
      h('span', { class: 'mf-status', text: c.status === 'adopted' ? 'Storm ' + c.version + (stormEns() ? ', replaced by ' + stormVersionInUse() : ' in use') : 'calibration experimental' })));
    box.appendChild(h('p', { class: 'dt-lead', text: 'Storm learns from DFT-computed Tc. Round 3 checked it against ' + (dd.n_matched || '?') + ' conventional materials with measured Tc (' +
      (dd.n_sc || '?') + ' superconducting) that are also in its training set, and taught a calibration step to map its prediction to the measured value. Storm’s inputs here are its predictions for materials it never saw, never the DFT labels.' }));
    var max = Math.max(sc.dft_mae || 0, sc.mae_raw || 0, sc.mae || 0);
    var fb = h('div', { class: 'dt-chart', role: 'img', 'aria-label': 'Average error against measured Tc' }, h('p', { class: 'dt-sub', text: 'Average error against measured Tc:' }));
    fb.appendChild(barRow('DFT labels', 'what Storm learns from', [{ cls: 'b', val: sc.dft_mae, text: k2(sc.dft_mae) }], max));
    fb.appendChild(barRow('Storm 1.0', 'uncalibrated', [{ cls: 'b', val: sc.mae_raw, text: k2(sc.mae_raw) }], max));
    fb.appendChild(barRow('Calibrated', c.method ? c.method.name : '', [{ cls: 'a', val: sc.mae, text: k2(sc.mae) }], max));
    box.appendChild(fb);
    box.appendChild(h('p', { class: 'note', text: (c.status === 'adopted' ? 'Better than uncalibrated in ' + sc.folds_better + ' of ' + list(sc.folds).length + ' folds, so it was released as Storm ' + c.version + '.'
      : 'Better in ' + sc.folds_better + ' of ' + list(sc.folds).length + ' folds; a calibration is released only with at least 4 of 5, so Storm 1.0 stays in use.') }));
    var ph = c.physics && (c.physics.K4 || c.physics.K3);
    if (ph) box.appendChild(h('p', { class: 'note', text: 'Physics fit on all matched materials: λ scaled by ' + ph.alpha + ', effective μ* = ' + ph.mu_star +
      (ph.gamma ? ', raised by ' + ph.gamma + ' times the share of magnetic 3d atoms' : '') + '.' }));
    var sf = list(c.shortfalls).slice(0, 6);
    if (sf.length) {
      box.appendChild(h('p', { class: 'dt-sub', text: 'Largest shortfalls, where measured Tc is far above the calibrated prediction:' }));
      box.appendChild(smallTable(['Material', 'Measured', 'Calibrated', 'DFT label'], sf.map(function (r) {
        return [hurSub(r.name), k1(r.tc_exp), k1(r.calibrated), k1(r.dft)];
      })));
      box.appendChild(h('p', { class: 'note', text: 'Causes include pairing that isotropic Allen–Dynes misses (MgB₂’s two gaps), a different polymorph in the DFT set, or pairing that phonons alone may not explain; these are the leads for the mechanism stage.' }));
    }
    box.appendChild(h('p', { class: 'note dt-data' }, 'Data: DFT electron–phonon calculations from ', h('a', { href: 'https://alexandria.icams.rub.de/', text: 'Alexandria' }),
      ' and measured Tc from ', h('a', { href: 'https://doi.org/10.1038/s41597-023-02721-y', text: '3DSC' }), ', both under ',
      h('a', { href: 'https://creativecommons.org/licenses/by/4.0/', text: 'CC BY 4.0' }), '; we match the two by composition.'));
    return box;
  };

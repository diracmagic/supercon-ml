'use strict';
// model-cards: shared lexical function definitions; no startup side effects.

  // The version of Storm in use: the latest adopted one (ai_model.current), never the one picked in the demo.
  const stormInUse = function stormInUse(d) {
    var am = d && d.ai_model;
    var vs = am ? list(am.versions).filter(function (v) { return v && v.spec && v.scores; }) : [];
    if (!vs.length) return null;
    return vs.filter(function (v) { return v.version === am.current; })[0] || vs[vs.length - 1];
  };

  const modelFamily = function modelFamily(d) {
    var sv = stormInUse(d), sname = (d && d.ai_model && d.ai_model.name) || 'Storm';
    var mae = sv && typeof sv.scores.tc_mae === 'number' ? sv.scores.tc_mae.toFixed(2) + ' K' : '';
    // Storm 3.0 and later: the version in use, calibrated to measured Tc (ai_model.calibration).
    var cal = sv && sv.status === 'adopted' && sv.version === ((d && d.ai_model && d.ai_model.current) || sv.version) ? stormCal() : null;
    var calN = cal && cal.data && typeof cal.data.n_matched === 'number' ? fmtInt(cal.data.n_matched) + ' ' : '';
    var ens = cal ? stormEns() : null, unc = ens ? stormUnc() : null;
    if (ens) return [
      { id: 'storm', name: 'Storm', on: true, live: true, status: sname + ' ' + (unc ? unc.version : ens.version) + ' in use', role: 'Conventional superconductors, paired by phonons',
        text: 'Combines boosted trees that learn from about 7,600 materials whose electron–phonon coupling λ and phonon scale ω_log have been computed (the Alexandria set) with a crystal-graph network that learns from the atoms and their neighbours: ' +
          ens.scores.tc_mae.toFixed(2) + ' K off on average against the computed Tc of materials it never saw' + (typeof ens.scores.reference_mae === 'number' ? ', against ' + ens.scores.reference_mae.toFixed(2) + ' K for the trees alone' : '') +
          '. Calibrated to measured Tc, it is off by ' + ens.calibration.mae.toFixed(2) + ' K against experiment.' +
          (unc ? ' Every prediction comes with a 90% range: for materials it never saw, the range held the computed Tc ' + Math.round(100 * unc.scores.coverage) + '% of the time, and half of the ranges are narrower than ' + unc.scores.median_width.toFixed(1) + ' K.' : '') +
          ' Our AI-assisted implementation uses published methods (see Cite); a new version is released only if it beats the current one on held-out materials and holds up against replicated Tc measurements.',
        act: ['See how Storm works', function () { setView('demos'); selectDemo('storm'); window.scrollTo(0, 0); }] },
      hurFamilyEntry(),
      radFamilyEntry()
    ];
    return [
      { id: 'storm', name: 'Storm', on: true, live: !!sv,
        status: cal ? sname + ' ' + cal.version + ' in use' : sv ? sname + ' ' + sv.version + ' in use' : 'In use',
        role: 'Conventional superconductors, paired by phonons',
        text: 'Learns from about 7,600 materials whose electron–phonon coupling λ and phonon scale ω_log have been computed (the Alexandria set) and predicts Tc in under a second' +
          (mae ? ', ' + mae + ' off on average against the computed Tc of materials it never saw' : '') +
          (cal ? '. A calibration learned from ' + calN + 'materials with measured Tc then maps its prediction to experiment: off by ' + cal.scores.mae.toFixed(2) + ' K' +
            (typeof cal.scores.mae_raw === 'number' ? ', against ' + cal.scores.mae_raw.toFixed(2) + ' K uncalibrated' : '') : '') +
          '. Our AI-assisted implementation uses published methods (see Cite); a new version is released only if it beats the current one on held-out materials and holds up against replicated Tc measurements.',
        act: ['See how Storm works', function () { setView('demos'); selectDemo('storm'); window.scrollTo(0, 0); }] },
      hurFamilyEntry(),
      radFamilyEntry()
    ];
  };

  // Radar's entry follows its own results (progress.json "radar").
  const radFamilyEntry = function radFamilyEntry() {
    var ri = radInfo(), role = 'Decides which model to ask';
    if (!ri) return { id: 'radar', name: 'Radar', status: 'Planned', role: role,
      text: 'Reads a material’s composition and structure, estimates whether phonons can account for its pairing, and sends it to Storm or Hurricane. When the call is close it says so and shows both predictions. Comparing where the two disagree is also a clue to the pairing mechanism.' };
    var sc = ri.v.scores || {}, dd = ri.data || {}, inUse = !!ri.rd.current;
    var cu = list(ri.v.lofo).filter(function (r) { return r.family === 'cuprate'; })[0];
    return { id: 'radar', name: 'Radar', on: inUse, live: true, status: inUse ? radTitle(ri) + ' in use' : radTitle(ri) + ' experimental', role: role,
      text: 'Reads a material’s composition and crystal structure and gives the probability that it belongs to an unconventional family, then sends it to Hurricane or Storm. It learns from ' +
        fmtInt(dd.n) + ' SuperCon entries in 3DSC. On held-out chemical-system groups its balanced accuracy is ' + radPct(sc.balanced_accuracy) + ', against ' +
        radPct(sc.reference_balanced_accuracy) + ' for a composition-only baseline.' + (cu ? ' Trained without any cuprate, it still sends ' + radPct(cu.right) + ' of cuprates to Hurricane.' : '') + ' Sources and implementation differences are listed under Cite.',
      act: ['See how Radar works', function () { setView('demos'); selectDemo('radar'); window.scrollTo(0, 0); }] };
  };

  // Hurricane's entry follows its own results (progress.json "hurricane").
  const hurFamilyEntry = function hurFamilyEntry() {
    var hi = hurInfo(), role = 'Unconventional superconductors: cuprates, nickelates, iron-based, heavy-fermion and more';
    if (!hi) return { id: 'hurricane', name: 'Hurricane', status: 'Up next', role: role,
      text: 'No first-principles theory gives their Tc, so Hurricane will learn from measured Tc in the literature. Every measurement is graded as replicated, single report, preprint, retracted or refuted: unconfirmed claims count less and retracted ones not at all. Our AI agent will design it the same way as Storm.' };
    var sc = hi.v.scores || {}, dd = hi.data || {}, inUse = !!hi.hu.current;
    if (hurTW(hi.v)) {   // round 9 on: the NIMS datasheet, checked on time windows
      var rl9 = hurRel(hi.v) || {}, near = (((hi.v.temporal.families.cuprate || {}).difference || {})['data-R1'] || {}).met === true;
      return { id: 'hurricane', name: 'Hurricane', on: inUse, live: true, status: inUse ? hurTitle(hi) + ' in use' : hurTitle(hi) + ' experimental', role: role,
        text: 'Learns from ' + fmtInt(dd.n) + ' measured compositions in the NIMS SuperCon datasheet, ' + fmtInt(dd.n_negative) + ' of them measured not to superconduct, and reads the composition only. ' +
          'Asked about cuprate parent compounds first reported in the five years after its training data end, it ranks them by Tc with a rank correlation of ' + hurR2(hurRank(hi.v, 'cuprate', 'data')) +
          ', against ' + hurR2(hurRank(hi.v, 'cuprate', 'previous')) + ' for the same recipe on the previous model’s data and ' + hurR2(hurRank(hi.v, 'cuprate', 'R1')) + ' for the Tc of the nearest known compound, which it ' +
          (near ? 'beats' : 'does not clearly beat') + '. It gives a chance only to compounds near its training data and answers “not known” further away: of the held-out compounds with no superconductivity record that Radar sends it, it answers “not known” for ' +
          radPct(rl9.unknown_sent) + ' and gives ' + (rl9.false_alarms === 0 ? 'none' : radPct(rl9.false_alarms)) + ' at least an even chance. Sources and implementation differences are listed under Cite.',
        act: ['See how Hurricane works', function () { setView('demos'); selectDemo('hurricane'); window.scrollTo(0, 0); }] };
    }
    return { id: 'hurricane', name: 'Hurricane', on: inUse, live: true, status: inUse ? hurTitle(hi) + ' in use' : hurTitle(hi) + ' experimental', role: role,
      text: 'Learns from ' + fmtInt(dd.n) + ' catalogued Tc values (SuperCon with Materials Project structures, via 3DSC), including zero labels whose measurement limits are not established here. For held-out chemical-system groups it is off by ' +
        hurK(sc.tc_mae) + ' K on average, against ' + (hi.v.previous && typeof hi.v.previous.tc_mae === 'number' ? hurK(hi.v.previous.tc_mae) + ' K for Hurricane ' + hi.v.previous.version + ' and ' : '') +
        hurK(sc.reference_mae) + ' K for a composition-only baseline.' +
        // round 3 on: fewer false alarms outside the training data (hurRel in details.js)
        (hur4(hurRel(hi.v)) ? ' It gives a chance only to compounds near its training data and answers “not known” further away. In cross-validation it gives ' +
          (hurRel(hi.v).false_alarms === 0 ? 'none' : radPct(hurRel(hi.v).false_alarms)) + ' of the held-out compounds with no superconductivity record at least an even chance, and trained without a whole family it calls ' + radPct(hurRel(hi.v).dismissed) +
          ' of that family’s superconductors unlikely, against ' + radPct(hurRel(hi.v).dismissed_previous) + ' for Hurricane ' + ((hi.v.previous && hi.v.previous.version) || 'before') +
          (typeof hurLofoAvg(hi.v, 'unknown') === 'number' && typeof hurLofoAvg(hi.v, 'found') === 'number' ? '; for ' + radPct(hurLofoAvg(hi.v, 'unknown')) + ' of them it answers “not known”, and it gives ' +
            radPct(hurLofoAvg(hi.v, 'found')) + ' at least an even chance' + (typeof hurLofoAvg(hi.v, 'found_reference') === 'number' && hurRel(hi.v).reference_version ?
              ', against ' + radPct(hurLofoAvg(hi.v, 'found_reference')) + ' for Hurricane ' + hurRel(hi.v).reference_version : '') : '') + '.' :
          hurRel(hi.v) ? ' It also learns from compounds with no superconductivity record, so of the compounds like those it screens it gives ' +
          (hurRel(hi.v).false_alarms === 0 ? 'none' : radPct(hurRel(hi.v).false_alarms)) + ' at least an even chance of superconducting, against ' + radPct(hurRel(hi.v).false_alarms_previous) + ' for Hurricane ' + ((hi.v.previous && hi.v.previous.version) || 'before') + '.' : '') + ' Sources and implementation differences are listed under Cite.',
      act: ['See how Hurricane works', function () { setView('demos'); selectDemo('hurricane'); window.scrollTo(0, 0); }] };
  };

  // progress.json may update a model's status without a new app release: "model_family": [{ "id": "hurricane", "status": "In design" }].
  // Training rounds write these for apps that cannot read a model's own results, so an entry built from those results ("live")
  // ignores them unless the override says "force": true; otherwise an old override could name a version that is no longer in use.
  const familyOverride = function familyOverride(d, m) {
    var o = list(d && d.model_family).filter(function (x) { return x && x.id === m.id; })[0];
    return o && (!m.live || o.force === true) ? o : {};
  };

  const renderModels = function renderModels(d) {
    var el = $('#models-card');
    if (!el) return;
    clear(el);
    var ul = h('ul', { class: 'model-family' });
    modelFamily(d).forEach(function (m) {
      var o = familyOverride(d, m);
      var status = typeof o.status === 'string' && o.status ? o.status : m.status;
      var on = typeof o.active === 'boolean' ? o.active : !!m.on;
      var g = h('span', { class: 'mf-glyph' });
      g.innerHTML = MODEL_GLYPH[m.id] || '';
      ul.appendChild(h('li', { class: on ? 'on' : null },
        h('div', { class: 'mf-head' }, g,
          h('div', { class: 'mf-title' }, h('h3', { text: m.name }), h('span', { class: 'mf-status', text: status }))),
        richText(h('p', { class: 'mf-role' }), m.role),
        richText(h('p', { class: 'mf-text' }), typeof o.text === 'string' && o.text ? o.text : m.text),
        m.act ? h('button', { class: 'btn small mf-act', type: 'button', onclick: m.act[1] }, m.act[0]) : null));
    });
    append(el, [
      cardHead('Our models', 'Conventional and unconventional superconductors follow different physics and come with different data, so each gets its own model, and a third decides which one to ask.'),
      ul
    ]);
  };

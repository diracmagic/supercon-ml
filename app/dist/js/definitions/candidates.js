'use strict';
// candidates: shared lexical function definitions; no startup side effects.


  // the block that holds a list: the screen block itself for Storm's, its "hurricane" block for Hurricane's
  const candBlock = function candBlock(sc, kind) {
    if (!sc || typeof sc !== 'object') return null;
    return kind === 'hurricane' ? (sc.hurricane && typeof sc.hurricane === 'object' ? sc.hurricane : null) : sc;
  };

  const candRows = function candRows(sc, kind) {
    var b = candBlock(sc, kind);
    return candidateData.partitionCandidates(list(b && b.candidates).filter(function (c) {
      return c && typeof c.formula === 'string' && c.formula.trim();
    }), kind);
  };

  const candCurrentRows = function candCurrentRows(sc, kind) {
    var got = candRows(sc, kind);
    if (candState.archive) got.rows = got.reported;
    if (kind !== 'hurricane') got.rows = candidateData.trackRows(got.rows, sc && sc.tracks, candState.track);
    got.rows = candidateData.sortByPredictedTc(got.rows, kind);
    return got;
  };

  const candId = function candId(c) { return String(c.id || c.formula); };

  const candK = function candK(v) { return typeof v === 'number' && isFinite(v) ? (v >= 100 ? Math.round(v) : v.toFixed(1)) + ' K' : '—'; };

  const candNum = function candNum(v) { return typeof v === 'number' && isFinite(v); };

  // just under one half shows a decimal, so that a chance below an even chance never reads as 50%
  const candPct = function candPct(p) { return candNum(p) ? (p < 0.01 ? 'under 1%' : p > 0.99 ? 'over 99%' : p < 0.5 && p >= 0.495 ? (100 * p).toFixed(1) + '%' : Math.round(100 * p) + '%') : '—'; };

  // the Hurricane version that screened this list (its leave-one-family-out shares), if the live data has it
  const candHurVersion = function candHurVersion(block) {
    var hi = hurInfo(), want = block && String(block.model || '').replace(/^Hurricane\s*/, '');
    return hi && want ? list(hi.versions).filter(function (x) { return x.version === want; })[0] || null : null;
  };

  const candRange = function candRange(c) { return candNum(c.lo) && candNum(c.hi) ? c.lo.toFixed(1) + '–' + candK(c.hi) : ''; };

  // Hurricane's conditional Tc must be explicit: its joint chance-and-Tc score is not a fallback.
  const candTcSc = function candTcSc(c) { return candidateData.predictedTc(c, 'hurricane'); };

  const candChecked = function candChecked(c) { var k = candidateData.checkFor(c); return k && typeof k === 'object' && CHECK_LABEL[k.kind] ? k : null; };

  const candWorthTests = function candWorthTests(c, hur) {
    var k = candChecked(c), dft = !!(k && k.kind === 'dft' && k.superconducts !== false && candNum(k.tc) && k.tc >= MCMILLAN_K), tc = hur ? candTcSc(c) : c.tc;
    return {
      above: candNum(tc) && tc >= MCMILLAN_K && (hur || dft || (candNum(c.lo) && c.lo >= MCMILLAN_K)),
      likely: candNum(c.p_sc) && c.p_sc >= WORTH_P,
      inside: candNum(c.novelty) && c.novelty <= 1 && c.outside !== true,
      made: c.icsd === true || (dft && candNum(c.ehull) && c.ehull <= WORTH_HULL),
      settled: !!(k && (k.superconducts === false || (candNum(k.tc) && k.tc < MCMILLAN_K)))
    };
  };

  const candMcm = function candMcm(c, hur) {
    var k = candChecked(c);
    if (k && k.kind === 'experiment' && k.superconducts !== false && candNum(k.tc) && k.tc >= MCMILLAN_K && k.confirmed === true &&
      typeof k.ref === 'string' && REFS[k.ref] && typeof k.ref2 === 'string' && REFS[k.ref2]) return 'confirmed';
    var t = candWorthTests(c, hur);
    return t.above && t.likely && t.inside && t.made && !t.settled ? 'worth' : '';
  };

  const candMcmAll = function candMcmAll(sc) {
    var out = [];
    CAND_KINDS.forEach(function (kind) {
      candRows(sc, kind).rows.forEach(function (c) { var lv = candMcm(c, kind === 'hurricane'); if (lv) out.push({ kind: kind, c: c, level: lv }); });
    });
    return out;
  };

  const candMcmChips = function candMcmChips(list) {
    var chips = h('div', { class: 'cand-mcm-chips' });
    list.slice(0, 8).forEach(function (x) {
      var c = x.c, tc = x.level === 'confirmed' ? candChecked(c).tc : x.kind === 'hurricane' ? candTcSc(c) : c.tc;
      chips.appendChild(h('button', { class: 'btn small cand-mcm-chip' + (x.level === 'confirmed' ? ' is-done' : ''), type: 'button', onclick: function () { candGo(x.kind, candId(c)); } },
        hurSub(c.formula) + ' · ' + candK(tc) + (x.level === 'worth' ? ' predicted' : ' measured')));
    });
    return chips;
  };

  const candMcmBanner = function candMcmBanner(sc) {
    var all = candMcmAll(sc);
    if (!all.length) return null;
    var done = all.filter(function (x) { return x.level === 'confirmed'; }), worth = all.filter(function (x) { return x.level === 'worth'; }), out = [];
    if (done.length) {
      out.push(h('div', { class: 'cand-mcm-banner is-done', role: 'note' },
        h('p', null, h('b', { text: done.length === 1 ? 'A new superconductor above the McMillan limit.' : done.length + ' new superconductors above the McMillan limit.' }), ' ',
          (done.length === 1 ? 'One of our candidates superconducts' : done.length + ' of our candidates superconduct') + ' above about 40 K, long thought to be the ceiling for conventional superconductors: measured, published and reproduced by another group (',
          h('a', { href: refUrl(REFS.mcmillan1968), text: REFS.mcmillan1968.t }), ').'), candMcmChips(done)));
    }
    if (worth.length) {
      out.push(h('div', { class: 'cand-mcm-banner', role: 'note' },
        h('p', null, h('b', { text: 'Worth an experiment.' }), ' ',
          (worth.length === 1 ? 'One candidate passes' : worth.length + ' candidates pass') + ' every test we set before suggesting a measurement: a predicted Tc above the McMillan limit of about 40 K, long thought to be the ceiling for conventional superconductors (',
          h('a', { href: refUrl(REFS.mcmillan1968), text: REFS.mcmillan1968.t }), '); more likely than not to superconduct; inside its model’s training data; and made before. ' +
          (worth.length === 1 ? 'It is still a prediction, and we suggest it' : 'They are still predictions, and we suggest them') + ' to experimental groups: if you can measure ' + (worth.length === 1 ? 'it' : 'one') + ', ',
          contactLink('write to us', 'experiment'), '.'), candMcmChips(worth)));
    }
    return out;
  };

  // open a list at one candidate (the banner's buttons)
  const candGo = function candGo(kind, id) {
    if (CAND_KINDS.indexOf(kind) < 0) return;
    if (kind !== candState.kind) { candState.kind = kind; candState.all = false; store.set('cand-kind', kind); }
    var sc = state.data && state.data.screen, got = candRows(sc, kind);
    candState.archive = got.reported.some(function (c) { return candId(c) === id; });
    if (kind === 'storm' && !candCurrentRows(sc, kind).rows.some(function (c) { return candId(c) === id; })) {
      candState.track = candidateData.trackForId(candState.archive ? got.reported : got.rows, sc && sc.tracks, id, candState.track);
      store.set('cand-track', candState.track);
    }
    candState.sel[kind] = id;
    candState.key = '';
    renderCandidates(state.data);
    var v = $('#cand-viewer');
    if (v) v.scrollIntoView({ block: 'start', behavior: motionOK() ? 'smooth' : 'auto' });
  };

  // the remarks that go with every candidate: whether it was ever made, how wide its range is, how far its chance can be
  // trusted, how close it is to what the model learned from, whether anything has checked it, and when we first listed it
  const candRemarks = function candRemarks(c, hur, block) {
    var out = [], model = hur ? 'Hurricane' : 'Storm', range = candRange(c), ck = (block && block.check) || {};
    out.push(c.icsd === true ? ['ok', 'Made before: its structure is in ICSD, so the compound has been synthesized.'] :
      ['warn', 'Computed structure: not marked as an ICSD structure in this dataset; its synthesis history remains unresolved.']);
    if (range) {
      var wide = (c.hi + 1) / (c.lo + 1) >= 5;
      out.push([wide ? 'warn' : 'info', (wide ? 'Very wide range: the 90% range for its ' + (hur ? 'Tc if it superconducts' : 'DFT Tc') + ' is ' + range + ', so ' + model + ' is far from sure.' :
        'The 90% range for its ' + (hur ? 'Tc if it superconducts' : 'DFT Tc') + ' is ' + range + '.')]);
    }
    if (candNum(c.p_sc)) {
      out.push(['warn', 'Chance it superconducts: ' + candPct(c.p_sc) + '. ' + (hur ?
        'It is calibrated on compounds in 3DSC, the families Hurricane learned from' + (block && block.background ? ', and on compounds with no superconductivity record' : '') +
          (c.outside ? '; this compound lies outside the families, so here the chance says little.' :
          c.nearest ? ', and holds only for compounds like them.' : '; for a compound unlike them it says little.') :
        'It is calibrated on ' + (candNum(ck.n) ? fmtInt(ck.n) + ' ' : '') + 'known materials in 3DSC, most of them measured because someone expected them to superconduct, so for a new material it is likely lower' +
          (c.outside ? '; this one also lies outside Storm’s training data, so here it says little.' : '.'))]);
    } else out.push(['warn', model + ' gives no chance of superconducting for this candidate yet.']);
    if (hur && candidateData.disagreement(c)) out.push(['warn', candidateData.disagreement(c)]);
    if (c.nearest && typeof c.nearest.formula === 'string') {
      var near = hurSub(cText(c.nearest.formula, 60).replace(/([A-Z][a-z]?)1(?![\d.])/g, '$1')) + (candNum(c.nearest.tc) ? ' (' + (hur ? 'measured' : 'DFT') + ' Tc ' + candK(c.nearest.tc) + ')' : '');
      out.push([c.outside ? 'warn' : 'info', c.outside ? 'Outside the training data: even the most similar material ' + model + ' learned from, ' + near + ', is far from it, so this prediction is an extrapolation.' :
        'The most similar material ' + model + ' learned from is ' + near + '.']);
    } else if (hur) out.push(['warn', 'Many compounds on this list are unlike anything Hurricane learned from; this one has not been compared with its training data yet.']);
    var k = candChecked(c);
    out.push(k && typeof k === 'object' && CHECK_LABEL[k.kind] ? ['info', 'Checked: ' + candCheckText(k) + '.'] : ['warn', 'No matching DFT or experimental test is recorded here.']);
    if (k && typeof k === 'object' && CHECK_LABEL[k.kind]) {
      candidateData.checkEvidenceLines(k).forEach(function (text) { out.push(['literature', text]); });
      if (candCheckSource(k)) out.push(['source', k]);
    }
    candidateData.priorReportLines(c).forEach(function (text) { out.push(['literature', text]); });
    var prior = candidateData.earlierReport(c);
    if (prior.status === 'confirmed') {
      if (prior.evidence !== k) candidateData.checkEvidenceLines(prior.evidence).forEach(function (text) { out.push(['literature', text]); });
      out.push(['literature-source', prior.source], ['prediction-source', prior.prediction]);
    }
    candidateData.literatureLines(c).forEach(function (text) { out.push(['literature', text]); });
    candidateData.literatureSources(c).forEach(function (source) { out.push(['literature-source', source]); });
    candidateData.phononLines(c.phonon_check).forEach(function (text) {
      out.push(['warn', text]);
    });
    if (c.listed && /^\d{4}-\d{2}-\d{2}$/.test(String(c.listed.date))) out.push(['date', c.listed]);
    return out;
  };

  const candListedText = function candListedText(l) { return 'First listed on ' + fmtDayISO(l.date) + (candNum(l.round) ? ', in screening round ' + l.round : ''); };

  // the remarks fold away, to save space: a click on "Remarks" opens them (the viewer remembers the choice)
  const candRemarksEl = function candRemarksEl(c, hur, block, inRow) {
    var ul = h('ul', { class: 'xt-notes', 'aria-label': 'Remarks' });
    candRemarks(c, hur, block).forEach(function (r) {
      if (r[0] === 'date') {
        var file = /^screen_round\d+\.json$/.test(String(r[1].file || '')) ? r[1].file : '';
        ul.appendChild(h('li', { class: 'is-date' }, candListedText(r[1]) + '. ', file ? h('a', { href: REPO_URL + '/commits/main/results/' + file, text: 'The repository’s history' }) : 'The repository’s history',
          ' records when we proposed it.'));
      } else if (r[0] === 'source') {
        ul.appendChild(h('li', { class: 'is-info' }, 'Source: ', h('a', { href: candCheckSource(r[1]), text: cText(r[1].cite, 300) || 'Read the reported check' })));
      } else if (r[0] === 'literature-source') {
        ul.appendChild(h('li', { class: 'is-info' }, 'Literature source: ', h('a', { href: r[1].url, text: r[1].cite })));
      } else if (r[0] === 'prediction-source') {
        ul.appendChild(h('li', { class: 'is-info' }, 'Frozen prediction source: ', h('a', { href: r[1].url, text: r[1].cite })));
      } else if (r[0] === 'literature') {
        ul.appendChild(h('li', { class: 'is-info', text: r[1] }));
      } else ul.appendChild(richText(h('li', { class: 'is-' + r[0] }), r[1]));
    });
    var warns = ul.querySelectorAll('li.is-warn').length;
    var box = h('details', { class: inRow ? 'cand-remarks' : 'xt-remarks', open: !inRow && candState.notesOpen },
      h('summary', { class: warns ? 'has-warn' : '' }, 'Remarks', warns ? h('span', { class: 'cand-remarks-n', text: warns + (warns === 1 ? ' caution' : ' cautions') }) : null), ul);
    if (!inRow) box.addEventListener('toggle', function () { candState.notesOpen = box.open; });
    return box;
  };

  const candCheckText = function candCheckText(k) {
    return candidateData.checkText(k);
  };

  const candCheckSource = function candCheckSource(k) {
    var source = candidateData.sourceLink(k);
    if (source) return source.url;
    var ref = typeof k.ref === 'string' ? REFS[k.ref] : null;
    return ref && isHttps(refUrl(ref)) ? refUrl(ref) : '';
  };

  // A matching DFT or experimental check is separate from a literature-search record.
  const candCheck = function candCheck(c) {
    var k = candChecked(c);
    if (!k || typeof k !== 'object' || !CHECK_LABEL[k.kind]) return h('span', { class: 'cand-open', text: 'no matching check recorded' });
    var txt = candCheckText(k);
    var url = candCheckSource(k);
    var el = richText(h('span', { class: 'cand-done' + (k.superconducts === false ? ' miss' : k.superconducts === true ? ' hit' : '') }), txt);
    return url ? h('a', { href: url, class: 'cand-check-link' }, el) : el;
  };

  const candOursNote = function candOursNote(sc, kind) {
    var b = candBlock(sc, kind), ex = (b && b.excluded) || {}, parts = [], sys = typeof ex.system === 'number';
    if (typeof ex.supercon === 'number') parts.push(fmtInt(ex.supercon) + ' with a SuperCon or 3DSC record');
    if (typeof ex.computed === 'number') parts.push(fmtInt(ex.computed) + ' with a computed Tc');
    if (typeof ex.prior === 'number') parts.push(fmtInt(ex.prior) + ' reported or predicted by others');
    if (sys) parts.push(fmtInt(ex.system) + ' made of the same elements as a known superconductor');
    var txt = 'The new-candidate view retains predictions unless a reviewed experimental superconductivity report matches the exact composition, structure, phase, pressure, doping and sample form and predates a sourced frozen prediction. Such records remain visible in the earlier-reports archive. An unknown outcome, a formula match or a theoretical prediction is not enough to move a row. This list does not establish novelty.';
    if (parts.length && sc) txt += ' The original screening round ' + (sc.round || 1) + ' applied broader pool exclusions: ' + parts.join(', ') + '. These historical exclusions are preserved in the screening data; the app does not restore materials absent from that data.';
    return h('div', { class: 'cand-ours' }, h('span', { class: 'cand-ours-mark', 'aria-hidden': 'true' }), h('p', null, h('b', { text: 'Predictions and earlier reports.' }), ' ', h('span', { text: txt })));
  };

  const candKind = function candKind(k) {
    if (CAND_KINDS.indexOf(k) < 0 || k === candState.kind) return;
    candState.kind = k;
    candState.all = false;
    store.set('cand-kind', k);
    renderCandidates(state.data);
  };

  const candTrack = function candTrack(k) {
    if (candidateData.tracks.indexOf(k) < 0 || k === candState.track) return;
    candState.track = k;
    candState.all = false;
    store.set('cand-track', k);
    renderCandidates(state.data);
  };

  const candArchive = function candArchive(show) {
    if (candState.archive === show) return;
    candState.archive = show;
    candState.all = false;
    candState.key = '';
    renderCandidates(state.data);
  };

  const candModel = function candModel(sc, re, fallback) {
    var m = list(sc && sc.models).filter(function (x) { return typeof x === 'string' && re.test(x); })[0];
    return m ? cText(m, 40) : fallback;
  };


  const renderCandidates = function renderCandidates(d) {
    var el = $('#candidates-card');
    if (!el) return;
    var sc = d && d.screen, kind = candState.kind === 'hurricane' ? 'hurricane' : 'storm', hur = kind === 'hurricane';
    var gotS = candRows(sc, 'storm'), gotH = candRows(sc, 'hurricane'), got = candCurrentRows(sc, kind), rows = got.rows;
    // a refresh with the same list keeps the card (and its turning structures) as it is
    var key = JSON.stringify([sc && sc.round, sc && sc.date, sc && sc.status, sc && (sc.phonon_checks || sc.phonon_check), kind, candState.track, candState.archive, gotS.hidden, gotH.hidden, gotS.rows.length, gotH.rows.length, candState.all,
      rows.map(function (c) { return [candId(c), c.tc, c.tc_cal, c.tc_sc, c.lo, c.hi, c.p_sc, c.p_lo, c.p_hi, c.novelty, c.outside, candChecked(c), c.phonon_check, candidateData.literatureFor(c), c.prior_superconductivity, c.prediction_provenance]; })]);
    if (key === candState.key && el.firstChild) return;
    candState.key = key;
    xtReset();
    clear(el);
    el.appendChild(h('div', { class: 'card-head' }, h('div', null,
      h('h2', { text: 'Superconductivity candidates from our AI models' }),
      richText(h('p'), 'These model predictions include matching checks and bounded literature-search records when available. Radar sorts the materials: Storm ranks the ones that look like conventional superconductors, which pair through phonons, and Hurricane the ones that look like the unconventional families. Literature searches and direct validation checks are shown separately.'))));
    var banner = candMcmBanner(sc);
    if (banner) append(el, banner);
    var seg = h('div', { class: 'seg cand-seg', role: 'group', 'aria-label': 'Which list to show' });
    [['storm', 'Conventional', 'found by Storm', gotS.rows.length], ['hurricane', 'Unconventional', 'found by Hurricane', gotH.rows.length]].forEach(function (k) {
      seg.appendChild(h('button', { type: 'button', 'aria-pressed': kind === k[0] ? 'true' : 'false', 'data-kind': k[0], onclick: function () { candKind(k[0]); } },
        h('b', { text: k[1] }), h('span', { class: 'cand-seg-sub', text: '· ' + k[2] }), k[3] ? h('span', { class: 'cand-seg-n', text: String(k[3]) }) : null));
    });
    el.appendChild(seg);
    var selected = hur ? gotH : gotS, archiveSeg = h('div', { class: 'seg cand-seg', role: 'group', 'aria-label': 'Candidates or earlier reports' });
    [[false, 'New candidates', selected.rows.length], [true, 'Earlier reports archive', selected.reported.length]].forEach(function (view) {
      archiveSeg.appendChild(h('button', { type: 'button', 'aria-pressed': !!candState.archive === view[0] ? 'true' : 'false', onclick: function () { candArchive(view[0]); } },
        view[1], h('span', { class: 'cand-seg-n', text: String(view[2]) })));
    });
    el.appendChild(archiveSeg);
    el.appendChild(h('p', { class: 'cand-meta', text: 'Sorted by predicted ' + (hur ? 'Tc if superconducting' : 'DFT Tc') + ', highest first; unknown Tc last. ' +
      (candState.archive ? 'This archive retains predictions with a reviewed, earlier experimental report for the exact candidate.' : '“New candidates” is a working list, not a claim of previously unreported superconductivity.') }));
    if (!hur) {
      var tracks = h('div', { class: 'seg cand-seg', role: 'group', 'aria-label': 'Storm candidate ranking' });
      CAND_TRACKS.forEach(function (track) {
        var count = candidateData.trackRows(candState.archive ? gotS.reported : gotS.rows, sc && sc.tracks, track[0]).length;
        tracks.appendChild(h('button', { type: 'button', 'aria-pressed': candState.track === track[0] ? 'true' : 'false', onclick: function () { candTrack(track[0]); } },
          track[1], h('span', { class: 'cand-seg-n', text: String(count) })));
      });
      el.appendChild(tracks);
      var track = CAND_TRACKS.filter(function (t) { return t[0] === candState.track; })[0];
      el.appendChild(h('p', { class: 'cand-meta', text: track[2] + ' Rank is within this selected list; each prediction remains subject to its validation checks.' }));
    }
    el.appendChild(candOursNote(sc, kind));
    if (!hur) candidateData.phononSummaryLines(sc).forEach(function (text) {
      el.appendChild(h('p', { class: 'cand-meta', text: text }));
    });
    var block = candBlock(sc, kind);
    if (!rows.length) {
      if (candState.archive) {
        el.appendChild(h('p', { class: 'note', text: 'No earlier experimental superconductivity report currently meets the exact-identity and sourced prediction-date requirements for this selected list. This is not evidence that no such report exists.' }));
        el.appendChild(candTellUs());
        return;
      }
      // before the round that fills this list: what it will hold
      el.appendChild(h('ol', { class: 'cand-steps' }, hur ? [
        richText(h('li'), 'Sort: Radar sends the compounds in open crystal databases that look like the unconventional families (cuprates, iron-based and heavy-fermion compounds and other oxides) to Hurricane.'),
        richText(h('li'), 'Rank: Hurricane gives the chance that each compound superconducts and its Tc if it does, with a 90% range.'),
        richText(h('li'), 'Review: exact candidates with verified earlier experimental superconductivity reports move to the visible archive.'),
        richText(h('li'), 'Check: the top candidates are suggested to experimental groups, since a calculation cannot yet predict unconventional pairing reliably.')] : [
        richText(h('li'), 'Rank: Radar keeps the metals in open crystal databases that look like conventional superconductors, and Storm predicts their Tc, each with a 90% range.'),
        richText(h('li'), 'Review: exact candidates with verified earlier experimental superconductivity reports move to the visible archive.'),
        richText(h('li'), 'Check: the top candidates go to a full DFT electron–phonon calculation.'),
        richText(h('li'), 'Measure: the ones that pass are suggested to experimental groups.')]));
      var round = (sc && sc.round) || 0, empty;
      if (sc && sc.status === 'running') empty = 'Screening round ' + (round || 1) + ' is running; the list appears here when it finishes.';
      else if (!hur && gotS.rows.length) empty = 'No published candidates belong to this selected ranking yet. Choose another Storm ranking to see the available candidates.';
      else if (got.hidden) empty = 'These candidates have reviewed earlier experimental reports. Their predictions, sources and conditions remain in the earlier-reports archive.';
      else if (hur && block) empty = 'Radar sent no compound to Hurricane in screening round ' + (round || 1) + '.';
      else if (hur) empty = 'Hurricane’s list of unconventional candidates comes with Screening round ' + Math.max(2, round + 1) + ', our next run.';
      else empty = 'The first list, with the crystal structure of every candidate turning in 3D, comes with Screening round 1, our next run.';
      el.appendChild(h('p', { class: 'note', text: empty }));
      el.appendChild(candTellUs());
      return;
    }
    var pool = (block && block.pool) || {};
    var meta = h('p', { class: 'cand-meta' }), when = 'Screening round ' + (sc.round || 1) + (sc.date ? ', ' + fmtDayISO(sc.date) : '') + ': ';
    var rule = cText(String(pool.rule || '').split('; the list holds')[0], 400);
    if (hur) {
      richText(meta, when + 'of the ' + (candNum(pool.n_screened) ? fmtInt(pool.n_screened) + ' ' : '') + 'compounds in Hurricane’s pool from ' + cText(pool.source || 'JARVIS-DFT', 120) +
        (rule ? ' (' + rule + ')' : '') + ', ' + candModel(sc, /^Radar/, 'Radar') + ' sent ' + (candNum(pool.n_sent) ? fmtInt(pool.n_sent) : 'the ones that look unconventional') + ' to ' +
        cText(block.model || candModel(sc, /^Hurricane/, 'Hurricane'), 40) + '. Hurricane learns measured Tc: it gives the chance that a compound superconducts and its Tc if it does, and the 90% range is for that Tc. ' + candidateData.rankingText(block));
    } else {
      var models = list(sc.models).filter(function (m) { return typeof m === 'string' && !/^Hurricane/.test(m); }).map(function (m) { return cText(m, 40); });
      richText(meta, when + (models.length ? models.join(' and ') : sc.model ? cText(sc.model, 40) : 'Storm') + ' ranked ' +
        (candNum(pool.n_screened) ? fmtInt(pool.n_screened) + ' ' : '') + cText(pool.what || 'materials', 120) + (pool.source ? ' from ' + cText(pool.source, 120) : '') +
        (rule ? ': ' + rule : '') + '. Storm’s Tc is the computed (DFT) Tc that it learns, and the 90% range is for that value.');
    }
    el.appendChild(meta);
    if (!rows.some(function (c) { return candId(c) === candState.sel[kind]; })) candState.sel[kind] = candId(rows[0]);
    var sel = candState.sel[kind];
    var shown = candState.all ? rows : rows.slice(0, CAND_SHOWN);
    if (!shown.some(function (c) { return candId(c) === sel; })) shown = shown.concat(rows.filter(function (c) { return candId(c) === sel; }));
    var body = h('div', { class: 'cand-body' });
    var viewer = h('div', { class: 'cand-viewer', id: 'cand-viewer' });
    body.appendChild(viewer);
    // a grid list rather than a table, so that phones get the same information without scrolling sideways
    var ol = h('ol', { class: 'cand-list' + (hur ? ' is-hur' : '') });
    ol.appendChild(h('li', { class: 'cand-row cand-headrow', 'aria-hidden': 'true' },
      h('span', { class: 'cand-rank', text: '#' }), h('span'), h('span', { text: 'Material' }),
      richText(h('span', { class: 'cand-tc' }), hur ? 'Tc if it superconducts, 90% range' : 'Storm Tc, 90% range'),
      hur ? null : h('span', { class: 'cand-cal', text: 'Calibrated' }), h('span', { class: 'cand-p', text: 'Chance' }), h('span', { class: 'cand-check', text: 'Check' })));
    shown.forEach(function (c) {
      var i = rows.indexOf(c), id = candId(c), M = xtModel(c), on = id === sel;
      var name = isHttps(c.url) ? h('a', { href: c.url, text: hurSub(c.formula) }) : h('span', { text: hurSub(c.formula) });
      var sub = [c.spg ? cText(c.spg, 30) : '', candNum(c.ehull) ? (Math.round(1000 * c.ehull) === 0 ? 'on the convex hull' : Math.round(1000 * c.ehull) + ' meV/atom above the hull') : '',
        hur && candNum(c.gap) ? (c.gap > 0 ? 'band gap ' + c.gap.toFixed(1) + ' eV' : 'metallic') : '', hur && c.magnetic === true ? 'magnetic' : '',
        c.id ? cText(String(c.id), 40) : '', c.listed && /^\d{4}-\d{2}-\d{2}$/.test(String(c.listed.date)) ? 'listed ' + fmtDayISO(c.listed.date) : ''].filter(Boolean).join(' · ');
      var thumb;
      if (M) {
        var cv = h('canvas', { class: 'xt-thumb', 'aria-hidden': 'true' });
        thumb = h('button', { class: 'cand-thumb', type: 'button', 'aria-pressed': on ? 'true' : 'false', 'aria-label': 'Show the crystal structure of ' + c.formula + ' in the viewer',
          onclick: function () { candSelect(id, true); } }, cv);
        xtItem(cv, M, false);
      } else thumb = h('span', { class: 'cand-thumb none', title: 'No structure stored' });
      var tc = hur ? candTcSc(c) : c.tc, range = candRange(c), mcm = candMcm(c, hur);
      var li = h('li', { class: 'cand-row' + (on ? ' is-sel' : '') + (mcm ? ' is-mcm' : ''), 'data-id': id },
        h('span', { class: 'cand-rank', text: String(i + 1) }),
        thumb,
        h('div', { class: 'cand-main' }, h('b', null, name), sub ? h('div', { class: 'dt-cell-sub', text: sub }) : null,
          h('div', { class: 'dt-cell-sub', text: candidateData.literatureText(c) }),
          candRemarksEl(c, hur, block, true),
          mcm ? h('span', { class: 'cand-mcm' + (mcm === 'confirmed' ? ' is-done' : ''), text: mcm === 'confirmed' ? 'Above the McMillan limit: measured and reproduced' : 'Worth an experiment: predicted above the McMillan limit' }) : null),
        h('div', { class: 'cand-tc' }, h('b', { text: candK(tc) }), range ? h('div', { class: 'dt-cell-sub', text: range }) : null),
        hur ? null : h('div', { class: 'cand-cal' }, h('span', { class: 'cand-label', text: 'Calibrated ' }), candNum(c.tc_cal) ? candK(c.tc_cal) : '—'),
        h('div', { class: 'cand-p' }, h('span', { class: 'cand-label', text: 'Chance it superconducts ' }), candPct(c.p_sc),
          hur && candNum(c.p_lo) && candNum(c.p_hi) ? h('div', { class: 'dt-cell-sub', title: candidateData.disagreement(c), text: 'Model disagreement ' + (100 * c.p_lo).toFixed(1) + '–' + (100 * c.p_hi).toFixed(1) + '%' }) : null),
        h('div', { class: 'cand-check' }, candCheck(c), c.phonon_check ? h('div', { class: 'dt-cell-sub', text: candidateData.phononLines(c.phonon_check)[0] }) : null));
      ol.appendChild(li);
    });
    body.appendChild(ol);
    el.appendChild(body);
    if (rows.length > CAND_SHOWN) {
      el.appendChild(h('div', { class: 'feed-more' }, h('button', { class: 'btn small', type: 'button', onclick: function () { candState.all = !candState.all; renderCandidates(state.data); } },
        candState.all ? 'Show the top ' + CAND_SHOWN : 'Show all ' + rows.length)));
    }
    if (candState.archive) {
      el.appendChild(h('p', { class: 'note', text: 'Original predictions are retained here for comparison with earlier measurements. Remarks provide the report, sample conditions, identity review and frozen prediction source. These entries are not new discoveries by this model.' }));
      el.appendChild(candTellUs());
      candViewer(rows);
      xtKick();
      return;
    }
    var checked = rows.filter(function (c) { return candChecked(c); }).length;
    var lead = (checked ? checked + ' of ' + rows.length + ' candidates have matching checks recorded. ' : 'No matching DFT or experimental check is recorded for these candidates. ') + 'They are predictions: a candidate becomes a discovery only when ' +
      (hur ? 'an experiment confirms it. Many of these compounds have a band gap in DFT or are magnetic, and, like the parent compounds of the cuprates and iron-based superconductors, would need doping or pressure to superconduct. ' :
        'a calculation and then an experiment confirm it. “Calibrated” is Storm’s estimate of the measured Tc. ');
    var ck = block && block.check;
    if (ck && candNum(ck.share_sc_likely) && candNum(ck.share_sc_unlikely)) {
      lead += 'How far its chance can be trusted: on ' + (hur ? 'compounds in 3DSC' : 'known materials in 3DSC') + ' that it had not seen in training, ' + Math.round(100 * ck.share_sc_likely) +
        '% of those it gave at least an even chance superconduct, against ' + Math.round(100 * ck.share_sc_unlikely) + '% of the others. ' +
        (hur ? '' : 'Most of those materials were measured because someone expected them to superconduct, so for new materials the chance is likely lower. ');
    }
    // round 3 on: Hurricane also learned from compounds with no superconductivity record, and was released for fewer false alarms
    var rel = hur && block && block.reliability, nk = hur && block && block.not_known;
    if (rel && candNum(rel.dismissed) && candNum(rel.false_alarms)) {   // round 4 on: "not known" far from the training data
      lead += (block.model || 'Hurricane') + ' gives a chance only to compounds near its training data' +
        (nk && candNum(nk.n) && candNum(nk.of) ? ': ' + fmtInt(nk.n) + ' of the ' + fmtInt(nk.of) + ' compounds Radar sent it lie too far, so it does not judge them and they are not on this list' : '') +
        '. It learned from ' + (candNum(rel.n_background) ? fmtInt(rel.n_background) + ' ' : '') + 'compounds with no superconductivity record, counted as probably not superconducting. In cross-validation it gave ' +
        (rel.false_alarms === 0 ? 'none' : candPct(rel.false_alarms)) + ' of the held-out compounds of that kind at least an even chance' + (candNum(rel.false_alarms_reference) && rel.reference ? ' (Hurricane ' + rel.reference + ': ' + candPct(rel.false_alarms_reference) + ')' : '');
      // Describe the published screening predictions without calling a fold ensemble a full-data fit.
      var nLik = rows.filter(function (c) { return candNum(c.p_sc) && c.p_sc >= 0.5; }).length;
      lead += '; the published screening predictions give ' + (nLik === 0 ? 'none' : nLik === 1 ? 'one' : fmtInt(nLik)) + ' of the ' + fmtInt(rows.length) + ' on this list at least an even chance. ';
      var hv = candHurVersion(block), fA = hv ? hurLofoAvg(hv, 'found') : null, uA = hv ? hurLofoAvg(hv, 'unknown') : null, fR = hv ? hurLofoAvg(hv, 'found_reference') : null;
      lead += 'Trained without a whole family, it calls ' + candPct(rel.dismissed) + ' of that family’s superconductors unlikely' + (candNum(rel.dismissed_previous) && rel.previous ? ' (Hurricane ' + rel.previous + ': ' + candPct(rel.dismissed_previous) + ')' : '') +
        (candNum(fA) && candNum(uA) ? ', answers “not known” for ' + candPct(uA) + ' and gives ' + candPct(fA) + ' at least an even chance' + (candNum(fR) && rel.reference ? ' (Hurricane ' + rel.reference + ': ' + candPct(fR) + ')' : '') : '') + '. ';
    } else if (rel && candNum(rel.false_alarms) && candNum(rel.false_alarms_previous)) {
      lead += (block.model || 'Hurricane') + ' also learned from ' + (candNum(rel.n_background) ? fmtInt(rel.n_background) + ' ' : '') + 'compounds with no superconductivity record, counted as probably not superconducting, so it is more cautious with compounds unlike its training data: of the held-out compounds of that kind, it gives ' +
        (rel.false_alarms === 0 ? 'none' : candPct(rel.false_alarms)) + ' at least an even chance, against ' + candPct(rel.false_alarms_previous) + ' for Hurricane ' + (rel.previous || 'before') + '. The price: it would also be slow to recognize a family of superconductors that no one has found yet. ';
    }
    var nOut = rows.filter(function (c) { return c.outside === true; }).length;
    if (hur && nk) lead += (nOut ? fmtInt(nOut) + (nOut === 1 ? ' compound on this list lies' : ' compounds on this list lie') + ' just outside its training data, near enough for a chance; ' : 'Every compound on this list lies near its training data; ') +
      'still, the chance and the Tc are far from certain: treat this list as a set of leads, not of likely superconductors. ';
    else if (hur) lead += 'But many compounds on this list are unlike anything Hurricane learned from, and for them both the chance and the Tc are far less certain than these numbers suggest; treat this list as a set of leads, not of likely superconductors. ';
    if (got.hidden) lead += got.hidden + (got.hidden === 1 ? ' material is' : ' materials are') + ' retained in the earlier-reports archive after exact-identity and prediction-date review. ';
    var nWorth = rows.filter(function (c) { return candMcm(c, hur) === 'worth'; }).length;
    lead += 'We highlight a candidate as worth an experiment only when its predicted Tc is above the McMillan limit of about 40 K and it passes every test: more likely than not to superconduct, inside its model’s training data, and made before (in ICSD)' +
      (hur ? '' : '; a Storm candidate also needs the low end of its 90% range, or a full DFT calculation, above 40 K') + '. ' + (nWorth ? (nWorth === 1 ? 'One candidate on this list does.' : nWorth + ' candidates on this list do.') : 'None on this list does yet.') + ' ';
    el.appendChild(richText(h('p', { class: 'note' }), lead));
    el.appendChild(candTellUs());
    el.appendChild(h('p', { class: 'note xt-credit' }, 'Atom sizes follow covalent radii (', h('a', { href: refUrl(REFS.cordero2008), text: REFS.cordero2008.t }), '); the box is the unit cell.'));
    candViewer(rows);
    xtKick();
  };

  const candTellUs = function candTellUs() {
    return h('p', { class: 'note' }, 'If you know of an earlier report of any of these materials, ', contactLink('tell us', 'candidate'), '. We will review its source, sample conditions and timing; a verified earlier superconductivity report for the exact candidate moves to the archive with its original prediction.');
  };

  const candSelect = function candSelect(id, scroll) {
    var kind = candState.kind === 'hurricane' ? 'hurricane' : 'storm';
    candState.sel[kind] = id;
    [].forEach.call(document.querySelectorAll('#candidates-card .cand-row[data-id]'), function (li) {
      var on = li.getAttribute('data-id') === id;
      li.classList.toggle('is-sel', on);
      var b = li.querySelector('.cand-thumb');
      if (b && b.tagName === 'BUTTON') b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    candViewer(candCurrentRows(state.data && state.data.screen, kind).rows);
    var v = $('#cand-viewer');
    if (scroll && v && v.getBoundingClientRect().top < 0) v.scrollIntoView({ block: 'start', behavior: motionOK() ? 'smooth' : 'auto' });
    xtKick();
  };

  // the large structure viewer: the selected candidate turning slowly; drag (or the arrow keys) to turn it
  const candViewer = function candViewer(rows) {
    var box = $('#cand-viewer');
    if (!box) return;
    XT.items = XT.items.filter(function (it) { if (it.big) { xtForget(it); return false; } return true; });
    var was = box.querySelector('details.xt-remarks');
    if (was) candState.notesOpen = was.open;   // the toggle event comes a moment later, so read the state itself
    clear(box);
    var hur = candState.kind === 'hurricane', sel = candState.sel[hur ? 'hurricane' : 'storm'], i = 0;
    rows.forEach(function (c, k) { if (candId(c) === sel) i = k; });
    var c = rows[i];
    if (!c) return;
    var M = xtModel(c);
    var play = h('button', { class: 'btn small xt-play', type: 'button', onclick: function () { XT.play = !XT.play; xtSync(); xtKick(); } });
    box.appendChild(h('div', { class: 'xt-head' },
      h('div', { class: 'xt-title' }, h('span', { class: 'xt-rank', text: '#' + (i + 1) }), h('b', { text: hurSub(c.formula) }),
        h('span', { class: 'xt-sub', text: [c.spg ? cText(c.spg, 30) : '', M ? M.n + (M.n === 1 ? ' atom' : ' atoms') + ' in the cell' : ''].filter(Boolean).join(' · ') })),
      M ? play : null));
    box.appendChild(h('p', { class: 'xt-facts', text: candidateData.literatureText(c) }));
    if (!M) {
      box.appendChild(h('p', { class: 'note', text: 'No crystal structure is stored for this material.' }));
      box.appendChild(candRemarksEl(c, hur, candBlock(state.data && state.data.screen, hur ? 'hurricane' : 'storm')));
      return;
    }
    var cv = h('canvas', { class: 'xt-big', role: 'img', tabindex: '0', 'aria-label': xtAlt(c, M) });
    var it = xtItem(cv, M, true);
    xtDragOn(cv, it);
    box.appendChild(h('div', { class: 'xt-stage' }, cv));
    var key = h('ul', { class: 'xt-key', 'aria-label': 'Elements' });
    M.els.forEach(function (e, k) {
      var r = XT_R[XT_Z[e]] / 100, px = Math.round(8 + 6 * Math.min(1, Math.max(0, (r - 0.6) / 1.6)));
      key.appendChild(h('li', null, h('i', { class: 'xt-dot xt-s' + Math.min(k + 1, 4), style: 'width:' + px + 'px;height:' + px + 'px' }), e + ' ', h('span', { class: 'xt-n', text: '×' + M.count[e] })));
    });
    box.appendChild(key);
    box.appendChild(h('p', { class: 'xt-facts', text: xtCellText(M) }));
    var tc = h('p', { class: 'xt-tc' }), range = candRange(c);
    if (hur) {
      richText(tc, 'Hurricane: Tc ' + candK(candTcSc(c)) + ' if it superconducts' + (range ? ' (90% range ' + range + ')' : '') +
        (candNum(c.p_sc) ? '; the chance that it does is ' + candPct(c.p_sc) : '') + '. ' + (candChecked(c) ? 'Reported checks are listed below.' : 'A prediction awaiting a DFT or measurement check.'));
    } else {
      richText(tc, 'Storm Tc ' + candK(c.tc) + (range ? ' (90% range ' + range + ')' : '') + (candNum(c.tc_cal) ? ' · calibrated ' + candK(c.tc_cal) : ''));
    }
    box.appendChild(tc);
    var mcm = candMcm(c, hur);
    if (mcm === 'confirmed') {
      box.appendChild(h('p', { class: 'xt-mcm is-done' }, 'Above the McMillan limit of about 40 K, long thought to be the ceiling for conventional superconductors: measured, published and reproduced by another group.'));
    } else if (mcm === 'worth') {
      box.appendChild(h('p', { class: 'xt-mcm' }, 'Worth an experiment: ' + (hur ? 'Hurricane puts its Tc, if it superconducts,' : 'Storm puts its Tc') +
        ' above the McMillan limit of about 40 K, and it passes every test we set before suggesting a measurement. It is still a prediction. If you can measure it, ', contactLink('write to us', 'experiment'), '.'));
    }
    if (hur) {
      var types = list(c.types).filter(function (t) { return CAND_TYPE[t]; }).map(function (t) { return CAND_TYPE[t]; });
      var fam = CAND_FAMILY[c.family];
      if (fam || types.length) {
        box.appendChild(h('p', { class: 'xt-facts' }, [fam ? 'It contains ' + fam + '.' : '', types.length ? 'Its formula fits the pattern of the ' + types.join(' and the ') + '.' : ''].filter(Boolean).join(' ')));
      }
    }
    box.appendChild(candRemarksEl(c, hur, candBlock(state.data && state.data.screen, hur ? 'hurricane' : 'storm')));
    var nav = h('div', { class: 'xt-nav' },
      h('button', { class: 'btn small', type: 'button', disabled: i === 0, onclick: function () { candSelect(candId(rows[i - 1]), false); } }, 'Previous'),
      h('span', { class: 'xt-hint', text: 'Drag to turn it' }),
      h('button', { class: 'btn small', type: 'button', disabled: i >= rows.length - 1, onclick: function () { candSelect(candId(rows[i + 1]), false); } }, 'Next'));
    box.appendChild(nav);
    xtSync();
  };

  const xtSync = function xtSync() {
    var b = $('#cand-viewer .xt-play');
    if (!b) return;
    b.innerHTML = XT.play ? G.pause : G.play;
    b.appendChild(document.createTextNode(XT.play ? 'Pause' : 'Play'));
    b.setAttribute('aria-label', XT.play ? 'Stop the structures turning' : 'Turn the structures');
    b.hidden = !motionOK();
  };

  const xtAlt = function xtAlt(c, M) {
    var parts = M.els.map(function (e) { return M.count[e] + ' ' + e; });
    return 'Crystal structure of ' + c.formula + (c.spg ? ', space group ' + c.spg : '') + ': ' + M.n + ' atoms in the unit cell (' + parts.join(', ') + '); ' + xtCellText(M);
  };

  const xtCellText = function xtCellText(M) {
    var a = M.abc, g = M.ang, f = function (x) { return x.toFixed(2); }, same = function (x, y) { return Math.abs(x - y) < 0.005; };
    var len = same(a[0], a[1]) && same(a[1], a[2]) ? 'a = b = c = ' + f(a[0]) + ' Å' : same(a[0], a[1]) ? 'a = b = ' + f(a[0]) + ' Å, c = ' + f(a[2]) + ' Å' :
      'a = ' + f(a[0]) + ' Å, b = ' + f(a[1]) + ' Å, c = ' + f(a[2]) + ' Å';
    var d = function (x) { return Math.round(x * 10) / 10 + '°'; }, deg = g.map(function (x) { return x * 180 / Math.PI; }), right = function (x) { return Math.abs(x - 90) < 0.05; };
    var ang = deg.every(right) ? 'α = β = γ = 90°' : right(deg[0]) && right(deg[1]) ? 'α = β = 90°, γ = ' + d(deg[2]) : 'α = ' + d(deg[0]) + ', β = ' + d(deg[1]) + ', γ = ' + d(deg[2]);
    return len + '; ' + ang + '; ' + (M.vol / M.n).toFixed(1) + ' Å³ per atom';
  };

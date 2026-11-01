'use strict';
// hurricane-tour: shared lexical function definitions; no startup side effects.


  /* ---------- Hurricane in the Hello Super tour ---------- */
  const hurStoryCaption = function hurStoryCaption() {
    var info = hurInfo();
    if (!info) return 'Hurricane, our second AI-designed model, learns the Tc of unconventional superconductors from measurements, each graded by how well it has been confirmed.';
    var v = info.v, sc = v.scores || {}, dd = info.data, top = list(v.importance).slice(0, 2).map(function (i) { return hurFeatName(i.name); });
    return 'Hurricane, our second AI-designed model, learns the Tc of cuprates, iron- and nickel-based, heavy-fermion and other oxide superconductors directly from ' + fmtInt(dd.n) +
      ' measurements. Our AI agent gave it physics features such as the number of holes per copper, which sets where a cuprate sits on its Tc dome' +
      (top.length ? '; these turned out to be what the model relies on most (' + top.join(', ') + ')' : '') + '. ' + hurTitle(info) + ' is off by ' + hurK(sc.tc_mae) +
      ' K for compounds whose parent it never saw, against ' + hurK(sc.reference_mae) + ' K for a composition-only model. It cannot yet predict a family it has never seen, which is where the search for new high-Tc families has to go beyond data.';
  };

  const drawStoryHurricane = function drawStoryHurricane(c, C, B, t, narrow) {
    var info = hurInfo(), a0 = stSpan(t, 0, 0.5);
    c.globalAlpha = a0;
    var D = narrow ? { x: B.x, y: B.y + 4, w: B.w, h: Math.min(200, B.h * 0.5) } : { x: B.x, y: B.y + 6, w: Math.round(B.w * 0.5), h: B.h - 6 };
    drawHurDomePanel(c, C, D, t, 0.2, narrow);
    var R = narrow ? { x: B.x, y: D.y + D.h + 14, w: B.w, h: B.y + B.h - (D.y + D.h + 14) } : { x: D.x + D.w + 40, y: B.y + 6, w: B.w - D.w - 40, h: B.h - 6 };
    if (!info) { c.globalAlpha = 1; return; }
    var v = info.v, sc = v.scores || {}, dd = info.data;
    var items = [
      ['Learns from', fmtInt(dd.n) + ' measured Tc values', '4 families · SuperCon via 3DSC'],
      ['Error, unseen parents', hurK(sc.tc_mae) + ' K', 'composition only: ' + hurK(sc.reference_mae) + ' K'],
      ['Relies most on', list(v.importance).slice(0, 2).map(function (i) { return hurFeatName(i.name); }).join(' · '), 'physics features the AI proposed']
    ];
    var rowH = narrow ? Math.min(58, R.h / 3) : Math.min(78, R.h / 3.3);
    items.forEach(function (it, i) {
      var a = stSpan(t, 2.4 + 0.9 * i, 3.0 + 0.9 * i);
      if (a <= 0) return;
      c.globalAlpha = a0 * a;
      var y = R.y + i * rowH;
      label(c, C, it[0], R.x, y + 12, { size: 11.5, color: C.muted });
      stText(c, C, hurFit(c, C, it[1], R.w, narrow ? 14 : 16, '600'), R.x, y + (narrow ? 31 : 34), { size: narrow ? 14 : 16, weight: '600', color: i === 1 ? C.accent : C.ink });
      label(c, C, hurFit(c, C, it[2], R.w, 11.5), R.x, y + (narrow ? 48 : 54), { size: 11.5, color: C.ink2 });
    });
    c.globalAlpha = 1;
  };

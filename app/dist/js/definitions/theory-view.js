'use strict';
// theory-view: shared lexical function definitions; no startup side effects.


  const richText = function richText(el, text) {
    clear(el);
    String(text).split(/(ω_log|Tc|k_B)/).forEach(function (p) {
      if (!p) return;
      if (p === 'ω_log') { el.appendChild(document.createTextNode('ω')); el.appendChild(h('sub', { text: 'log' })); }
      else if (p === 'Tc') { el.appendChild(document.createTextNode('T')); el.appendChild(h('sub', { text: 'c' })); }
      else if (p === 'k_B') { el.appendChild(document.createTextNode('k')); el.appendChild(h('sub', { text: 'B' })); }
      else el.appendChild(document.createTextNode(p));
    });
    return el;
  };


  const buildLearn = function buildLearn() {
    var el = $('#learn');
    clear(el);
    el.appendChild(h('p', { class: 'note learn-note', text: 'Animations simplify structures and physical ideas. Their curves illustrate trends; they are not digitised experimental measurements. Reported temperatures and conditions are identified separately and linked to their sources.' }));
    var chartCard = h('section', { class: 'card' });
    var toggle = h('button', { class: 'btn small', type: 'button', id: 'tc-toggle', onclick: function () { learn.table = !learn.table; renderTcChart(); } });
    append(chartCard, [
      h('div', { class: 'card-head' },
        h('div', null, richText(h('h2'), 'Tc through the years'),
          h('p', { text: 'Every dot is a superconductor. Press play to watch them arrive year by year, and choose one — ' +
            'the dot or the name beside it — to see its structure and the paper that reported it.' })),
        toggle),
      h('div', { class: 'tc-legend', id: 'tc-legend' }),
      h('div', { class: 'tc-controls', id: 'tc-controls' }),
      h('div', { class: 'chart', id: 'tc-chart' }),
      h('div', { class: 'tc-detail', id: 'tc-detail', hidden: true })
    ]);
    var famBar = h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter materials by family', id: 'mat-filter' });
    [['all', 'All']].concat(Object.keys(FAMILIES).map(function (k) { return [k, FAMILIES[k].label]; })).forEach(function (f) {
      famBar.appendChild(h('button', { class: 'demo-tab', type: 'button', 'data-fam': f[0], 'aria-pressed': f[0] === learn.fam ? 'true' : 'false', text: f[1], onclick: function () { learn.fam = f[0]; renderMaterials(); } }));
    });
    var theoryCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Theories of superconductivity' }),
        h('p', { text: 'From the first equations to today’s open questions, with the original papers.' }))),
      h('div', { class: 'learn-grid', id: 'theory-grid' }));
    var matCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Materials to know' }),
        h('p', { text: 'The superconductors behind today’s technology and today’s headlines.' }))),
      famBar,
      h('div', { class: 'learn-grid', id: 'material-grid' }));
    var nobelCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Nobel Prizes for superconductivity' }),
        h('p', { text: 'Six Nobel Prizes in Physics went to superconductivity, from its discovery to superconducting quantum circuits.' }))),
      nobelList(NOBEL, 'nobel'),
      h('p', { class: 'nobel-sub', text: 'Related prizes' }),
      nobelList(NOBEL_RELATED, 'nobel related'));
    var mechCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, richText(h('h2'), 'Classic mechanisms of high-Tc superconductivity'),
        h('p', { text: 'Forty years after the cuprates were found, these are the main ideas for how they superconduct. Each explains part of the phase diagram; none is settled.' }))),
      h('div', { class: 'mech-overview' }, miniCanvas('cupratepd'),
        h('div', { class: 'mech-intro' },
          richText(h('p'), 'The copper-oxide phase diagram, drawn schematically. Undoped, the CuO₂ planes are antiferromagnetic Mott insulators. Adding holes (p per copper) melts the magnetism and opens a dome of d-wave superconductivity peaking near p ≈ 0.16, with a pseudogap and charge stripes on the underdoped side and a strange metal above the dome.'),
          h('p', { text: 'The probe moving along the doping axis names the idea that addresses each region; the cards below explain them one by one.' }))),
      h('div', { class: 'learn-grid', id: 'mech-grid' }));
    append(el, [chartCard, nobelCard, theoryCard, mechCard, matCard,
      h('p', { class: 'note learn-note', text: 'Tc values are as reported in the cited papers; onsets are marked. Links open the papers through their DOI. “Latest” lists results from 2023 to 2026; the New papers view has the full list and a live feed.' })]);
    var grid = $('#theory-grid');
    THEORIES.forEach(function (th) {
      var card = h('article', { class: 'lcard' },
        miniCanvas(th.anim),
        h('div', { class: 'lcard-top' }, h('h3', { text: th.name }), h('span', { class: 'tag', text: th.year })),
        h('p', { class: 'meta', text: th.who }),
        richText(h('p'), th.text),
        refList(th.refs),
        latestList(th.anim));
      if (th.demo) {
        card.appendChild(h('button', { class: 'btn small go', type: 'button', onclick: function () { setView('demos'); selectDemo(th.demo); window.scrollTo(0, 0); } }, 'See the animation'));
      }
      grid.appendChild(card);
    });
    var mgrid = $('#mech-grid');
    MECHANISMS.forEach(function (mc) {
      mgrid.appendChild(h('article', { class: 'lcard' },
        miniCanvas(mc.anim),
        h('div', { class: 'lcard-top' }, h('h3', { text: mc.name }), h('span', { class: 'tag', text: mc.year })),
        h('p', { class: 'meta', text: mc.who }),
        richText(h('p'), mc.text),
        h('p', { class: 'open-q' }, h('b', { text: 'Still open: ' }), richText(h('span'), mc.open)),
        refList(mc.refs),
        latestList(mc.anim)));
    });
    learn.built = true;
    renderMaterials();
    miniKick();
    renderTcChart();
    if (window.ResizeObserver) {
      var last = 0;
      new ResizeObserver(function (entries) {
        var w = Math.round(entries[0].contentRect.width);
        if (w && w !== last) { last = w; if (!learn.table) renderTcChart(); }
      }).observe($('#tc-chart'));
    }
  };


  const latestList = function latestList(card) {
    var items = recentFor(card).slice(0, 2);
    if (!items.length) return null;
    var ul = h('ul', { class: 'latest' });
    items.forEach(function (r) {
      ul.appendChild(h('li', null,
        h('span', { class: 'latest-meta' }, fmtMonth(r.d) + ' · ' + (KIND_LABEL[r.k] || r.k)),
        richText(h('b'), r.h),
        richText(h('span', { class: 'latest-text' }), r.x),
        h('span', { class: 'latest-ref' }, recentLink(r))));
    });
    return h('div', { class: 'latest-wrap' }, h('p', { class: 'latest-title', text: 'Latest' }), ul);
  };

  const nobelList = function nobelList(items, cls) {
    var ol = h('ol', { class: cls });
    items.forEach(function (n) {
      ol.appendChild(h('li', null,
        n.anim && MINI_DRAW[n.anim] ? miniCanvas(n.anim) : null,
        h('div', { class: 'nobel-row' },
          h('a', { class: 'nobel-year', href: nobelUrl(n.y), text: String(n.y), 'aria-label': 'The Nobel Prize in Physics ' + n.y + ' on NobelPrize.org' }),
          h('div', null, h('b', { text: n.who }), richText(h('span'), n.what),
            h('a', { class: 'nobel-link', href: nobelUrl(n.y), text: 'NobelPrize.org: Physics ' + n.y })))));
    });
    return ol;
  };


  const renderMaterials = function renderMaterials() {
    var grid = $('#material-grid');
    if (!grid) return;
    clear(grid);
    // only the material filter: the Papers and AI views have filter bars of the same kind
    [].forEach.call(document.querySelectorAll('#mat-filter button'), function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-fam') === learn.fam ? 'true' : 'false'); });
    MATERIALS.filter(function (m) { return learn.fam === 'all' || m.f === learn.fam; }).forEach(function (m) {
      grid.appendChild(h('article', { class: 'lcard' },
        miniCanvas(m.anim),
        h('div', { class: 'lcard-top' }, h('h3', { text: m.name }), h('span', { class: 'chip' }, h('i', { class: FAMILIES[m.f].cls }), FAMILIES[m.f].label)),
        h('p', { class: 'meta' }, h('b', { text: m.tag }), ' · ', richText(h('span'), 'Tc ' + m.tc)),
        richText(h('p'), m.text),
        refList(m.refs),
        latestList(m.anim)));
    });
    miniPrune();
    miniKick();
  };


  const tcStop = function tcStop() {
    if (learn.tcRaf) cancelAnimationFrame(learn.tcRaf);
    learn.tcRaf = 0; learn.tcLast = 0;
  };

  const tcEntry = function tcEntry(name) {
    var found = null;
    TC_DATA.forEach(function (d) { if (d.n === name) found = d; });
    return found;
  };

  // The chosen dot keeps its ring without rebuilding the chart, so a running sweep is not disturbed.
  const tcMark = function tcMark() {
    var host = $('#tc-chart');
    if (!host) return;
    Array.prototype.forEach.call(host.querySelectorAll('.tc-dot'), function (el) {
      if (el.classList) el.classList.toggle('sel', el.getAttribute('data-tc') === learn.tcSel);
    });
  };

  const renderTcDetail = function renderTcDetail() {
    var el = $('#tc-detail');
    if (!el) return;
    var d = tcEntry(learn.tcSel);
    clear(el);
    el.hidden = !d;
    if (!d) { miniPrune(); return; }
    var r = d.ref ? REFS[d.ref] : null, url = r ? refUrl(r) : '', fam = FAMILIES[d.f];
    var note = d.note ? d.note.charAt(0).toUpperCase() + d.note.slice(1) + '.' : '';
    append(el, [
      h('div', { class: 'tcd-head' },
        h('div', null,
          h('h3', { class: 'tcd-name', text: d.n }),
          h('p', { class: 'tcd-meta' }, h('i', { class: 'key ' + fam.cls }), fam.label + ' · ' + d.y +
            (d.p ? ' · under high pressure' : '') + (d.pre ? ' · preprint' : ''))),
        h('button', { class: 'btn small', type: 'button', 'aria-label': 'Close these material details',
          onclick: function () {
            learn.tcSel = ''; renderTcDetail(); tcMark();
            // Closing hands the keyboard back to the chart, which is where the next dot is chosen.
            var sv = $('#tc-chart svg');
            if (sv && sv.focus) { try { sv.focus({ preventScroll: true }); } catch (err) { sv.focus(); } }
          } }, 'Close')),
      h('div', { class: 'tcd-body' },
        h('div', { class: 'tcd-art' },
          d.a && MINI_DRAW[d.a] ? miniCanvas(d.a) : null,
          h('p', { class: 'tcd-cap',
            text: (d.a && MINI_CAP[d.a]) || 'Labelled schematic of an idealised structure, not measured coordinates.' })),
        h('div', { class: 'tcd-text' },
          richText(h('p', { class: 'tcd-tc' }), 'Tc ' + d.tc + ' K'),
          note ? richText(h('p', { class: 'tcd-note' }), note) : null,
          TC_BG[d.n] ? richText(h('p', { class: 'tcd-bg' }), TC_BG[d.n]) : null,
          r ? h('p', { class: 'tcd-ref' }, h('span', { class: 'tcd-cite', text: r.t }),
            url ? h('a', { class: 'tcd-link', href: url, text: 'Open the paper' }) : null)
            : h('p', { class: 'tcd-ref' }, h('span', { class: 'tcd-cite', text: 'This entry cites no single reporting paper.' }))))
    ]);
    miniPrune(); miniKick();
  };

  const renderTcChart = function renderTcChart() {
    var host = $('#tc-chart'), legend = $('#tc-legend'), bar = $('#tc-controls');
    if (!host) return;
    tcStop();
    clear(host); clear(legend);
    if (bar) clear(bar);
    var tg = $('#tc-toggle');
    clear(tg); tg.appendChild(document.createTextNode(learn.table ? 'Chart' : 'Table'));
    Object.keys(FAMILIES).forEach(function (k) {
      var on = !learn.tcHidden[k];
      legend.appendChild(h('button', { class: 'lg lg-btn', type: 'button', 'aria-pressed': on ? 'true' : 'false',
        title: (on ? 'Hide ' : 'Show ') + FAMILIES[k].label,
        onclick: function () { learn.tcHidden[k] = on; renderTcChart(); } },
        h('i', { class: FAMILIES[k].cls }), FAMILIES[k].label));
    });
    legend.appendChild(h('span', { class: 'lg' }, h('i', { class: 'lg-ring' }), 'Under high pressure'));
    legend.appendChild(h('span', { class: 'lg' }, h('i', { class: 'lg-step' }), 'Ambient-pressure record'));
    // The dashed rise above the record was unlabelled, which left it reading as part of the record.
    if (!learn.table && !learn.tcHidden.cuprate)
      legend.appendChild(h('span', { class: 'lg' }, h('i', { class: 'lg-step dash' }), 'Quenched from pressure (onset)'));
    if (learn.table) {
      var tbl = h('table', { class: 'tbl' });
      var thead = h('thead', null, h('tr', null, h('th', { text: 'Material' }), h('th', { text: 'Year' }), richText(h('th'), 'Tc (K)'), h('th', { text: 'Family' }), h('th', { text: 'Notes' }), h('th', { text: 'Reference' })));
      var tb = h('tbody');
      TC_DATA.forEach(function (d) {
        var r = d.ref ? REFS[d.ref] : null, url = r ? refUrl(r) : '';
        tb.appendChild(h('tr', null, h('td', { text: d.n }), h('td', { text: String(d.y) }), h('td', { class: 'num', text: String(d.tc) }),
          h('td', { text: FAMILIES[d.f].label }), richText(h('td'), [d.note, d.p ? 'high pressure' : ''].filter(Boolean).join('; ')),
          h('td', null, r ? (url ? h('a', { href: url, text: r.t }) : r.t) : '')));
      });
      append(tbl, [thead, tb]);
      host.appendChild(h('div', { class: 'tbl-wrap' }, tbl));
      return;
    }
    var W = Math.max(300, Math.round(host.getBoundingClientRect().width || 900));
    var narrow = W < 560, Hh = narrow ? 330 : 410;
    var m = { l: 46, r: narrow ? 14 : 26, t: 28, b: 38 }, pw = W - m.l - m.r, ph = Hh - m.t - m.b;
    // Tc spans three decades once the low-Tc classics are included, so the temperature axis is logarithmic.
    var X0 = 1906, X1 = 2031, YMIN = 0.2, YMAX = 330, LAST = 2026;
    var lo = Math.log(YMIN), span = Math.log(YMAX) - lo;
    function X(y) { return m.l + (y - X0) / (X1 - X0) * pw; }
    function Y(v) { return m.t + ph - (Math.log(Math.max(YMIN, Math.min(YMAX, v))) - lo) / span * ph; }
    var svg = s('svg', { class: 'plot', width: W, height: Hh, viewBox: '0 0 ' + W + ' ' + Hh, role: 'img', tabindex: '0',
      'aria-label': 'Critical temperature of ' + TC_DATA.length + ' notable superconductors against the year they were reported, on a logarithmic temperature axis, ' +
        'from strontium titanate at 0.3 K and mercury at 4.2 K in 1911 to cuprates above liquid nitrogen and hydrides above 200 K under pressure. ' +
        'Use the left and right arrow keys to move along the dots and Enter to open the structure and paper of one.' });
    var defs = s('defs', {}), clip = s('clipPath', { id: 'tc-sweep-clip' });
    var clipRect = s('rect', { x: m.l - 7, y: 0, width: pw + 14, height: Hh });
    clip.appendChild(clipRect); defs.appendChild(clip); svg.appendChild(defs);
    [0.3, 1, 3, 10, 30, 100, 300].forEach(function (v) {
      var major = v === 1 || v === 10 || v === 100;
      svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: Y(v), y2: Y(v), class: major ? 'grid-line' : 'grid-line faint' }));
      if (major || !narrow) svg.appendChild(s('text', { x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'tick' }, String(v)));
    });
    svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: m.t + ph, y2: m.t + ph, class: 'axis-line' }));
    var ystep = W < 820 ? 20 : 10, yy;
    for (yy = 1910; yy <= 2030; yy += ystep) {
      svg.appendChild(s('line', { x1: X(yy), x2: X(yy), y1: m.t + ph, y2: m.t + ph + 4, class: 'axis-line' }));
      svg.appendChild(s('text', { x: X(yy), y: m.t + ph + 18, 'text-anchor': 'middle', class: 'tick' }, String(yy)));
    }
    for (yy = 1910 + ystep / 2; yy < 2030; yy += ystep)
      svg.appendChild(s('line', { x1: X(yy), x2: X(yy), y1: m.t + ph, y2: m.t + ph + 2.5, class: 'axis-line minor' }));
    svg.appendChild(s('text', { x: m.l - 8, y: m.t - 10, 'text-anchor': 'end', class: 'tick' }, 'K'));
    svg.appendChild(s('text', { x: m.l + pw, y: m.t - 10, 'text-anchor': 'end', class: 'tick' }, 'logarithmic temperature axis'));
    // Everything a material label must not cover: the axis notes, the reference captions and the record staircase.
    var guards = [{ x: m.l + pw - 160, y: m.t - 22, w: 160, h: 16 }];
    [[4.2, 'liquid helium 4.2 K', 1], [77, 'liquid nitrogen 77 K', 0], [295, 'room temperature', 0]].forEach(function (rl) {
      var ly = Y(rl[0]), right = rl[2], tw = rl[1].length * 5.6 + 6;
      var tx = right ? m.l + pw - 6 - tw : m.l + 6, ty = ly - m.t < 16 ? ly + 13 : ly - 5;
      svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: ly, y2: ly, class: 'ref-line', 'stroke-dasharray': '4 4' }));
      svg.appendChild(s('text', { x: right ? m.l + pw - 6 : m.l + 6, y: ty, 'text-anchor': right ? 'end' : 'start', class: 'ref-label' }, rl[1]));
      guards.push({ x: tx, y: ty - 11, w: tw, h: 14 });
    });
    var rec = TC_DATA.filter(function (d) { return TC_RECORD.indexOf(d.n) >= 0; });
    var path = '';
    rec.forEach(function (d, i) {
      path += (i ? 'H' + X(d.y).toFixed(1) + 'V' : 'M' + X(d.y).toFixed(1) + ' ') + Y(d.tc).toFixed(1);
    });
    path += 'H' + X(LAST).toFixed(1);
    rec.forEach(function (d, i) {
      var x2 = i + 1 < rec.length ? X(rec[i + 1].y) : X(LAST);
      guards.push({ x: X(d.y), y: Y(d.tc) - 4, w: Math.max(1, x2 - X(d.y)), h: 8 });
    });
    svg.appendChild(s('path', { d: path, class: 'record-line', 'clip-path': 'url(#tc-sweep-clip)' }));
    // The quenched onset rises above the standing ambient record, so it is drawn as a dashed
    // rise from that record rather than as a step of it. It starts at the record's own Tc.
    var q = tcEntry('Hg-1223, pressure-quenched'), top = rec.length ? rec[rec.length - 1] : null;
    if (q && top && !learn.tcHidden[q.f])
      svg.appendChild(s('path', { d: 'M' + X(LAST).toFixed(1) + ' ' + Y(top.tc).toFixed(1) + 'V' + Y(q.tc).toFixed(1),
        class: 'record-line', 'stroke-dasharray': '3 3', 'clip-path': 'url(#tc-sweep-clip)' }));
    var pts = TC_DATA.filter(function (d) { return !learn.tcHidden[d.f]; }).map(function (d) {
      return { d: d, x: X(d.y), y: Y(d.tc), el: null, tx: null, halo: null, mark: false };
    });
    // A material switched off in the legend cannot stay open in the panel below.
    if (learn.tcSel && !pts.filter(function (p) { return p.d.n === learn.tcSel; }).length) learn.tcSel = '';
    // Every halo is drawn before every dot, so one material's glow never covers its neighbour.
    pts.forEach(function (p) {
      p.halo = s('circle', { cx: p.x, cy: p.y, r: 5, opacity: '0', 'data-tc': p.d.n,
        class: 'tc-halo ' + FAMILIES[p.d.f].cls });
      svg.appendChild(p.halo);
    });
    pts.forEach(function (p) {
      p.el = s('circle', { cx: p.x, cy: p.y, r: 5, 'data-tc': p.d.n,
        class: 'tc-dot ' + FAMILIES[p.d.f].cls + (p.d.p ? ' hp' : '') + (p.d.pre ? ' pre' : '') + (p.d.n === learn.tcSel ? ' sel' : '') });
      svg.appendChild(p.el);
    });
    // Every material carries its name, but only a few show at once: the names twinkle in and
    // out like stars, so all of them can be read over a cycle without crowding the chart.
    var dotBoxes = pts.map(function (p) { return { x: p.x - 6, y: p.y - 6, w: 12, h: 12 }; });
    var taken = dotBoxes.concat(guards), markRects = [];
    function hits(r, list) {
      for (var i = 0; i < list.length; i++) {
        var q = list[i];
        if (r.x < q.x + q.w && q.x < r.x + r.w && r.y < q.y + q.h && q.y < r.y + r.h) return true;
      }
      return false;
    }
    // wide: the era-opening names are placed first and must not be left off, so they are
    // allowed to sit further from their dot than a twinkling name ever would.
    function spotFor(p, wide, avoid) {
      var name = p.d.n, text = name === 'Hg-1223, pressure-quenched' ? 'Hg-1223 (2026)' : name + (p.d.pre ? ' (preprint)' : '');
      // Measured against the rendered boxes: subscripts and the bold landmark names run up to
      // 9% wider than a flat 6.1 px a character, which used to let a name land on another one.
      var w = text.length * 6.7 + 6, hgt = 15, found = null;
      [[9, -4, 'start'], [-9, -4, 'end'], [9, 11, 'start'], [-9, 11, 'end'], [0, -11, 'middle'], [0, 18, 'middle']]
        .concat(wide ? [[0, -21, 'middle'], [0, 27, 'middle'], [14, -16, 'start'], [-14, -16, 'end'],
          [14, 22, 'start'], [-14, 22, 'end'], [0, -31, 'middle'], [0, 37, 'middle']] : [])
        .forEach(function (o) {
          if (found) return;
          var lx = p.x + o[0], rx = o[2] === 'start' ? lx : o[2] === 'end' ? lx - w : lx - w / 2;
          var r = { x: rx, y: p.y + o[1] - hgt / 2, w: w, h: hgt };
          if (r.x < m.l + 2 || r.x + r.w > m.l + pw - 2 || r.y < 6 || r.y + r.h > m.t + ph - 2) return;
          if (!hits(r, avoid || taken)) found = { o: o, r: r, text: text };
        });
      return found;
    }
    function place(p, wide, avoid) {
      p.lab = spotFor(p, wide, avoid);
      if (!p.lab) return;
      p.tx = s('text', { x: p.x + p.lab.o[0], y: p.y + p.lab.o[1] + 4, 'text-anchor': p.lab.o[2],
        class: 'tc-label' + (p.mark ? ' mark' : ''), opacity: '0', 'data-tc': p.d.n, 'aria-hidden': 'true' }, p.lab.text);
      svg.appendChild(p.tx);
    }
    // The few that opened an era are placed before anything else and their space is then
    // reserved, so their names can stay on the chart for good without a twinkling one ever
    // landing on top of them. Every one of them tries the close positions first, so an early
    // name does not take a distant slot that a later one needs near its own dot.
    // On a phone the last of them may find nothing left; rather than drop the name, the third
    // pass lets it sit over the axis notes and the record staircase, which its outline survives.
    // No pass ever lets a name sit on a dot.
    var marks = [];
    [0, 1, 2].forEach(function (pass) {
      TC_LANDMARK.forEach(function (n) {
        pts.forEach(function (p) {
          if (p.d.n !== n || p.tx) return;
          p.mark = true; place(p, pass > 0, pass > 1 ? dotBoxes.concat(markRects) : null);
          if (!p.lab) return;
          taken.push(p.lab.r); markRects.push(p.lab.r);   // only these reserve their space
          p.phase = (p.d.y % 7) * 0.9;
          marks.push(p);
        });
      });
    });
    pts.forEach(function (p) { if (!p.tx) { p.mark = false; place(p, false, null); } });
    // Curated names come round first, then the rest in the order they were found.
    var rot = [], live = [], cursor = 0, started = 0, clock = 0, pinned = null;
    var FADE = 0.6, HOLD = 3.4, LIFE = FADE * 2 + HOLD;
    var twinkling = motionOK(), atOnce = narrow ? 2 : W > 900 ? 5 : 4;
    TC_LABELS.forEach(function (n) {
      pts.forEach(function (p) { if (p.d.n === n && p.lab && !p.mark && rot.indexOf(p) < 0) rot.push(p); });
    });
    pts.forEach(function (p) { if (p.lab && !p.mark && rot.indexOf(p) < 0) rot.push(p); });
    if (!twinkling) {
      var used = [];
      TC_LANDMARK.concat(TC_LABELS).forEach(function (n) {
        if (narrow && !TC_LABELS_NARROW[n] && TC_LANDMARK.indexOf(n) < 0) return;
        var p = null;
        pts.forEach(function (c) { if (c.d.n === n) p = c; });
        if (!p || !p.lab || hits(p.lab.r, used)) return;
        used.push(p.lab.r); p.still = true;
      });
    }
    // A dot lights up with its own name and goes dark again with it, so there is never any
    // doubt about which dot a name belongs to.
    function glow(p, a) {
      p.halo.setAttribute('opacity', (a * 0.38).toFixed(3));
      p.halo.setAttribute('r', (5 + 7 * a).toFixed(2));
    }
    // Reaching for a name takes a moment, and a name that fades during that moment cannot be
    // used. So the rotation stands still while the pointer is in the chart, and for a few
    // seconds after a tap, because a touch screen has no pointer to hold over anything.
    var inside = false, holdTill = 0, GRACE = 2.4;
    function hold() { holdTill = clock + 5; }
    function twinkleStep(dt) {
      var i, e, frozen = inside || clock < holdTill;
      clock += dt;
      for (i = live.length - 1; i >= 0; i--) {
        e = live[i]; e.age += frozen ? 0 : dt;
        // A name for a year the slider has been dragged back past goes either way.
        if ((e.age >= e.life && !frozen) || e.p.d.y > learn.tcYear) {
          e.p.tx.setAttribute('opacity', '0'); glow(e.p, 0); live.splice(i, 1);
        }
      }
      var busy = live.map(function (q) { return q.p.lab.r; });
      if (pinned && pinned.lab) busy.push(pinned.lab.r);
      // The rotation moves on by one name at a time, so every one of them gets its turn; among
      // the next few it picks the one furthest from the names already up, which keeps them spread.
      while (!frozen && live.length < atOnce) {
        var best = -1, bestFar = -1, seen = 0, k, at, c, skip, near, dx, dy;
        for (k = 0; k < rot.length && seen < 8; k++) {
          at = (cursor + k) % rot.length; c = rot[at]; skip = false;
          if (c.d.y > learn.tcYear || c.d.n === learn.tcSel) continue;
          if (c.shown !== undefined && clock - c.shown < 24) continue;   // every name has its turn before any repeats
          for (i = 0; i < live.length; i++) if (live[i].p === c) skip = true;
          if (skip || hits(c.lab.r, busy)) continue;
          seen++;
          near = 1e9;
          for (i = 0; i < live.length; i++) {
            dx = live[i].p.x - c.x; dy = (live[i].p.y - c.y) * 1.7;
            near = Math.min(near, Math.sqrt(dx * dx + dy * dy));
          }
          if (near > bestFar) { bestFar = near; best = at; }
        }
        if (best < 0) break;
        var p = rot[best];
        // Staggered starts and uneven lifetimes keep the names from blinking in step.
        var jit = ((p.d.y * 37 + Math.round(p.d.tc * 10)) % 11) / 10;
        live.push({ p: p, age: started < atOnce ? -0.8 * started : 0, life: LIFE * (0.8 + 0.5 * jit) });
        busy.push(p.lab.r);
        p.shown = clock;
        started++; cursor = (cursor + 1) % rot.length;
      }
      live.forEach(function (q) {
        var a = q.age <= 0 ? 0 : q.age < FADE ? q.age / FADE
          : q.age > q.life - FADE ? Math.max(0, (q.life - q.age) / FADE) : 1;
        q.p.tx.setAttribute('opacity', a.toFixed(3));
        glow(q.p, a);
        if (a >= 0.25) q.p.lit = clock;   // when this name was last readable
      });
      // The names that opened an era never leave, and their dots keep a slow pulse of their own.
      marks.forEach(function (p) {
        var on = p.d.y <= learn.tcYear;
        p.tx.setAttribute('opacity', on ? '1' : '0');
        glow(p, on ? 0.5 + 0.35 * Math.sin(clock * 1.9 + p.phase) : 0);
      });
      // The chosen material keeps its name on screen for as long as it stays chosen.
      if (pinned && pinned.d.n !== learn.tcSel) {
        var held = false;
        for (i = 0; i < live.length; i++) if (live[i].p === pinned) held = true;
        if (!held && !pinned.mark) { pinned.tx.setAttribute('opacity', '0'); glow(pinned, 0); }
        pinned = null;
      }
      if (learn.tcSel) {
        var sel = null;
        pts.forEach(function (c) { if (c.d.n === learn.tcSel && c.tx) sel = c; });
        if (sel) {
          sel.tx.setAttribute('opacity', '1');
          if (!sel.mark) glow(sel, 0.55);
          pinned = sel;
        }
      }
    }
    var sweepLine = s('line', { y1: m.t, y2: m.t + ph, class: 'tc-sweep', visibility: 'hidden' });
    var sweepYear = s('text', { y: m.t - 5, 'text-anchor': 'middle', class: 'tc-sweep-year', visibility: 'hidden' }, '');
    svg.appendChild(sweepLine); svg.appendChild(sweepYear);
    var ring = s('circle', { r: 9, class: 'hover-dot', visibility: 'hidden' });
    svg.appendChild(ring);
    var tip = h('div', { class: 'tooltip tc-tip', hidden: true });
    host.appendChild(svg);
    host.appendChild(tip);

    /* ---------- the year sweep ---------- */
    if (!learn.tcYear) { learn.tcYear = motionOK() ? X0 : LAST; learn.tcPlay = motionOK(); }
    var readout = h('span', { class: 'tc-readout', role: 'status' });
    var playBtn = h('button', { class: 'btn small tc-play', type: 'button' });
    var slider = h('input', { type: 'range', class: 'tc-range', min: String(X0), max: String(LAST), step: '1',
      value: String(Math.round(learn.tcYear)), 'aria-label': 'Show superconductors reported up to this year' });
    function recordBy(year) {
      var best = 0;
      rec.forEach(function (d) { if (d.y <= year && !d.p && d.tc > best) best = d.tc; });
      return best;
    }
    function apply() {
      var yr = learn.tcYear, done = yr >= LAST;
      clipRect.setAttribute('width', Math.max(0, X(yr) - (m.l - 7)).toFixed(1));
      pts.forEach(function (p) {
        var k = Math.max(0, Math.min(1, (yr - p.d.y + 1.4) / 1.4));
        p.el.setAttribute('opacity', k.toFixed(3));
        p.el.setAttribute('r', (2.2 + 2.8 * k).toFixed(2));
        if (p.tx && !twinkling) p.tx.setAttribute('opacity', p.still && p.d.y <= yr ? '1' : '0');
      });
      sweepLine.setAttribute('visibility', done ? 'hidden' : 'visible');
      sweepYear.setAttribute('visibility', done ? 'hidden' : 'visible');
      if (!done) {
        sweepLine.setAttribute('x1', X(yr).toFixed(1)); sweepLine.setAttribute('x2', X(yr).toFixed(1));
        sweepYear.setAttribute('x', Math.min(Math.max(X(yr), m.l + 16), m.l + pw - 16).toFixed(1));
        sweepYear.textContent = String(Math.round(yr));
      }
      if (slider.value !== String(Math.round(yr))) slider.value = String(Math.round(yr));
      var best = recordBy(yr), seen = 0;
      pts.forEach(function (p) { if (p.d.y <= yr) seen++; });
      clear(readout);
      readout.appendChild(document.createTextNode(done ? seen + ' superconductors shown' :
        Math.round(yr) + ' · ' + seen + ' shown · ambient-pressure record ' + (best ? best + ' K' : 'none yet')));
    }
    function syncPlay() {
      clear(playBtn);
      var done = learn.tcYear >= LAST && !learn.tcPlay;
      playBtn.appendChild(glyph(learn.tcPlay ? 'pause' : done ? 'refresh' : 'play', 'tc-play-icon'));
      playBtn.appendChild(document.createTextNode(learn.tcPlay ? 'Pause' : done ? 'Replay' : 'Play'));
      playBtn.setAttribute('aria-label', learn.tcPlay ? 'Pause the year-by-year animation' :
        done ? 'Play the year-by-year animation again from 1911' : 'Play the year-by-year animation');
    }
    function step(ts) {
      learn.tcRaf = 0;
      if (!svg.isConnected || view !== 'learn') { learn.tcLast = 0; return; }
      var dt = learn.tcLast ? Math.min(0.08, (ts - learn.tcLast) / 1000) : 0;
      learn.tcLast = ts;
      if (learn.tcPlay) {
        learn.tcYear = Math.min(LAST, learn.tcYear + dt * 9.5);
        apply();
        if (learn.tcYear >= LAST) { learn.tcPlay = false; syncPlay(); }
      }
      if (twinkling) twinkleStep(dt);
      if (learn.tcPlay || twinkling) learn.tcRaf = requestAnimationFrame(step);
      else learn.tcLast = 0;
    }
    function run() { tcStop(); if (learn.tcPlay || twinkling) learn.tcRaf = requestAnimationFrame(step); }
    playBtn.addEventListener('click', function () {
      if (learn.tcPlay) learn.tcPlay = false;
      else { if (learn.tcYear >= LAST) learn.tcYear = X0; learn.tcPlay = true; }
      syncPlay(); apply(); run();
    });
    slider.addEventListener('input', function () {
      learn.tcPlay = false;
      learn.tcYear = Math.max(X0, Math.min(LAST, Number(slider.value) || X0));
      syncPlay(); apply(); run();
    });
    if (bar) append(bar, [playBtn, slider, readout]);
    syncPlay(); apply(); run();

    /* ---------- hover, keyboard and selection ---------- */
    var order = pts.slice().sort(function (a, b) { return a.d.y - b.d.y || a.d.tc - b.d.tc; }), cur = -1;
    // The name under the pointer is underlined, so it reads as something that can be chosen.
    var hot = null;
    function setHot(p) {
      var q = p && p.tx ? p : null;
      if (q === hot) return;
      if (hot && hot.tx && hot.tx.classList) hot.tx.classList.remove('hot');
      hot = q;
      if (hot && hot.tx.classList) hot.tx.classList.add('hot');
    }
    function show(p) {
      if (!p) return;
      setHot(p);
      cur = order.indexOf(p);
      ring.setAttribute('cx', p.x); ring.setAttribute('cy', p.y); ring.setAttribute('visibility', 'visible');
      clear(tip);
      var r = p.d.ref ? REFS[p.d.ref] : null;
      append(tip, [
        h('b', { text: p.d.n }),
        richText(h('span', { class: 'tip-row' }), 'Tc ' + p.d.tc + ' K · ' + p.d.y + (p.d.p ? ' · high pressure' : '')),
        h('span', { class: 'tip-row' }, h('i', { class: 'key ' + FAMILIES[p.d.f].cls }), FAMILIES[p.d.f].label),
        p.d.note ? richText(h('span', { class: 'tip-row' }), p.d.note) : null,
        r ? h('span', { class: 'tip-row tip-ref', text: r.t }) : null,
        h('span', { class: 'tip-row tip-hint', text: 'Choose it for its structure and paper' })
      ]);
      tip.hidden = false;
      var tw = Math.min(260, W - 16);
      tip.style.maxWidth = tw + 'px';
      tip.style.left = Math.min(Math.max(p.x, tw / 2 + 4), W - tw / 2 - 4) + 'px';
      tip.style.top = (p.y < 130 ? p.y + 150 : p.y) + 'px';
    }
    function hide() { cur = -1; setHot(null); ring.setAttribute('visibility', 'hidden'); tip.hidden = true; }
    function pick(p) {
      if (!p) return;
      learn.tcSel = p.d.n;
      // The hover card has no pointerleave to dismiss it on a touch screen, so it would sit over
      // the neighbouring dots. Everything it said is in the panel below; the thin ring stays.
      tip.hidden = true;
      tcMark(); renderTcDetail();
      var panel = $('#tc-detail');
      if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
    }
    // Arrow keys walk the dots that have arrived, so the sweep is not read out ahead of itself.
    function move(dir) {
      var n = order.length, i = cur < 0 ? (dir > 0 ? -1 : n) : cur, k;
      for (k = 0; k < n; k++) {
        i += dir;
        if (i < 0 || i >= n) return;
        if (order[i].d.y <= learn.tcYear) { show(order[i]); return; }
      }
    }
    // A name is a target too. The dots are small and several of them sit almost on top of one
    // another, so a name that can be read at that moment can be used to reach its material. A
    // name that has only just gone counts as well, since the hand was already on its way to it;
    // one gone longer than that does not, or the chart would be full of invisible targets.
    function labelAt(px, py) {
      var hit = null, gone = null;
      pts.forEach(function (p) {
        if (!p.tx || p.d.y > learn.tcYear) return;
        var r = p.lab.r;
        if (px < r.x - 3 || px > r.x + r.w + 3 || py < r.y - 3 || py > r.y + r.h + 3) return;
        if (parseFloat(p.tx.getAttribute('opacity') || '0') >= 0.25) { if (!hit) hit = p; }
        else if (!gone && p.lit !== undefined && clock - p.lit < GRACE) gone = p;
      });
      return hit || gone;   // a name that is there now comes before one that has just gone
    }
    function nearest(evt) {
      var box = svg.getBoundingClientRect();
      var px = (evt.clientX - box.left) * (W / box.width), py = (evt.clientY - box.top) * (Hh / box.height);
      var named = labelAt(px, py);
      if (named) return named;
      var best = null, bd = 28 * 28;
      pts.forEach(function (p) {
        if (p.d.y > learn.tcYear) return;
        var dd = (p.x - px) * (p.x - px) + (p.y - py) * (p.y - py);
        if (dd < bd) { bd = dd; best = p; }
      });
      return best;
    }
    svg.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') inside = true; });
    svg.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'mouse') inside = true;
      var p = nearest(e);
      svg.style.cursor = p ? 'pointer' : '';
      if (p) show(p); else hide();
    });
    svg.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') hold(); var p = nearest(e); if (p) { show(p); pick(p); } else hide(); });
    svg.addEventListener('pointerleave', function (e) { inside = false; if (e.pointerType === 'mouse') hide(); });
    svg.addEventListener('pointercancel', function () { inside = false; });
    svg.addEventListener('blur', function () { inside = false; hide(); });
    svg.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { move(1); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { move(-1); e.preventDefault(); }
      else if (e.key === 'Enter' || e.key === ' ') { if (cur >= 0) { pick(order[cur]); e.preventDefault(); } }
      else if (e.key === 'Escape') hide();
    });
    renderTcDetail();
  };

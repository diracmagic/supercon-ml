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
          h('p', { text: 'Every dot is a superconductor; hover or tap for details and the original paper.' })),
        toggle),
      h('div', { class: 'tc-legend', id: 'tc-legend' }),
      h('div', { class: 'chart', id: 'tc-chart' })
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


  const renderTcChart = function renderTcChart() {
    var host = $('#tc-chart'), legend = $('#tc-legend');
    if (!host) return;
    clear(host); clear(legend);
    var tg = $('#tc-toggle');
    clear(tg); tg.appendChild(document.createTextNode(learn.table ? 'Chart' : 'Table'));
    Object.keys(FAMILIES).forEach(function (k) { legend.appendChild(h('span', { class: 'lg' }, h('i', { class: FAMILIES[k].cls }), FAMILIES[k].label)); });
    legend.appendChild(h('span', { class: 'lg' }, h('i', { class: 'lg-ring' }), 'Under high pressure'));
    legend.appendChild(h('span', { class: 'lg' }, h('i', { class: 'lg-step' }), 'Ambient-pressure record'));
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
    var narrow = W < 560, Hh = narrow ? 300 : 380;
    var m = { l: 46, r: narrow ? 12 : 24, t: 16, b: 34 }, pw = W - m.l - m.r, ph = Hh - m.t - m.b;
    var X0 = 1905, X1 = 2030, YMAX = 320;
    function X(y) { return m.l + (y - X0) / (X1 - X0) * pw; }
    function Y(v) { return m.t + ph - Math.min(v, YMAX) / YMAX * ph; }
    var svg = s('svg', { class: 'plot', width: W, height: Hh, viewBox: '0 0 ' + W + ' ' + Hh, role: 'img', tabindex: '0',
      'aria-label': 'Critical temperature of notable superconductors by year of discovery, from mercury at 4.2 K in 1911 to hydrides above 200 K under pressure' });
    [50, 100, 150, 200, 250, 300].forEach(function (v) {
      svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: Y(v), y2: Y(v), class: 'grid-line' }));
      svg.appendChild(s('text', { x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'tick' }, String(v)));
    });
    svg.appendChild(s('text', { x: m.l - 8, y: Y(0) + 4, 'text-anchor': 'end', class: 'tick' }, '0'));
    svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: Y(0), y2: Y(0), class: 'axis-line' }));
    (narrow ? [1920, 1960, 2000] : [1910, 1930, 1950, 1970, 1990, 2010, 2030]).forEach(function (y) {
      svg.appendChild(s('text', { x: X(y), y: m.t + ph + 18, 'text-anchor': 'middle', class: 'tick' }, String(y)));
    });
    svg.appendChild(s('text', { x: m.l - 8, y: m.t + 2, 'text-anchor': 'end', class: 'tick' }, 'K'));
    [[77, 'liquid nitrogen 77 K'], [295, 'room temperature']].forEach(function (rl) {
      svg.appendChild(s('line', { x1: m.l, x2: m.l + pw, y1: Y(rl[0]), y2: Y(rl[0]), class: 'ref-line', 'stroke-dasharray': '4 4' }));
      svg.appendChild(s('text', { x: m.l + 6, y: Y(rl[0]) - 5, class: 'ref-label' }, rl[1]));
    });
    var rec = TC_DATA.filter(function (d) { return TC_RECORD.indexOf(d.n) >= 0; });
    var path = '';
    rec.forEach(function (d, i) {
      path += (i ? 'H' + X(d.y).toFixed(1) + 'V' : 'M' + X(d.y).toFixed(1) + ' ') + Y(d.tc).toFixed(1);
    });
    path += 'H' + X(2026).toFixed(1);
    svg.appendChild(s('path', { d: path, class: 'record-line' }));
    var q = TC_DATA.filter(function (d) { return d.n === 'Hg-1223, pressure-quenched'; })[0];
    if (q) svg.appendChild(s('path', { d: 'M' + X(2026).toFixed(1) + ' ' + Y(133).toFixed(1) + 'V' + Y(q.tc).toFixed(1), class: 'record-line', 'stroke-dasharray': '3 3' }));
    var pts = TC_DATA.map(function (d) { return { d: d, x: X(d.y), y: Y(d.tc) }; });
    pts.forEach(function (p) {
      var cls = 'tc-dot ' + FAMILIES[p.d.f].cls + (p.d.p ? ' hp' : '') + (p.d.pre ? ' pre' : '');
      svg.appendChild(s('circle', { cx: p.x, cy: p.y, r: 5, class: cls }));
    });
    pts.forEach(function (p) {
      var lab = TC_LABELS[p.d.n];
      if (!lab || (narrow && !TC_LABELS_NARROW[p.d.n])) return;
      var text = p.d.n === 'Hg-1223, pressure-quenched' ? 'Hg-1223 (2026)' : p.d.n + (p.d.pre ? ' (preprint)' : '');
      svg.appendChild(s('text', { x: p.x + lab[0], y: p.y + lab[1], 'text-anchor': lab[2], class: 'tc-label' }, text));
    });
    var ring = s('circle', { r: 9, class: 'hover-dot', visibility: 'hidden' });
    svg.appendChild(ring);
    var tip = h('div', { class: 'tooltip tc-tip', hidden: true });
    host.appendChild(svg);
    host.appendChild(tip);
    var order = pts.slice().sort(function (a, b) { return a.d.y - b.d.y || a.d.tc - b.d.tc; }), cur = -1;
    function show(p) {
      cur = order.indexOf(p);
      ring.setAttribute('cx', p.x); ring.setAttribute('cy', p.y); ring.setAttribute('visibility', 'visible');
      clear(tip);
      var r = p.d.ref ? REFS[p.d.ref] : null;
      append(tip, [
        h('b', { text: p.d.n }),
        richText(h('span', { class: 'tip-row' }), 'Tc ' + p.d.tc + ' K · ' + p.d.y + (p.d.p ? ' · high pressure' : '')),
        h('span', { class: 'tip-row' }, h('i', { class: 'key ' + FAMILIES[p.d.f].cls }), FAMILIES[p.d.f].label),
        p.d.note ? richText(h('span', { class: 'tip-row' }), p.d.note) : null,
        r ? h('span', { class: 'tip-row tip-ref', text: r.t }) : null
      ]);
      tip.hidden = false;
      var tw = Math.min(260, W - 16);
      tip.style.maxWidth = tw + 'px';
      tip.style.left = Math.min(Math.max(p.x, tw / 2 + 4), W - tw / 2 - 4) + 'px';
      tip.style.top = (p.y < 120 ? p.y + 150 : p.y) + 'px';
    }
    function hide() { cur = -1; ring.setAttribute('visibility', 'hidden'); tip.hidden = true; }
    function nearest(evt) {
      var box = svg.getBoundingClientRect();
      var px = (evt.clientX - box.left) * (W / box.width), py = (evt.clientY - box.top) * (Hh / box.height);
      var best = null, bd = 28 * 28;
      pts.forEach(function (p) { var dd = (p.x - px) * (p.x - px) + (p.y - py) * (p.y - py); if (dd < bd) { bd = dd; best = p; } });
      return best;
    }
    svg.addEventListener('pointermove', function (e) { var p = nearest(e); if (p) show(p); else hide(); });
    svg.addEventListener('pointerdown', function (e) { var p = nearest(e); if (p) show(p); else hide(); });
    svg.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') hide(); });
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { show(order[Math.min(order.length - 1, cur + 1)]); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { show(order[Math.max(0, cur < 0 ? 0 : cur - 1)]); e.preventDefault(); }
      else if (e.key === 'Escape') hide();
    });
  };

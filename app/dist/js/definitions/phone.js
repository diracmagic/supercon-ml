'use strict';
// phone: shared lexical function definitions; no startup side effects.

  const qrSvg = function qrSvg() {
    var n = QR.n, pad = 3, size = n + 2 * pad, bits = '';
    for (var i = 0; i < QR.hex.length; i++) bits += ('000' + parseInt(QR.hex[i], 16).toString(2)).slice(-4);
    var d = '';
    for (var y = 0; y < n; y++) for (var x = 0; x < n; x++) if (bits[y * n + x] === '1') d += 'M' + (x + pad) + ' ' + (y + pad) + 'h1v1h-1z';
    var svg = s('svg', { class: 'qr', viewBox: '0 0 ' + size + ' ' + size, role: 'img', 'aria-label': 'QR code for ' + PHONE_URL, 'shape-rendering': 'crispEdges' });
    svg.appendChild(s('rect', { width: size, height: size, rx: 2, fill: '#ffffff' }));
    svg.appendChild(s('path', { d: d, fill: '#0b0b0b' }));
    return svg;
  };

  const renderPhoneCard = function renderPhoneCard() {
    var el = $('#phone-card');
    if (!el) return;
    clear(el);
    append(el, [
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'On your phone or iPad' }),
        h('p', { text: 'Scan to follow the live progress on any phone or tablet.' }))),
      h('div', { class: 'phone-row' }, qrSvg(),
        h('div', null,
          h('p', null, h('a', { href: PHONE_URL, text: 'diracmagic.github.io/supercon-ml' })),
          h('p', { class: 'note', text: 'iPhone and iPad: Share → Add to Home Screen. Android: menu → Install app. It opens full screen like an app and refreshes on its own.' })))
    ]);
  };


  const setView = function setView(v) {
    var prev = view;
    view = v;
    store.set('view', v);
    ['progress', 'candidates', 'ai', 'demos', 'learn', 'papers', 'authors'].forEach(function (k) {
      var b = $('#view-' + k);
      if (b) b.setAttribute('aria-selected', v === k ? 'true' : 'false');
    });
    $('#ai').hidden = v !== 'ai';
    $('#demos').hidden = v !== 'demos';
    $('#learn').hidden = v !== 'learn';
    $('#papers').hidden = v !== 'papers';
    $('#authors').hidden = v !== 'authors';
    $('#main').hidden = v !== 'progress' || !state.data;
    $('#candidates').hidden = v !== 'candidates' || !state.data;
    if (v === 'candidates') { xtDirty(); xtSync(); xtKick(); }
    if (prev === 'ai' && v !== 'ai') aiStop();
    if (v === 'ai') {
      if (!aiState.built) buildAI(); else renderAI();
      loadPapers(false);
      loadContent(false);
      aiStart();
    }
    if (v === 'demos') {
      if (!demo.built) buildDemos();
      else syncControls();
      sizeCanvas();
      kick();
    }
    if (v === 'learn' && !learn.built) buildLearn();
    if (v === 'learn') { miniKick(); loadContent(false); }
    if (v === 'papers') { if (!paperState.built) buildPapers(); loadPapers(false); loadContent(false); miniKick(); }
    if (v === 'authors') { renderAuthors(); miniKick(); }
  };

'use strict';
// ai-view: shared lexical function definitions; no startup side effects.


  const aiItems = function aiItems() {
    var d = paperState.data;
    return d ? list(d.ai).filter(function (x) { return x && x.title && isHttps(x.url); })
      .sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; }) : [];
  };

  const buildAI = function buildAI() {
    var el = $('#ai');
    clear(el);
    var live = h('section', { class: 'card ai-live' },
      h('div', { class: 'card-head' },
        h('div', null, h('h2', { text: 'AI for superconductivity' }),
          h('p', { text: 'Machine learning, AI agents and autonomous labs for superconductors: new papers and news, newest first.' })),
        h('button', { class: 'btn small', type: 'button', id: 'ai-refresh', onclick: function () { loadPapers(true); loadContent(true); } }, 'Refresh')),
      h('p', { class: 'ai-status', id: 'ai-status' }),
      h('div', { class: 'ai-ticker', id: 'ai-ticker' }),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter by kind', id: 'ai-filter' }),
      h('ol', { class: 'feed-list', id: 'ai-list' }),
      h('div', { class: 'feed-more', id: 'ai-more' }),
      h('p', { class: 'note', text: 'Collected every three hours from arXiv (all categories), Nature, Science, Physical Review and Nature-family journals, and science-news sites. An item is kept when it names an AI or machine-learning method and is about superconducting materials or their theory; quantum-computing and superconducting-electronics papers are left out. “AI prediction” marks new candidate superconductors proposed by a model, and “AI + experiment” candidates that were then made and measured. Tags are assigned automatically, so treat them as a rough guide.' }));
    var ours = h('section', { class: 'card', id: 'ai-ours' });
    var found = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Superconductors found with AI by other groups' }),
        h('p', { text: 'New superconductors whose discovery a machine-learning model guided and that experiments then confirmed, each with its paper. None of them is ours: the candidates our own models found are in the Candidates view.' }))),
      h('ol', { class: 'adv-list', id: 'ai-found' }),
      h('p', { class: 'note', id: 'ai-found-note' }),
      h('h3', { class: 'found-sub', text: 'Predicted by AI, waiting for experiment' }),
      h('p', { class: 'found-sub-intro', text: 'Notable AI predictions that, as far as we know, no experiment has tested yet. The feed above tags new AI predictions and new experiments as they appear; a material moves up to the list above once a measurement confirms it.' }),
      h('ol', { class: 'adv-list', id: 'ai-watch' }));
    var cur = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Selected AI advances' }),
        h('p', { text: 'Results we checked by hand, each with its paper. New ones are added to the app without an update.' }))),
      h('ol', { class: 'adv-list', id: 'ai-curated' }));
    append(el, [live, ours, found, cur]);
    aiState.built = true;
    renderAI();
  };

  const renderAI = function renderAI() {
    if (!aiState.built) return;
    renderAIList();
    renderAIOurs();
    renderAIFound();
    renderAICurated();
  };

  const renderAIFound = function renderAIFound() {
    var ol = $('#ai-found'), note = $('#ai-found-note'), wl = $('#ai-watch');
    if (!ol) return;
    function rows(target, items, kind) {
      clear(target);
      items.forEach(function (r) {
        var refs = (r.refs || [r.ref]).map(function (k) { return REFS[k]; }).filter(Boolean), refP = h('p', { class: 'adv-ref' });
        refs.forEach(function (ref, i) {
          if (i) refP.appendChild(document.createTextNode('; '));
          var url = refUrl(ref);
          refP.appendChild(url ? h('a', { href: url, text: ref.t }) : h('span', { text: ref.t }));
        });
        target.appendChild(h('li', null,
          h('p', { class: 'adv-meta' }, h('span', { text: r.d }), h('span', { class: 'kind kind-' + kind, text: r.m }), richText(h('span', { class: 'found-tc' }), r.tc)),
          h('h3', { text: r.h }),
          richText(h('p', { class: 'adv-text' }), r.x),
          refs.length ? refP : null));
      });
    }
    rows(ol, AI_FOUND, 'experiment');
    if (wl) {
      rows(wl, AI_WATCH, 'theory');
      wl.hidden = !AI_WATCH.length;
      [].forEach.call(document.querySelectorAll('.found-sub, .found-sub-intro'), function (e) { e.hidden = !AI_WATCH.length; });
    }
    if (note) {
      clear(note);
      richText(note, AI_FOUND_NOTE.x + ' ');
      var nr = REFS[AI_FOUND_NOTE.ref];
      if (nr) note.appendChild(h('a', { href: refUrl(nr), text: nr.t }));
    }
  };

  const renderAIList = function renderAIList() {
    var st = $('#ai-status'), bar = $('#ai-filter'), ol = $('#ai-list'), more = $('#ai-more');
    if (!ol) return;
    clear(st); clear(bar); clear(ol); clear(more);
    var d = paperState.data, items = aiItems();
    st.appendChild(h('span', { class: 'live-dot' + (d && !paperState.failed ? '' : ' off'), 'aria-hidden': 'true' }));
    st.appendChild(document.createTextNode(paperState.busy ? 'Checking for new items…' :
      d && d.updated ? 'Live · feed updated ' + rel(parseDate(d.updated)) + ' · this page checks again every 10 minutes' :
      paperState.failed ? 'Couldn’t reach the feed. Check the connection and press Refresh.' : 'Loading the feed…'));
    if (d && !Array.isArray(d.ai)) {
      ol.appendChild(h('li', { class: 'empty', text: 'The AI list starts with the next feed update, within three hours.' }));
      renderTicker([]);
      return;
    }
    aiState.newest = items.length ? items[0].date : '';
    var counts = { all: items.length, paper: 0, news: 0, prediction: 0, experiment: 0 };
    items.forEach(function (x) { counts[x.kind_of === 'news' ? 'news' : 'paper']++; if (AI_KIND_LABEL[x.ai_kind]) counts[x.ai_kind]++; });
    if (!counts[aiState.kind] && aiState.kind !== 'all') aiState.kind = 'all';
    [['all', 'All'], ['paper', 'Papers'], ['news', 'News'], ['prediction', 'Predictions'], ['experiment', 'Experiments']].forEach(function (f) {
      if ((f[0] === 'prediction' || f[0] === 'experiment') && !counts[f[0]]) return;
      bar.appendChild(h('button', { class: 'demo-tab', type: 'button', 'aria-pressed': aiState.kind === f[0] ? 'true' : 'false',
        text: f[1] + (counts[f[0]] ? ' ' + counts[f[0]] : ''), onclick: function () { aiState.kind = f[0]; aiState.shown = 12; renderAIList(); } }));
    });
    var rows = items.filter(function (x) {
      return aiState.kind === 'all' || (aiState.kind === 'prediction' || aiState.kind === 'experiment' ? x.ai_kind === aiState.kind : (aiState.kind === 'news') === (x.kind_of === 'news'));
    });
    if (d && !rows.length) ol.appendChild(h('li', { class: 'empty', text: 'Nothing here yet; the next check runs within three hours.' }));
    rows.slice(0, aiState.shown).forEach(function (x) {
      var li = x.kind_of === 'news' ? aiNewsItem(x) : paperItem(x);
      if (AI_KIND_LABEL[x.ai_kind]) { var mt = li.querySelector('.paper-meta'); if (mt) mt.appendChild(h('span', { class: 'ai-kind ai-kind-' + x.ai_kind, text: AI_KIND_LABEL[x.ai_kind] })); }
      if (aiState.seen && x.date > aiState.seen) {
        li.classList.add('is-new');
        var meta = li.querySelector('.paper-meta');
        if (meta) meta.insertBefore(h('span', { class: 'new-badge', text: 'New' }), meta.firstChild);
      }
      ol.appendChild(li);
    });
    if (rows.length > aiState.shown) {
      more.appendChild(h('button', { class: 'btn small', type: 'button', onclick: function () { aiState.shown += 12; renderAIList(); } },
        'Show more (' + (rows.length - aiState.shown) + ' left)'));
    }
    renderTicker(items.slice(0, 6));
  };

  const aiNewsItem = function aiNewsItem(n) {
    var meta = h('p', { class: 'paper-meta' }, h('span', { class: 'src src-news', text: n.source }), h('span', { text: fmtDayISO(n.date) }));
    list(n.topics).forEach(function (t) { meta.appendChild(h('span', { class: 'topic', text: t })); });
    return h('li', null, meta, h('h3', null, h('a', { href: n.url, text: n.title })), n.summary ? h('p', { class: 'paper-intro', text: n.summary }) : null);
  };

  // The newest headlines roll past one at a time; with reduced motion the newest one stays put.
  const renderTicker = function renderTicker(items) {
    var el = $('#ai-ticker');
    if (!el) return;
    clearInterval(aiState.tickTimer);
    aiState.tickTimer = 0;
    clear(el);
    el.hidden = !items.length;
    if (!items.length) return;
    function show() {
      var x = items[aiState.tick % items.length];
      clear(el);
      el.appendChild(h('span', { class: 'ai-tick-label', text: 'Latest' }));
      el.appendChild(h('a', { class: 'ai-tick', href: x.url, text: x.title }));
      el.appendChild(h('span', { class: 'ai-tick-meta', text: x.source + ' · ' + fmtDayISO(x.date) }));
    }
    show();
    if (!motionOK() || items.length < 2) return;
    aiState.tickTimer = setInterval(function () {
      if (view !== 'ai' || document.hidden) return;
      aiState.tick++;
      el.classList.add('fade');
      setTimeout(function () { show(); el.classList.remove('fade'); }, 260);
    }, 5000);
  };

  const renderAIOurs = function renderAIOurs() {
    var el = $('#ai-ours');
    if (!el) return;
    clear(el);
    var d = state.data;
    var ul = h('ul', { class: 'ai-models' });
    modelFamily(d).forEach(function (m) {
      var o = familyOverride(d, m);
      var g = h('span', { class: 'mf-glyph' });
      g.innerHTML = MODEL_GLYPH[m.id] || '';
      ul.appendChild(h('li', null, g, h('div', null,
        h('p', { class: 'ai-model-head' }, h('b', { text: m.name }), h('span', { class: 'mf-status', text: typeof o.status === 'string' && o.status ? o.status : m.status })),
        richText(h('p', { class: 'mf-role' }), m.role))));
    });
    append(el, [
      cardHead('Our AI-designed models', 'An AI agent (Claude) designs each model; every version is scored on materials it never saw and is released only if it beats the current one in at least 4 of 5 folds.'),
      ul,
      h('p', { class: 'ai-links' },
        h('button', { class: 'btn small', type: 'button', onclick: function () { setView('progress'); var c = $('#details-card'); if (c && !c.hidden) c.scrollIntoView(); else window.scrollTo(0, 0); } }, 'Scores and details'),
        h('button', { class: 'btn small', type: 'button', onclick: function () { setView('demos'); selectDemo('storm'); window.scrollTo(0, 0); } }, 'See how Storm works'),
        h('button', { class: 'btn small', type: 'button', onclick: function () { setView('demos'); selectDemo('hurricane'); window.scrollTo(0, 0); } }, 'See how Hurricane works'),
        radInfo() ? h('button', { class: 'btn small', type: 'button', onclick: function () { setView('demos'); selectDemo('radar'); window.scrollTo(0, 0); } }, 'See how Radar works') : null)
    ]);
  };

  const renderAICurated = function renderAICurated() {
    var ol = $('#ai-curated');
    if (!ol) return;
    clear(ol);
    RECENT.filter(function (r) { return r.cards.indexOf('ai') >= 0; })
      .slice().sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : 0; })
      .forEach(function (r) {
        ol.appendChild(h('li', null,
          h('p', { class: 'adv-meta' }, h('span', { text: fmtMonth(r.d) }), h('span', { class: 'kind kind-' + r.k, text: KIND_LABEL[r.k] || r.k })),
          richText(h('h3'), r.h),
          richText(h('p', { class: 'adv-text' }), r.x),
          h('p', { class: 'adv-ref' }, recentLink(r))));
      });
  };

  const aiStart = function aiStart() {
    if (!aiState.timer) aiState.timer = setInterval(function () { if (view === 'ai' && !document.hidden) loadPapers(true); }, AI_POLL_MS);
  };

  const aiStop = function aiStop() {
    clearInterval(aiState.timer);
    aiState.timer = 0;
    clearInterval(aiState.tickTimer);
    aiState.tickTimer = 0;
    if (aiState.newest && aiState.newest > (store.get('aiSeen') || '')) store.set('aiSeen', aiState.newest);
  };

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
        h('div', null, h('h2', { text: 'Automatic research feed' }),
          h('p', { text: 'New papers and news, newest first. Feed tags are automatic; these items are separate from the reviewed studies above.' })),
        h('button', { class: 'btn small', type: 'button', id: 'ai-refresh', onclick: function () { loadPapers(true); loadContent(true); } }, 'Refresh')),
      h('p', { class: 'ai-status', id: 'ai-status' }),
      h('div', { class: 'ai-ticker', id: 'ai-ticker' }),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter by kind', id: 'ai-filter' }),
      h('ol', { class: 'feed-list', id: 'ai-list' }),
      h('div', { class: 'feed-more', id: 'ai-more' }),
      h('p', { class: 'note', text: 'Collected every three hours from arXiv (all categories), Nature, Science, Physical Review and Nature-family journals, and science-news sites. An item is kept when it names an AI or machine-learning method and is about superconducting materials or their theory; quantum-computing and superconducting-electronics papers are left out. “AI prediction” marks new candidate superconductors proposed by a model, and “AI + experiment” candidates that were then made and measured. Tags are assigned automatically, so treat them as a rough guide.' }));
    var ours = h('section', { class: 'card', id: 'ai-ours' });
    var found = h('section', { class: 'card external-research', id: 'ai-found', 'aria-label': 'Reviewed external AI research' });
    append(el, [found, ours, live]);
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
    var el = $('#ai-found'), data = globalThis.SuperconExternalResearch;
    if (!el) return;
    // Feed refreshes must not replace an open reviewed card or reset its filters.
    if (aiState.external.source === data && el.firstChild) return;
    stopExternalResearch(true);
    clear(el);
    aiState.external.source = data;
    var entries = externalResearchRows(data, 'all', '');
    append(el, [
      h('div', { class: 'external-research-heading' },
        h('div', null, h('p', { class: 'external-research-eyebrow', text: 'Evidence from other groups' }),
          h('h2', { text: 'Superconductors found with AI by other groups' }),
          h('p', { text: 'Explore what each study did, what it found, and what remains unverified. Predictions, experiments and research programmes keep their own evidence labels.' })),
        h('div', { class: 'external-research-total' }, h('b', { text: entries.length }), h('span', { text: 'reviewed entries' }))),
      h('p', { class: 'external-research-update', text: externalResearchSchedule(data) })
    ]);
    if (!entries.length) {
      el.appendChild(h('p', { class: 'empty', text: 'The reviewed research registry is unavailable in this app snapshot.' }));
      return;
    }
    var search = h('input', { id: 'external-research-search', type: 'search', placeholder: 'Material, method, author, year or DOI', value: aiState.external.query,
      oninput: function () { aiState.external.query = search.value; aiState.external.page = 0; renderExternalResearchList(); } });
    var select = h('select', { id: 'external-research-category', onchange: function () {
      aiState.external.category = select.value; aiState.external.page = 0; renderExternalResearchList();
    } });
    var categories = ['all'];
    entries.forEach(function (entry) { if (entry.category && categories.indexOf(entry.category) < 0) categories.push(entry.category); });
    categories.forEach(function (category) { select.appendChild(h('option', { value: category, text: externalResearchCategory(category) })); });
    if (categories.indexOf(aiState.external.category) < 0) aiState.external.category = 'all';
    select.value = aiState.external.category;
    append(el, [
      h('div', { class: 'external-research-tools' },
        h('label', { for: 'external-research-search' }, h('span', { text: 'Search studies' }), search),
        h('label', { for: 'external-research-category' }, h('span', { text: 'Evidence category' }), select)),
      h('p', { id: 'external-research-count', class: 'external-research-count', role: 'status', 'aria-live': 'polite' }),
      h('ol', { id: 'external-research-list', class: 'external-research-list' }),
      h('nav', { id: 'external-research-pages', class: 'external-research-pages', 'aria-label': 'Reviewed research pages' }),
      h('p', { class: 'note', text: 'The route animation explains the paper’s reported work; it does not simulate an experiment or turn a prediction into a measurement. The source and its limitations remain visible for every study.' })
    ]);
    renderExternalResearchList();
  };

  const externalResearchCategory = function externalResearchCategory(value) {
    return ({ all: 'All evidence', '计算预测': 'Computational prediction', '回溯验证': 'Retrospective validation',
      '实验研究': 'Experimental study', '数据与工具': 'Data & tools', '研究计划': 'Research programme' })[value] || value || 'Unspecified';
  };

  const externalResearchRows = function externalResearchRows(data, category, query) {
    var q = String(query || '').trim().toLocaleLowerCase();
    return list(data && data.entries).filter(function (entry) {
      if (!entry || !entry.id || !(entry.heading || entry.title)) return false;
      if (category && category !== 'all' && entry.category !== category) return false;
      return !q || [entry.heading, entry.title, entry.short, entry.year, entry.stage, entry.headline, entry.team,
        entry.publication, entry.result, entry.boundary, entry.doi, externalResearchCategory(entry.category)].join(' ').toLocaleLowerCase().indexOf(q) >= 0;
    });
  };

  const externalResearchSchedule = function externalResearchSchedule(data) {
    if (!data) return 'No reviewed snapshot loaded.';
    var date = typeof data.reviewed_on === 'string' ? data.reviewed_on : data.updated;
    var text = date ? 'Source review: ' + date + '.' : 'Source review date not supplied.';
    var schedule = data.schedule;
    if (schedule && schedule.frequency === 'daily') {
      text += ' ' + (schedule.status === 'active' || schedule.status === 'active_schedule' ? 'Review schedule: daily' : 'Planned review: daily') +
        (schedule.time ? ' at ' + schedule.time : '') + (schedule.timezone ? ' (' + schedule.timezone + ')' : '') +
        '. A schedule does not mean a new review has completed.';
    }
    return text;
  };

  const externalResearchUrl = function externalResearchUrl(value) {
    if (typeof value !== 'string') return '';
    try { var url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; }
    catch (_) { return ''; }
  };

  const externalResearchReferences = function externalResearchReferences(entry) {
    var raw = [{ title: entry.title || entry.publication || 'Primary paper', url: entry.url,
      doi: entry.doi }].concat(list(entry.primary_refs), list(entry.extra));
    var seen = {}, refs = [];
    raw.forEach(function (ref) {
      if (Array.isArray(ref)) ref = { title: ref[0], url: ref[1] };
      if (typeof ref === 'string') ref = { title: 'Source', url: ref };
      if (!ref || typeof ref !== 'object') return;
      var url = externalResearchUrl(ref.url);
      if (!url && typeof ref.doi === 'string' && /^10\.\d{4,9}\/\S+$/.test(ref.doi)) url = externalResearchUrl('https://doi.org/' + ref.doi);
      if (!url || seen[url]) return;
      seen[url] = true;
      refs.push({ title: ref.title || ref.label || ref.name || 'Primary source', url: url });
    });
    return refs;
  };

  const renderExternalResearchList = function renderExternalResearchList() {
    var el = $('#external-research-list'), pages = $('#external-research-pages'), count = $('#external-research-count');
    if (!el) return;
    stopExternalResearch(true);
    clear(el); clear(pages);
    var st = aiState.external, rows = externalResearchRows(st.source, st.category, st.query);
    var totalPages = Math.max(1, Math.ceil(rows.length / st.pageSize));
    st.page = Math.max(0, Math.min(st.page, totalPages - 1));
    var start = st.page * st.pageSize;
    count.textContent = rows.length ? 'Showing ' + (start + 1) + '–' + Math.min(start + st.pageSize, rows.length) + ' of ' + rows.length + ' studies' : 'No studies match this search.';
    el.setAttribute('start', String(start + 1));
    rows.slice(start, start + st.pageSize).forEach(function (entry) { el.appendChild(buildExternalResearchCard(entry)); });
    if (!rows.length) el.appendChild(h('li', { class: 'empty', text: 'Try another material, method or evidence category.' }));
    if (totalPages > 1) {
      function turn(page) {
        st.page = page; renderExternalResearchList();
        count.setAttribute('tabindex', '-1'); count.focus();
        count.scrollIntoView({ block: 'nearest', behavior: 'auto' });
      }
      append(pages, [
        h('button', { class: 'btn small', type: 'button', disabled: st.page === 0, onclick: function () { turn(st.page - 1); } }, 'Previous'),
        h('span', { text: 'Page ' + (st.page + 1) + ' of ' + totalPages }),
        h('button', { class: 'btn small', type: 'button', disabled: st.page >= totalPages - 1, onclick: function () { turn(st.page + 1); } }, 'Next')
      ]);
    }
  };

  const buildExternalResearchCard = function buildExternalResearchCard(entry) {
    var refs = externalResearchReferences(entry);
    var detail = h('details', { class: 'external-research-detail' });
    var route = buildExternalResearchRoute(entry);
    detail.addEventListener('toggle', function () { if (!detail.open) route.stop(); });
    var facts = h('dl', { class: 'external-research-facts' });
    [['Team', entry.team], ['Publication', entry.publication], ['Source reviewed', entry.reviewed_on], ['Version checked', entry.verified_version],
      ['Evidence', entry.evidence_type], ['Pressure / conditions', entry.pressure], ['Tc criterion', entry.tc_criterion]].forEach(function (fact) {
      if (typeof fact[1] === 'string' && fact[1]) append(facts, [h('dt', { text: fact[0] }), h('dd', { text: fact[1] })]);
    });
    var sources = h('ul', { class: 'external-research-sources' });
    refs.forEach(function (ref) { sources.appendChild(h('li', null, h('a', { href: ref.url, target: '_blank', rel: 'noopener noreferrer', text: ref.title }))); });
    append(detail, [h('summary', null, h('span', { text: 'Explore the study' }), h('span', { class: 'external-research-summary-hint', text: 'Method · evidence · sources' })),
      h('div', { class: 'external-research-detail-body' },
        h('h4', { text: 'What the study found' }), h('p', { text: entry.result || 'Result not supplied in this snapshot.' }),
        route.element,
        h('div', { class: 'external-research-boundary' }, h('h4', { text: 'Evidence limits' }),
          h('p', { text: entry.boundary || 'Evidence limitations not supplied in this snapshot.' })),
        entry.reference_point ? h('div', { class: 'external-research-insight' }, h('h4', { text: 'What we can learn' }), h('p', { text: entry.reference_point })) : null,
        facts, h('h4', { text: 'Read the primary sources' }), sources)
    ]);
    return h('li', { class: 'external-research-card', 'data-study-id': entry.id },
      h('div', { class: 'external-research-card-meta' }, h('span', { class: 'external-research-index', text: '#' + entry.id }),
        h('span', { text: entry.year || 'Date not supplied' }),
        h('span', { class: 'external-research-category', text: externalResearchCategory(entry.category) })),
      h('h3', { text: entry.heading || entry.title }),
      h('p', { class: 'external-research-headline', text: entry.headline || entry.short || '' }),
      h('p', { class: 'external-research-stage', text: 'Reported stage · ' + (entry.stage || 'Not specified') }),
      refs.length ? h('a', { class: 'external-research-paper-link', href: refs[0].url, target: '_blank', rel: 'noopener noreferrer', text: 'Primary source ↗' }) : null,
      detail);
  };

  const stopExternalResearch = function stopExternalResearch(dispose) {
    if (!aiState || !aiState.external) return;
    aiState.external.controllers.forEach(function (controller) { controller.stop(); if (dispose) controller.dispose(); });
    if (dispose) aiState.external.controllers = [];
  };

  const buildExternalResearchRoute = function buildExternalResearchRoute(entry) {
    var steps = list(entry.progress_steps).filter(function (step) { return step && typeof step.label === 'string'; });
    var section = h('section', { class: 'external-research-route', 'aria-label': 'Research route for ' + (entry.short || entry.heading || entry.title) });
    var timer = 0, index = 0, playing = false, observer = null, buttons = [];
    var labels = { completed: 'Reported', current: 'Current evidence', not_reported: 'Not reported' };
    var readout = h('div', { class: 'external-research-route-readout', 'aria-live': 'polite', 'aria-atomic': 'true' });
    var play = h('button', { class: 'btn small', type: 'button' }, 'Play explanation');
    var replay = h('button', { class: 'btn small', type: 'button' }, 'Replay');
    var status = h('span', { class: 'external-research-route-status' });
    function paint() {
      buttons.forEach(function (button, i) { button.setAttribute('aria-pressed', i === index ? 'true' : 'false'); });
      clear(readout);
      if (steps[index]) append(readout, [h('b', { text: (index + 1) + '. ' + steps[index].label }), h('p', { text: steps[index].detail || 'No further detail supplied.' })]);
      play.textContent = playing ? 'Pause' : index === steps.length - 1 ? 'Play again' : index ? 'Continue' : 'Play explanation';
      var reduced = !motionOK();
      play.hidden = reduced || steps.length < 2;
      replay.hidden = reduced || steps.length < 2;
      status.textContent = reduced ? 'Reduced motion · select any step' : playing ? 'Playing explanation' : 'Select a step or play the explanation';
    }
    function stop() { clearTimeout(timer); timer = 0; playing = false; paint(); }
    function advance() {
      if (!playing || view !== 'ai' || document.hidden || !motionOK() || !section.isConnected) { stop(); return; }
      if (index >= steps.length - 1) { stop(); return; }
      index++; paint();
      if (index === steps.length - 1) { playing = false; paint(); return; }
      timer = setTimeout(advance, 3200);
    }
    function start(reset) {
      if (!motionOK() || steps.length < 2 || view !== 'ai' || document.hidden) return;
      stopExternalResearch();
      if (reset || index === steps.length - 1) index = 0;
      playing = true; paint(); timer = setTimeout(advance, 3200);
    }
    var controller = { element: section, stop: stop, dispose: function () { clearTimeout(timer); if (observer) observer.disconnect(); } };
    if (!steps.length) {
      section.appendChild(h('p', { text: 'A step-by-step route is not supplied for this study.' }));
      return controller;
    }
    var rail = h('ol', { class: 'external-research-route-steps' });
    steps.forEach(function (step, i) {
      var known = Object.prototype.hasOwnProperty.call(labels, step.status) ? step.status : 'not_reported';
      var button = h('button', { type: 'button', class: 'external-research-step', 'aria-pressed': i === 0 ? 'true' : 'false', onclick: function () { stop(); index = i; paint(); } },
        h('span', { class: 'external-research-step-number', text: String(i + 1) }),
        h('b', { text: step.label }), h('small', { class: 'external-research-step-evidence evidence-' + known, text: labels[known] }));
      buttons.push(button); rail.appendChild(h('li', null, button));
    });
    play.addEventListener('click', function () { if (playing) stop(); else start(false); });
    replay.addEventListener('click', function () { start(true); });
    append(section, [h('h4', { text: 'Follow the research route' }), rail, readout,
      h('div', { class: 'external-research-route-controls' }, play, replay, status)]);
    aiState.external.controllers.push(controller);
    if (typeof IntersectionObserver === 'function') {
      observer = new IntersectionObserver(function (items) { items.forEach(function (item) { if (!item.isIntersecting && playing) stop(); }); });
      observer.observe(section);
    }
    paint();
    return controller;
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
      cardHead('Our AI-designed models', 'Our models and their published evaluation results. Research challengers remain separate until validation supports a release.'),
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
    stopExternalResearch();
    clearInterval(aiState.timer);
    aiState.timer = 0;
    clearInterval(aiState.tickTimer);
    aiState.tickTimer = 0;
    if (aiState.newest && aiState.newest > (store.get('aiSeen') || '')) store.set('aiSeen', aiState.newest);
  };

'use strict';
// ai-view: shared lexical function definitions; no startup side effects.


  const aiItems = function aiItems() {
    var d = paperState.data, seen = Object.create(null);
    return d ? list(d.ai).filter(function (x) { return x && x.title && isHttps(x.url); })
      .sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; }).filter(function (x) {
        var keys = feedIdentityKeys(x), duplicate = keys.some(function (key) { return seen[key]; });
        keys.forEach(function (key) { seen[key] = true; });
        return !duplicate;
      }) : [];
  };

  const buildAI = function buildAI() {
    var el = $('#papers-ai-feed');
    if (!el) return;
    clear(el);
    var live = h('section', { class: 'card ai-live' },
      h('div', { class: 'card-head' },
        h('div', null, h('h3', { text: 'AI papers and news' }),
          h('p', { text: 'New papers and news, newest first. Tags are assigned automatically; consult the original source for its evidence and limitations.' })),
        h('button', { class: 'btn small', type: 'button', id: 'ai-refresh', onclick: function () { loadPapers(true); loadContent(true); } }, 'Refresh')),
      h('p', { class: 'ai-status', id: 'ai-status' }),
      h('div', { class: 'ai-ticker', id: 'ai-ticker' }),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter by kind', id: 'ai-filter' }),
      h('ol', { class: 'feed-list', id: 'ai-list' }),
      h('div', { class: 'feed-more', id: 'ai-more' }),
      h('p', { class: 'note', text: 'Collected every three hours from arXiv (all categories), Nature, Science, Physical Review and Nature-family journals, and science-news sites. An item is kept when it names an AI or machine-learning method and is about superconducting materials or their theory; quantum-computing and superconducting-electronics papers are left out. “AI prediction” marks new candidate superconductors proposed by a model, and “AI + experiment” candidates that were then made and measured. Tags are assigned automatically, so treat them as a rough guide.' }));
    append(el, [live]);
    aiState.built = true;
    renderAI();
  };

  const renderAI = function renderAI() {
    if (!aiState.built) return;
    renderAIList();
  };

  const renderAIList = function renderAIList() {
    var st = $('#ai-status'), bar = $('#ai-filter'), ol = $('#ai-list'), more = $('#ai-more');
    if (!ol) return;
    clear(st); clear(bar); clear(ol); clear(more);
    miniPrune();
    var d = paperState.data, items = aiItems();
    st.appendChild(h('span', { class: 'live-dot' + (d && !paperState.failed ? '' : ' off'), 'aria-hidden': 'true' }));
    st.appendChild(document.createTextNode(paperState.busy ? 'Checking for new items…' :
      paperState.failed ? (d && d.updated ? 'Couldn’t refresh. Showing the feed updated ' + rel(parseDate(d.updated)) + '.' : 'Couldn’t reach the feed. Check the connection and press Refresh.') :
      d && d.updated ? 'Feed updated ' + rel(parseDate(d.updated)) + ' · checks every 10 minutes while News & Papers is open' :
      'Loading the feed…'));
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
      var li = aiAnimatedItem(x);
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
    miniKick();
  };

  const aiArticleArt = function aiArticleArt(item) {
    // Use this paper's method or material subject, rather than assigning every AI paper a crystal network.
    var art = newsArt(item);
    return art === 'news-general' || art === 'news-research' ? 'news-features' : art;
  };

  const aiWorkflowInfo = function aiWorkflowInfo(item) {
    var kind = item.ai_kind;
    var flows = {
      prediction: [['Inputs and model', 'Material information is used to estimate properties or rank candidates.'], ['Predicted candidates', 'A model score is a prediction, not a measured superconducting transition.'], ['Independent validation', 'Calculations or experiments would test the prediction; this diagram does not say those tests occurred.']],
      generation: [['Training structures', 'A generative model learns a representation of materials.'], ['Generated structures', 'Proposed structures still require physical and synthesis checks.'], ['Independent validation', 'A generated structure is not an experimentally realized phase.']],
      experiment: [['Inputs and model', 'The feed labels this item as linking AI with experiments; check the original source.'], ['Reported sample tests', 'Read which samples were made and which superconductivity criteria were measured.'], ['Phase and condition checks', 'A signal in a sample does not by itself identify the predicted phase; retain pressure, composition and measurement limits.']],
      data: [['Source records', 'Material records require source and sample identities.'], ['Model-assisted processing', 'Extracted or predicted values can contain errors and duplicate samples.'], ['Source audit', 'Check original conditions, units and permissions before using records as training targets.']],
      review: [['Published studies', 'A review compares existing work.'], ['Compare methods', 'Different datasets and validation splits are not automatically comparable.'], ['Assess evidence', 'A review is not a new experimental discovery.']]
    };
    var known = Object.prototype.hasOwnProperty.call(flows, kind);
    return { kind: known ? kind : 'analysis',
      steps: known ? flows[kind] : [['Research inputs', 'The source supplies material data, structures or a physical model.'], ['AI-assisted analysis', 'An AI method helps analyze, predict or search. The original source defines its actual role.'], ['Interpret the evidence', 'Check the reported validation and limitations. No experimental result is implied by this schematic.']] };
  };

  const aiWorkflow = function aiWorkflow(item) {
    var info = aiWorkflowInfo(item), position = 0, timer = 0, buttons = [];
    var box = h('details', { class: 'ai-workflow', 'data-workflow-kind': info.kind });
    var group = h('div', { class: 'ai-workflow-steps', role: 'group', 'aria-label': 'Explore the illustrative workflow' });
    var detail = h('p', { class: 'ai-workflow-detail', 'aria-live': 'polite' });
    var status = h('p', { class: 'ai-workflow-status' });
    function stop() { clearInterval(timer); timer = 0; }
    function show() {
      buttons.forEach(function (button, i) { button.setAttribute('aria-pressed', i === position ? 'true' : 'false'); });
      detail.textContent = info.steps[position][1];
      play.textContent = timer ? 'Pause explanation' : 'Play explanation';
      play.disabled = !motionOK();
      status.textContent = !motionOK() ? 'Reduced motion: choose a step manually.' : timer ? 'Playing an illustrative explanation.' : 'Choose a step or play the explanation.';
    }
    var play = h('button', { class: 'btn small', type: 'button', onclick: function () {
      if (timer || !motionOK()) { stop(); show(); return; }
      timer = setInterval(function () {
        if (!box.isConnected || !box.open || view !== 'papers' || document.hidden || !motionOK()) { stop(); show(); return; }
        position = (position + 1) % info.steps.length; show();
      }, 2500);
      show();
    } });
    info.steps.forEach(function (step, i) {
      var button = h('button', { type: 'button', onclick: function () { stop(); position = i; show(); } }, h('span', { text: String(i + 1) }), step[0]);
      buttons.push(button); group.appendChild(button);
    });
    box.addEventListener('toggle', function () { if (!box.open) stop(); show(); });
    append(box, [h('summary', { text: 'Explore the AI workflow' }), h('p', { class: 'note', text: 'Illustrative schematic, not a record of completed research steps. Feed labels are automatic; the linked source determines what was actually predicted or measured.' }), group, detail, play, status]);
    show();
    return box;
  };

  const aiAnimatedItem = function aiAnimatedItem(item) {
    var original = item.kind_of === 'news' ? aiNewsItem(item) : paperItem(item, true);
    var body = h('div', { class: 'news-body' });
    while (original.firstChild) body.appendChild(original.firstChild);
    body.appendChild(newsArticleFigure(item));
    body.appendChild(aiWorkflow(item));
    return h('li', { class: 'news-item ai-feed-item article-item', 'data-feed-key': feedIdentityKeys(item)[0] || '' }, body);
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
    if (!motionOK() || items.length < 2 || view !== 'papers') return;
    aiState.tickTimer = setInterval(function () {
      if (view !== 'papers' || document.hidden) return;
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

  const aiStart = function aiStart() {
    if (!aiState.timer) aiState.timer = setInterval(function () { if (view === 'papers' && !document.hidden) loadPapers(true); }, AI_POLL_MS);
  };

  const aiStop = function aiStop() {
    clearInterval(aiState.timer);
    aiState.timer = 0;
    clearInterval(aiState.tickTimer);
    aiState.tickTimer = 0;
    if (aiState.newest && aiState.newest > (store.get('aiSeen') || '')) store.set('aiSeen', aiState.newest);
  };

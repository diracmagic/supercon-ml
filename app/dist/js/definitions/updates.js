'use strict';
// updates: shared lexical function definitions; no startup side effects.

  const isDesktop = function isDesktop() { return !!(window.__TAURI__ || window.__TAURI_INTERNALS__); };

  const verParts = function verParts(s) { var m = /(\d+)\.(\d+)\.(\d+)/.exec(String(s || '')); return m ? [+m[1], +m[2], +m[3]] : null; };

  const verNewer = function verNewer(a, b) {
    a = verParts(a); b = verParts(b);
    if (!a || !b) return false;
    for (var i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i];
    return false;
  };

  const installerName = function installerName() {
    var ua = navigator.userAgent || '', pf = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '';
    if (/win/i.test(pf) || /Windows/.test(ua)) return 'SuperconProgress-windows-x64-setup.exe';
    if (/mac/i.test(pf) || /Mac OS X|Macintosh/.test(ua)) return 'SuperconProgress-macos-universal.dmg';
    return '';
  };

  // The bold titles of the "Version X adds:" bullets in the release notes.
  const releaseHighlights = function releaseHighlights(body, v) {
    var lines = String(body || '').split(/\r?\n/), out = [], on = false;
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i].trim();
      if (!on) { if (ln.indexOf('Version ' + v) === 0) on = true; continue; }
      if (!ln) { if (out.length) break; continue; }
      if (ln.charAt(0) !== '-') { if (out.length) break; continue; }
      var m = /\*\*(.+?)\*\*/.exec(ln);
      if (m) out.push(m[1].replace(/<[^>]+>/g, ''));
    }
    return out.slice(0, 4);
  };

  const updRead = function updRead(key) { try { return JSON.parse(store.get(key) || 'null'); } catch (e) { return null; } };

  const updAvailable = function updAvailable() {
    var info = UPD.info;
    return !!(isDesktop() && info && info.url && verNewer(info.v, APP_VERSION));
  };

  const checkUpdate = function checkUpdate(manual) {
    if (!isDesktop() || UPD.busy) return;
    var cached = updRead('update');
    if (!manual && cached && cached.t && Date.now() - cached.t < UPD_EVERY) { UPD.info = cached; renderUpdate(); return; }
    UPD.busy = true;
    if (manual) { store.set('updateLater', ''); UPD.dismissed = false; flashNote('Checking for updates…', 0); }
    getJSON(API + '/releases/latest', { headers: { Accept: 'application/vnd.github+json' }, timeout: 12000 })
      .then(function (rel) {
        var v = (verParts(rel && rel.tag_name) || []).join('.'), want = installerName(), url = '';
        (rel && rel.assets || []).forEach(function (a) { if (a && a.name === want && /^https:\/\//.test(a.browser_download_url || '')) url = a.browser_download_url; });
        var page = rel && /^https:\/\//.test(rel.html_url || '') ? rel.html_url : REPO_URL + '/releases/latest';
        // An unknown computer gets the release page; a known one waits until its installer is uploaded.
        UPD.info = { t: Date.now(), v: v, page: page, url: want ? url : page, news: releaseHighlights(rel && rel.body, v) };
        store.set('update', JSON.stringify(UPD.info));
        if (manual) flashNote(updAvailable() ? '' : 'You have the latest version.', 6000);
      }, function () {
        if (manual) flashNote('Couldn’t reach GitHub to check for updates. Try again later.', 8000);
      })
      .then(function () { UPD.busy = false; renderUpdate(); });
  };

  const flashNote = function flashNote(msg, ms) {
    UPD.note = msg;
    clearTimeout(UPD.noteTimer);
    renderUpdateFoot();
    if (msg && ms) UPD.noteTimer = setTimeout(function () { UPD.note = ''; renderUpdateFoot(); }, ms);
  };

  const renderUpdate = function renderUpdate() {
    var el = $('#update');
    if (!el) return;
    clear(el);
    var info = UPD.info, kind = '';
    if (UPD.web && !UPD.dismissed) kind = 'web';
    else if (updAvailable() && !UPD.dismissed) {
      var later = updRead('updateLater');
      if (!(later && later.v === info.v && Date.now() < later.until)) kind = 'desktop';
    }
    el.hidden = !kind;
    if (kind === 'web') {
      append(el, [glyph('refresh', 'upd-glyph'), h('div', { class: 'upd-body' },
        h('p', { class: 'upd-title', text: UPD.web === 'new' ? 'A new version of Supercon Progress is ready.' : 'Supercon Progress ' + UPD.web + ' is ready.' }),
        h('div', { class: 'upd-actions' },
          h('button', { class: 'btn primary', type: 'button', onclick: function () { window.location.reload(); } }, 'Reload now'),
          h('button', { class: 'btn', type: 'button', onclick: function () { UPD.dismissed = true; renderUpdate(); } }, 'Later')))]);
    } else if (kind === 'desktop') {
      var mac = /\.dmg$/.test(info.url), how = mac
        ? 'When the download finishes, quit Supercon Progress, open the .dmg and drag the app into Applications to replace this version.'
        : /\.exe$/.test(info.url) ? 'When the download finishes, quit Supercon Progress and run the installer. It replaces this version and keeps your settings.'
          : 'Download the installer for your computer from the release page.';
      append(el, [glyph('download', 'upd-glyph'), h('div', { class: 'upd-body' },
        h('p', { class: 'upd-title', text: 'Supercon Progress ' + info.v + ' is available. You have ' + APP_VERSION + '.' }),
        info.news && info.news.length ? h('p', { class: 'upd-news', text: 'New: ' + info.news.join(' · ') }) : null,
        h('div', { class: 'upd-actions' },
          h('button', { class: 'btn primary', type: 'button', onclick: function () { openExternal(info.url); UPD.downloaded = true; renderUpdate(); } }, glyph('download', 'btn-glyph'), 'Download ' + info.v),
          h('button', { class: 'btn', type: 'button', onclick: function () { openExternal(info.page); } }, 'What’s new'),
          h('button', { class: 'btn', type: 'button', onclick: function () { store.set('updateLater', JSON.stringify({ v: info.v, until: Date.now() + UPD_LATER })); renderUpdate(); } }, 'Later')),
        h('p', { class: 'upd-hint', text: UPD.downloaded ? 'Downloading in your browser. ' + how : how }))]);
    }
    renderUpdateFoot();
  };

  const renderUpdateFoot = function renderUpdateFoot() {
    var el = $('#upd-foot');
    if (!el) return;
    clear(el);
    if (!isDesktop()) return;
    el.appendChild(document.createTextNode(' · '));
    if (UPD.note) { el.appendChild(h('span', { class: 'upd-note', role: 'status', text: UPD.note })); return; }
    if (updAvailable()) {
      el.appendChild(h('button', { class: 'linklike', type: 'button', onclick: function () {
        store.set('updateLater', ''); UPD.dismissed = false; renderUpdate(); window.scrollTo(0, 0);
      } }, 'Update to ' + UPD.info.v));
      return;
    }
    el.appendChild(h('button', { class: 'linklike', type: 'button', onclick: function () { checkUpdate(true); } }, 'Check for updates'));
  };


  const render = function render() {
    renderChrome();
    var d = state.data;
    $('#main').hidden = !d || view !== 'progress';
    $('#candidates').hidden = !d || view !== 'candidates';
    if (!d) return;
    renderPipeline(d);
    renderCandidates(d);
    renderKpis(d);
    renderModels(d);
    renderStages(d);
    renderResults(d);
    renderActivity(d);
    renderGitHub();
    renderDetails(d);
    if (demo.built && view === 'demos') { syncControls(); kick(); }
    if (view === 'authors') renderAuthors();
    if (aiState.built) renderAIOurs();
  };


  const applyTheme = function applyTheme() {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
  };

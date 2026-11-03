'use strict';
// startup: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconStartup = function initializeSuperconStartup() {


  $('#btn-refresh').addEventListener('click', function () { refreshAll(true); });

  $('#btn-theme').addEventListener('click', function () {
    theme = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system';
    store.set('theme', theme);
    applyTheme();
    renderChrome();
    kick();
    miniKick();
    xtDirty();
    xtKick();
  });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && state.checkedAt && Date.now() - state.checkedAt.getTime() > 60 * 1000) refreshAll();
  });


  $('#view-progress').addEventListener('click', function () { setView('progress'); });

  $('#view-candidates').addEventListener('click', function () { setView('candidates'); });

  $('#view-demos').addEventListener('click', function () { setView('demos'); });

  $('#view-learn').addEventListener('click', function () { setView('learn'); });

  $('#view-papers').addEventListener('click', function () { setView('papers'); });

  $('#view-authors').addEventListener('click', function () { setView('authors'); });

  document.addEventListener('visibilitychange', function () { if (!document.hidden) kick(); });


  applyTheme();

  render();

  renderPhoneCard();

  setView(view);

  loadContent(false);

  loadBundled().then(function () { render(); return refreshAll(); });

  setInterval(refreshAll, REFRESH_MS);

  setInterval(function () { if (!state.busy) renderChrome(); }, 60 * 1000);

};

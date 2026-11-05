'use strict';
// core: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconCore = function initializeSuperconCore() {


  APP_VERSION = '0.3.24';

  REPO = 'diracmagic/supercon-ml';

  BRANCH = 'main';

  REPO_URL = 'https://github.com/' + REPO;

  DATA_URL = 'https://raw.githubusercontent.com/' + REPO + '/' + BRANCH + '/progress/progress.json';

  API = 'https://api.github.com/repos/' + REPO;

  REFRESH_MS = 3 * 60 * 1000;

  LOG_LIMIT = 6;


  STR = {
    en: {
      appName: 'Supercon Progress',
      refresh: 'Refresh',
      checked: 'Refresh (last checked {t})',
      themeSystem: 'Theme: follow system',
      themeLight: 'Theme: light',
      themeDark: 'Theme: dark',
      updated: 'Progress updated {t}',
      loading: 'Loading…',
      offline: 'Can’t reach GitHub right now, so this shows the most recent copy available (updated {t}).',
      notPublished: 'Live data isn’t published on GitHub yet, so this shows the copy bundled with the app (updated {t}).',
      pipelineAria: 'Pipeline: {d} of {n} stages done. {s}',
      noData: 'No progress data could be loaded yet. Check your internet connection and refresh.',
      rateLimited: 'GitHub’s hourly limit for anonymous requests was reached. Build status comes back at {t}.',
      repoMissing: 'The repository isn’t public yet, so live build status isn’t available.',
      ghError: 'Couldn’t load build status from GitHub.',
      progress: 'Overall progress',
      stagesDone: '{d} of {n} stages done',
      now: 'Now: {s}',
      allDone: 'All stages done',
      latestBuild: 'Latest build',
      noRuns: 'No builds yet',
      bestTc: 'Best Tc error so far',
      noModel: 'No trained model yet',
      vsBaseline: 'Best published, structure only: {v}',
      target: 'Target for v0.1',
      daysLeft: '{n} days left',
      dayLeft: '1 day left',
      dueToday: 'Due today',
      overdue: '{n} days past the target',
      stages: 'Stages',
      stagesSub: 'From plan to public release',
      targetOn: 'Target {d}',
      st_done: 'Done',
      st_active: 'In progress',
      st_blocked: 'Blocked',
      st_pending: 'Not started',
      activity: 'Activity',
      showAll: 'Show all ({n})',
      showLess: 'Show less',
      onGithub: 'On GitHub',
      openRepo: 'Open repository',
      runs: 'Workflow runs',
      commits: 'Commits',
      noCommits: 'No commits yet',
      run_running: 'Running',
      run_queued: 'Queued',
      run_success: 'Succeeded',
      run_failure: 'Failed',
      run_cancelled: 'Cancelled',
      run_attention: 'Needs attention',
      results: 'Results',
      resultsSub: 'Mean absolute error (MAE) on held-out materials. Lower is better.',
      chartTitle: 'Validation Tc error by training run (K)',
      chartEmpty: 'Results appear here after the first training run.',
      showTable: 'Show as table',
      showChart: 'Show as chart',
      colModel: 'Model',
      colTarget: 'Target',
      colMae: 'MAE',
      colNotes: 'Notes',
      colRun: 'Run',
      colDate: 'Date',
      thisProject: 'This project',
      refLabel: '{m}, published: {v}',
      baselineNote: 'Published numbers come from each paper’s own data split, so they are a reference point, not a head-to-head comparison.',
      footData: 'Data: progress/progress.json'
    }
  };


  G = {
    done: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" class="f-good"/><path d="M7.5 12.4l3 3 6-6.4" class="s-white" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    active: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" class="f-surface s-accent" stroke-width="2"/><circle cx="12" cy="12" r="4" class="f-accent pulse"/></svg>',
    blocked: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" class="f-warning"/><path d="M12 7.2v6" stroke="#0b0b0b" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="16.6" r="1.3" fill="#0b0b0b"/></svg>',
    pending: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" class="f-surface s-axis" stroke-width="2"/></svg>',
    failure: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" class="f-critical"/><path d="M8.6 8.6l6.8 6.8M15.4 8.6l-6.8 6.8" class="s-white" stroke-width="2.2" stroke-linecap="round"/></svg>',
    cancelled: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" class="f-surface s-muted" stroke-width="2"/><path d="M8 12h8" class="s-muted" stroke-width="2.2" stroke-linecap="round"/></svg>',
    running: '<svg viewBox="0 0 24 24" aria-hidden="true" class="spin"><circle cx="12" cy="12" r="9" fill="none" class="s-track" stroke-width="2.6"/><path d="M12 3a9 9 0 0 1 9 9" fill="none" class="s-accent" stroke-width="2.6" stroke-linecap="round"/></svg>',
    queued: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" class="f-surface s-accent" stroke-width="2"/><path d="M12 7.5V12l3 2" class="s-accent" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    commit: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3.5"/><path d="M3 12h5.5M15.5 12H21"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5a8 8 0 1 1-2.6-6.1"/><path d="M20 4v5h-5"/></svg>',
    system: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
    light: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6L6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/></svg>',
    dark: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.4"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M8 5.5v13l10.5-6.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><rect x="7" y="5.5" width="3.5" height="13" rx="1"/><rect x="13.5" y="5.5" width="3.5" height="13" rx="1"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6l-6 6 6 6"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 6l6 6-6 6"/></svg>',
    mail: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5.5" width="17" height="13" rx="2.2"/><path d="M4.5 7.5l7.5 5.6 7.5-5.6"/></svg>',
    download: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11"/><path d="M7.5 10.5L12 15l4.5-4.5"/><path d="M5 19.5h14"/></svg>',
    chart: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5h16"/><path d="M5 15l4-4 3 3 7-8"/></svg>'
  };

  RUN_GLYPH = { running: 'running', queued: 'queued', success: 'done', failure: 'failure', cancelled: 'cancelled', attention: 'blocked' };

  STAGE_STATUSES = ['done', 'active', 'blocked', 'pending'];


  store = {
    get: function (k) { try { return window.localStorage.getItem('supercon.' + k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem('supercon.' + k, v); } catch (e) { /* storage unavailable */ } }
  };


  lang = 'en';

  theme = (function () {
    var s = store.get('theme');
    return s === 'light' || s === 'dark' ? s : 'system';
  })();


  state = {
    data: null, live: null, loaded: false, shownPct: null, pipeIntro: false,
    runs: null, commits: null, gh: null,
    checkedAt: null, busy: false,
    showAllLog: false, view: 'chart'
  };

  SVGNS = 'http://www.w3.org/2000/svg';

  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href');
    if (/^https?:/i.test(href)) { e.preventDefault(); openExternal(href); }
    else if (/^mailto:/i.test(href) && (window.__TAURI__ || window.__TAURI_INTERNALS__)) { e.preventDefault(); openExternal(href); }
  });

};

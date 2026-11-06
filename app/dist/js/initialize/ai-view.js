'use strict';
// ai-view: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconAiView = function initializeSuperconAiView() {


  /* ---------- AI × superconductors: a live list of AI and machine-learning papers and news, and our models ----------
     The list comes from the paper feed's "ai" section (refreshed every three hours by GitHub Actions); while this view is open
     it checks for a newer feed every two hours and marks what arrived since the last visit. */
  AI_POLL_MS = 2 * 60 * 60 * 1000;

  // set by the feed (feed/papers.py, ai_kind): new candidates predicted, or AI-guided candidates made and measured
  AI_KIND_LABEL = { prediction: 'AI prediction', experiment: 'AI + experiment' };

  aiState = { built: false, kind: 'all', shown: 5, timer: 0, tick: 0, tickTimer: 0,
    seen: store.get('aiSeen') || '', newest: '' };

};

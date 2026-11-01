'use strict';
// papers-view: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconPapersView = function initializeSuperconPapersView() {


  /* ---------- New papers: curated recent advances and the live feed ---------- */
  PAPERS_URL = 'https://raw.githubusercontent.com/' + REPO + '/' + BRANCH + '/progress/papers.json';

  paperState = { data: null, at: 0, busy: false, failed: false, src: 'all', topic: 'all', shown: 20, kind: 'all', advAll: false, built: false, newsSrc: 'all', newsShown: 10 };

  PAPER_SOURCES = [['all', 'All'], ['arXiv', 'arXiv'], ['Nature', 'Nature'], ['Science', 'Science'], ['PRL', 'PRL'], ['PRX', 'PRX']];

};

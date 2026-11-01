'use strict';
// storm-current-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconStormCurrentDemo = function initializeSuperconStormCurrentDemo() {


  /* ---------- Storm in use (4.0 and later): the demo shows only the Storm in use, built over several rounds ----------
     Storm 1.0's trees (ai_model.versions), round 3's calibration (ai_model.calibration), round 4's average with the
     crystal-graph network (ai_model.ensemble) and round 5's 90% range (ai_model.uncertainty), all read from progress.json. */
  STORM_LATEST_STAGES = [
    { node: 'AI designs', short: 'Design' },
    { node: 'Inputs', short: 'Inputs' },
    { node: 'Learners', short: 'Learn' },
    { node: 'Prediction', short: 'Predict' },
    { node: 'Validation', short: 'Check' },
    { node: 'What’s new', short: 'New' }
  ];

};

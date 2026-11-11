'use strict';
// baseline-demos: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconBaselineDemos = function initializeSuperconBaselineDemos() {


  /* ---------- Baselines: the simple model that each of our AI models must beat ----------
     Storm's two baselines (hand-made features, and the MACE-MP-0 foundation model) learn computed Tc; Hurricane's and
     Radar's baselines read only the chemical formula. Scores come from progress.json, next to those of the model in use. */
  MODEL_STAGES.hurricane = [
    { node: 'Data', short: 'Data', title: 'Input: measured Tc' },
    { node: '33 numbers', short: 'Features', title: '33 numbers from the formula' },
    { node: 'Boosted trees', short: 'Trees', title: 'Gradient-boosted trees' },
    { node: 'Score', short: 'Score', title: 'Against Hurricane in use', titleFn: function () { var hi = hurFoldInfo(); return 'Against ' + (hi ? hurTitle(hi) : 'Hurricane'); } }
  ];

  MODEL_STAGES.radar = [
    { node: 'Data', short: 'Data', title: 'Input: each material’s family' },
    { node: '33 numbers', short: 'Features', title: '33 numbers from the formula' },
    { node: 'Classifier', short: 'Trees', title: 'A boosted classifier' },
    { node: 'Score', short: 'Score', title: 'Against Radar in use', titleFn: function () { var ri = radInfo(); return 'Against ' + (ri ? radTitle(ri) : 'Radar'); } }
  ];

  MODEL_VARIANTS = [['baseline', 'Storm'], ['foundation', 'Foundation'], ['hurricane', 'Hurricane'], ['radar', 'Radar']];

  MODEL_LABEL = { baseline: 'Storm’s baseline', foundation: 'Foundation model (for Storm)', hurricane: 'Hurricane’s baseline', radar: 'Radar’s baseline' };

  MODEL_REFS = { hurricane: ['sommer2023', 'jain2013', 'friedman2001', 'sklearn2011'], radar: ['sommer2023', 'jain2013', 'friedman2001', 'sklearn2011'] };

  COMP_GROUPS = [['count', 1], ['Z', 4], ['mass', 4], ['electroneg.', 4], ['row', 4], ['group', 4], ['radius', 4], ['Mendeleev', 4], ['valence', 4]];

};

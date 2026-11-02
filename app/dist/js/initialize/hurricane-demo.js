'use strict';
// hurricane-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconHurricaneDemo = function initializeSuperconHurricaneDemo() {


  /* ---------- Hurricane: the AI-designed model for unconventional superconductors, animated from its own results ----------
     Like Storm's demo, every number and label here comes from the "hurricane" block that each training round writes
     into progress.json, so a new version of Hurricane explains itself without new drawing code. */
  HUR_STAGES = [
    { node: 'Data', short: 'Data' },
    { node: 'AI designs', short: 'Design' },
    { node: 'Physics', short: 'Physics' },
    { node: 'Validation', short: 'Check' },
    { node: 'New family?', short: 'Family' },
    { node: 'Later finds', short: 'Later' }
  ];

  HUR_DUR = 8;

  HUR_FAMS = ['cuprate', 'iron-based', 'heavy-fermion', 'other oxide'];

  HUR_FAM_SHORT = { 'cuprate': 'Cuprates', 'iron-based': 'Fe, Ni-based', 'heavy-fermion': 'Heavy-fermion', 'other oxide': 'Other oxides' };

  HUR_FAM_TEXT = { 'cuprate': 'cuprates', 'iron-based': 'iron-based compounds', 'heavy-fermion': 'heavy-fermion compounds', 'other oxide': 'other oxides' };

  HUR_FEAT = {
    p_cu: 'nominal holes per Cu estimate', tm_d: 'nominal d-count estimate', nonint: 'non-integer formula proxy', aniso: 'layering proxy',
    oxide: 'oxygen share', mag3d: 'magnetic 3d share', cu_layers: 'Cu-count layer proxy', dome: 'empirical dome feature',
    heavy_block: 'Hg, Tl, Bi, Pb share', fe_based: 'FeAs/FeSe layer', f_share: 'f-electron share', f_count: 'f-electron count',
    f_spacing: 'f–f spacing', n_atoms_fu: 'atoms per formula', c_over_a: 'c/a', vpa: 'volume per atom'
  };

};

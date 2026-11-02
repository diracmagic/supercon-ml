'use strict';
// model-details: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconModelDetails = function initializeSuperconModelDetails() {


  /* ---------- Model details on the Progress view: Hurricane, and Storm calibrated to measured Tc ----------
     Both read only progress.json (the "hurricane" block and ai_model.calibration), so later training rounds
     appear here without an app update. */
  FEAT_LABEL = {
    tm_d: 'nominal d-count estimate', p_cu: 'nominal holes per Cu estimate', dome: 'empirical cuprate dome feature',
    cu_layers: 'Cu-count layer proxy (formula coefficient)', heavy_block: 'Hg, Tl, Bi, Pb share', fe_based: 'FeAs/FeSe-type composition flag',
    f_share: 'f-electron atom share', f_count: 'f-electron count', mag3d: 'magnetic 3d share', nonint: 'doping (non-integer stoichiometry)',
    n_atoms_fu: 'atoms per formula unit', oxide: 'oxygen share', chalcogenide: 'S, Se, Te share', pnictide: 'P, As, Sb share',
    halide: 'halogen share', vpa: 'volume per atom', density: 'density', aniso: 'layering (cell anisotropy)', c_over_a: 'c/a',
    f_spacing: 'f–f spacing (Hill limit)', pg_order: 'point-group order', n_elements: 'number of elements', context_flag: 'context flag',
    // Hurricane 2.0's structure types, read from the stoichiometry
    '123_cuprate': '123-type cuprate (YBCO)', '214_cuprate': '214-type cuprate (LSCO)', electron_doped_cuprate: 'electron-doped cuprate',
    Bi_cuprate: 'Bi-based cuprate', Tl_cuprate: 'Tl-based cuprate', Hg_cuprate: 'Hg-based cuprate', infinite_layer_cuprate: 'infinite-layer cuprate',
    '1111_pnictide': '1111 iron pnictide', '122_pnictide': '122 iron pnictide', '111_pnictide': '111 iron pnictide',
    '11_chalcogenide': '11 iron chalcogenide (FeSe)', '122_chalcogenide': '122 iron chalcogenide', nickel_pnictide: 'nickel pnictide',
    '115_heavy_fermion': '115 heavy fermion (CeCoIn₅)', '122_heavy_fermion': '122 heavy fermion (CeCu₂Si₂)',
    nickelate_oxide: 'nickelate', bismuthate_oxide: 'bismuthate', ruthenate_oxide: 'ruthenate', cobaltate_oxide: 'cobaltate'
  };

  PROP_LABEL = { Z: 'atomic number', atomic_mass: 'atomic mass', X: 'electronegativity', row: 'periodic-table row', group: 'periodic-table group',
    atomic_radius: 'atomic radius', mendeleev_no: 'Mendeleev number', valence: 'valence' };

  STAT_LABEL = { mean: 'mean', std: 'spread of', min: 'smallest', max: 'largest' };

  HUR_CHECKS = { false_alarms: 'at most half the false alarms', false_alarm_folds: 'fewer false alarms in 4 of 5 folds', tc: 'the measured-Tc error',
    superconductors: 'the error on the superconductors', brier: 'the Brier score', database_swap: 'the database swap' };

  HUR_FAM_SC = { 'cuprate': 'cuprate superconductors', 'iron-based': 'iron- and nickel-based superconductors', 'heavy-fermion': 'heavy-fermion superconductors', 'other oxide': 'superconducting other oxides' };

  HUR_CHECKS4 = { false_alarms: 'false alarms on at most 5%', called_unlikely: 'no more of a left-out family called unlikely than Hurricane 2.0',
    coverage: 'a chance for at least 85% of the held-out entries', tc: 'the measured-Tc error', superconductors: 'the error on the superconductors',
    brier: 'the Brier score', database_swap: 'the database swap' };

};

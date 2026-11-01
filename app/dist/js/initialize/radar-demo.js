'use strict';
// radar-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconRadarDemo = function initializeSuperconRadarDemo() {


  /* ---------- Radar: the AI-designed router between Storm and Hurricane, animated from its own results ----------
     Every number and label comes from the "radar" block that each training round writes into progress.json. */
  RAD_STAGES = [
    { node: 'Data', short: 'Data' },
    { node: 'AI designs', short: 'Design' },
    { node: 'Routing', short: 'Route' },
    { node: 'Validation', short: 'Check' },
    { node: 'New family?', short: 'Family' }
  ];

  RAD_DUR = 8;

  RAD_UNCONV = ['cuprate', 'iron-based', 'heavy-fermion', 'other oxide'];

  RAD_CONV = ['Other', 'Chevrel', 'Carbon'];

  RAD_LABEL = { 'cuprate': 'Cuprates', 'iron-based': 'Iron- and nickel-based', 'heavy-fermion': 'Heavy-fermion', 'other oxide': 'Other oxides',
    'Other': 'Other conventional', 'Chevrel': 'Chevrel phases', 'Carbon': 'Carbon-based' };

  RAD_SHORT = { 'cuprate': 'Cuprates', 'iron-based': 'Fe, Ni-based', 'heavy-fermion': 'Heavy-fermion', 'other oxide': 'Other oxides',
    'Other': 'Other', 'Chevrel': 'Chevrel', 'Carbon': 'Carbon' };

  RAD_TEXT = { 'cuprate': 'cuprates', 'iron-based': 'iron-based compounds', 'heavy-fermion': 'heavy-fermion compounds', 'other oxide': 'other oxides',
    'Other': 'other conventional superconductors', 'Chevrel': 'Chevrel phases', 'Carbon': 'carbon-based superconductors' };

};

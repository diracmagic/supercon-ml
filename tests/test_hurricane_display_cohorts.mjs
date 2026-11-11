import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const read = file => fs.readFileSync(new URL('../' + file, import.meta.url), 'utf8');
const progress = JSON.parse(read('progress/progress.json'));
const definitions = read('app/dist/js/definitions/hurricane-demo.js');
function infoFor(data) {
  const context = {state: {data}, list: value => Array.isArray(value) ? value : []};
  vm.runInNewContext(definitions + '\nthis.info = hurInfo();', context);
  return context.info;
}

// Hurricane 4.0 stays in the version list after a later release; these tests read its own entry by naming it.
function withH4(data) { data.hurricane.current = '4.0'; return data; }

test('the Hurricane 4.0 animation uses H4 entry counts and family sizes', () => {
  const info = infoFor(withH4(structuredClone(progress)));
  assert.equal(info.v.version, '4.0');
  assert.equal(info.data.n, 2123);
  assert.equal(info.data.n_sc, 1395);
  assert.equal(info.data.families.cuprate.n, 874);
});

test('the active Hurricane animation uses the entry of the version in use', () => {
  const info = infoFor(structuredClone(progress));
  const entry = progress.hurricane.versions.find(v => v.version === progress.hurricane.current);
  assert.equal(info.v.version, progress.hurricane.current);
  assert.equal(info.v.status, 'adopted');
  assert.deepEqual(info.data, entry.data);
  assert.equal(Object.values(info.data.families).reduce((sum, row) => sum + row.n, 0), info.data.n);
});

test('version-bound cohort wins over stale global metadata and switches with the version', () => {
  const data = withH4(structuredClone(progress));
  const h5 = data.hurricane.versions.find(v => v.version === '5.0');
  data.hurricane.data = h5.data;
  assert.equal(infoFor(data).data.n, 2123);
  data.hurricane.current = '5.0';
  data.hurricane.data = {n: 9999};
  const info = infoFor(data);
  assert.equal(info.v.status, 'experimental');
  assert.equal(info.data.n, 619);
  assert.equal(info.data.n_sc, 290);
});

test('older progress payloads without per-version metadata remain readable', () => {
  const data = structuredClone(progress);
  data.hurricane.versions.forEach(v => delete v.data);
  assert.equal(infoFor(data).data.n, progress.hurricane.data.n);
});

function numericalExamples(info) {
  const context = {hurInfo: () => info, list: value => Array.isArray(value) ? value : []};
  vm.runInNewContext(read('app/dist/js/definitions/prediction-demo.js') + '\nthis.examples = predHurExamples();', context);
  return context.examples;
}

test('the numerical Hurricane demonstration excludes actual H4 abstentions', () => {
  const info = infoFor(withH4(structuredClone(progress)));
  const ute = info.v.anchors.table.find(row => row.name === 'UTe2');
  assert.equal(ute.unknown, true);
  assert.equal(typeof ute.p_sc, 'number', 'A saved internal score must not override abstention');
  const examples = numericalExamples(info);
  assert.equal(examples.length, 3);
  assert.ok(examples.every(row => row.unknown !== true && row.use === 'score'));
  assert.ok(!examples.some(row => row.name === 'UTe2'));
  assert.ok(examples.some(row => row.name === 'CeRh2As2'), 'A valid same-family anchor remains available');
});

test('all anchors being unknown produces no numerical demonstration', () => {
  const info = infoFor(structuredClone(progress));
  info.v.anchors.table.forEach(row => { row.unknown = true; });
  assert.equal(numericalExamples(info).length, 0);
});

test('desktop and mobile anchor plots retain measurements but suppress abstained outputs', () => {
  for (const narrow of [false, true]) {
    function draw(unknown) {
      const dots = [], tags = [];
      const c = {beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, measureText: () => ({width: 20})};
      const C = {surface: 'white', accent: 'blue', ink2: 'gray', aqua: 'cyan'};
      const context = {list: value => Array.isArray(value) ? value : [],
        HUR_FAMS: ['heavy-fermion'], stormHeader() {}, stFont() {}, stSpan: () => 1,
        label() {}, stAlpha: value => value, dot: (...args) => dots.push(args),
        stTag: (_c, _C, text) => tags.push(text), c, C, narrow,
        info: {name: 'Hurricane', v: {version: '4.0', anchors: {table: [
          {name: 'UTe2', family: 'heavy-fermion', use: 'score', status: 'replicated',
           tc_exp: 1.6, pred: 0.18, unknown}
        ]}}}};
      vm.runInNewContext(definitions + '\ndrawHurLater(c, C, {x:0,y:0,w:600,h:300}, 10, narrow, info);', context);
      return {dots, tags};
    }
    const abstained = draw(true), predicted = draw(false);
    assert.equal(abstained.dots.length, 3, 'One measurement and two legend markers remain');
    assert.equal(predicted.dots.length, 4, 'A known entry additionally shows its prediction');
    assert.match(abstained.tags[0], /^unknown/);
    assert.match(predicted.tags[0], /^scored/);
  }
});

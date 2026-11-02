import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sources = JSON.parse(fs.readFileSync(new URL('../data/model_method_sources.json', import.meta.url), 'utf8'));
const source = fs.readFileSync(new URL('../app/dist/js/definitions/citation-contact.js', import.meta.url), 'utf8');
const flatten = e => [e, ...(e.children || []).flatMap(flatten)];
function harness() {
  const h = (tag, attrs, ...children) => {
    const node = {tag, attrs:attrs || {}, children:[], appendChild(x) {this.children.push(x);return x;}};
    if (attrs?.text) node.children.push(String(attrs.text));
    node.children.push(...children.flat(Infinity).filter(x => x !== null && x !== undefined));
    return node;
  };
  const c = vm.createContext({h, cardHead:(a,b) => h('header',null,a,b)});
  vm.runInContext(source,c);
  return {rows: JSON.parse(vm.runInContext('JSON.stringify(modelMethodSources())',c)), card:vm.runInContext('modelMethodsCard()',c)};
}

test('all audited method sources and project differences appear in Cite', () => {
  const {rows,card}=harness();
  assert.equal(rows.length,sources.selected_references.length);
  assert.equal(new Set(rows.map(r=>r.url)).size,rows.length);
  for (const r of sources.selected_references) {
    const entry=rows.find(x=>x.id===r.id);
    assert.ok(entry,r.id);
    assert.equal(entry.title,r.title);
    assert.equal(entry.url,'https://doi.org/'+r.doi);
    assert.equal(entry.ours,r.our_differences);
    assert.equal(r.not_a_novelty_claim,true);
  }
  const nodes=flatten(card);
  assert.equal(nodes.filter(x=>x.tag==='li').length,12);
  assert.equal(nodes.some(x=>x.tag==='details'),false);
  assert.ok(nodes.some(x=>x.tag==='a' && x.attrs.href==='https://github.com/diracmagic/supercon-ml/pull/17'));
});

test('direct model/data foundations and related benchmarks retain distinct meanings', () => {
  const refs=sources.selected_references;
  const cg=refs.find(r=>r.doi==='10.1103/PhysRevLett.120.145301');
  const mace=refs.find(r=>r.doi==='10.1063/5.0297006');
  assert.equal(cg.year,2018);assert.equal(mace.year,2025);
  assert.match(JSON.stringify(mace),/0b3/);
  assert.match(JSON.stringify(mace),/checkpoint/);
  assert.match(JSON.stringify(refs.find(r=>r.id==='konno2021-extrapolation')),/not adopted architecture|not the same temporal/);
  const stat=refs.find(r=>r.id==='lei2018-conformal');
  assert.match(stat.relationship,/NOT a superconductivity-specific/);
  assert.match(stat.our_differences,/not this method|not.*jackknife/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';

const read = file => fs.readFileSync(new URL('../app/dist/' + file, import.meta.url), 'utf8');
function harness() {
  const context = vm.createContext({ console, URL });
  for (const file of ['js/bindings.js', 'js/definitions/core.js', 'js/definitions/content.js', 'js/initialize/content.js', 'js/definitions/news-drawings.js']) vm.runInContext(read(file), context);
  vm.runInContext("store={get(){return ''}}; REPO_URL='https://github.com/diracmagic/supercon-ml';initializeSuperconContent();", context);
  context.content = JSON.parse(fs.readFileSync(new URL('../progress/content.json', import.meta.url), 'utf8'));
  vm.runInContext('applyContent(content)', context);
  const describe = article => { context.article = article; return JSON.parse(vm.runInContext('JSON.stringify(newsArticleDescribe(article))', context)); };
  const draw = (info, width = 360, time = 1.2) => {
    const calls = [];
    const methods = ['save','restore','setLineDash','translate','rotate','beginPath','closePath','stroke','fill','fillRect','strokeRect','rect','moveTo','lineTo','arc','ellipse','fillText'];
    const canvas = Object.fromEntries(methods.map(name => [name, (...args) => {
      for (const arg of args) if (typeof arg === 'number') assert.ok(Number.isFinite(arg), name);
      calls.push([name, ...args]);
    }]));
    context.canvas = canvas; context.info = info; context.width = width; context.time = time;
    vm.runInContext("newsArticleDraw(canvas,{ink:'#123',ink2:'#456',accent:'#278'},width,170,time,info)", context);
    return calls;
  };
  return { context, describe, draw, recent: vm.runInContext('JSON.parse(JSON.stringify(RECENT))', context) };
}

test('every public feed and current Recent entry has a source-specific, finite, nonempty illustration', () => {
  const h = harness(), feed = JSON.parse(fs.readFileSync(new URL('../progress/papers.json', import.meta.url), 'utf8'));
  const rows = ['news','arxiv','journals','ai'].flatMap(channel => (feed[channel] || []).map(item => ({ channel, item }))).concat(h.recent.map(item => ({ channel:'RECENT', item })));
  assert.ok(rows.length > 200);
  const signatures = new Map(), modes = new Set(), geometryGroups = new Map(), physicalSignatures = new Set(), audit = [];
  for (const {channel,item} of rows) {
    const info = h.describe(item);
    assert.ok(info.key && info.signature && info.concepts.length, item.title || item.h);
    assert.match(info.url, /^https:\/\//, info.title + ' keeps the original reference');
    const prior = signatures.get(info.signature);
    if (prior) assert.equal(prior.key, info.key, 'Different article identities must not silently receive identical source descriptors');
    signatures.set(info.signature, info); modes.add(info.mode);
    for (const fact of info.facts) {
      assert.ok(['title','summary','abstract','curated text'].includes(fact.field));
      assert.ok(fact.derived || fact.excerpt.includes(fact.text));
    }
    for (const width of [280, 720]) {
      const calls = h.draw(info, width);
      assert.ok(calls.filter(call => ['stroke','fillText','strokeRect'].includes(call[0])).length >= 8, info.title);
      assert.ok(calls.some(call => call[0] === 'fillText' && call[1] !== info.title), 'Substantive diagram text, not only a headline');
    }
    const geometryHash=crypto.createHash('sha256').update(JSON.stringify(h.draw(info).filter(call=>call[0]!=='fillText'))).digest('hex');
    geometryGroups.set(geometryHash,(geometryGroups.get(geometryHash)||0)+1);
    physicalSignatures.add(JSON.stringify({mode:info.mode,layers:info.layerCounts,materials:info.materials.map(m=>m.text),facts:info.facts.map(f=>[f.id,f.text])}));
    audit.push({ channel, geometry_hash:geometryHash, ...info });
  }
  assert.ok(modes.size >= 10, 'The real feed must use different scientific constructions');
  if (process.env.ARTICLE_AUDIT_PATH) fs.writeFileSync(process.env.ARTICLE_AUDIT_PATH, JSON.stringify({feed_updated:feed.updated,row_count:rows.length,mode_count:modes.size,full_source_signature_count:signatures.size,physical_descriptor_count:physicalSignatures.size,nontext_geometry_count:geometryGroups.size,largest_shared_geometry_group:Math.max(...geometryGroups.values()),neutral_question_fallback_count:audit.filter(x=>x.mode==='question').length,title_only_count:audit.filter(x=>x.sparse).length,limitations:['Full source signatures include extracted question concepts; they are not a count of independently designed crystal models.','Shared geometry is retained when supported scientific inputs are the same; no random visual uniqueness is added.','This is a public-title/abstract/curated-text review, not a full-paper verification.'],rows:audit},null,2)+'\n');
});

test('physical controls and named materials change drawing geometry, not only the headline or colour', () => {
  const h=harness();
  const geometry = item => JSON.stringify(h.draw(h.describe(item)).filter(call => call[0] !== 'fillText'));
  const examples = [
    {title:'Six-layer graphene under high pressure'},
    {title:'Bilayer graphene under tensile strain'},
    {title:'Four-probe resistivity of MgB2'},
    {title:'Terahertz pulses in MgB2'},
    {title:'Generative diffusion model for MgB2 structure proposals'},
    {title:'Graph neural network prediction for MgB2'},
    {title:'Heat capacity of LaH10'},
  ];
  assert.equal(new Set(examples.map(geometry)).size, examples.length);
  const a=h.describe({title:'Material study',abstract:'We use a four-probe resistivity measurement on MgB2.'});
  const b=h.describe({title:'Material study',abstract:'We use a generative diffusion model to propose LaH10.'});
  assert.notEqual(a.signature,b.signature);
  assert.notEqual(a.mode,b.mode);
  assert.notDeepEqual(h.draw(a).filter(c=>c[0]!=='fillText'),h.draw(b).filter(c=>c[0]!=='fillText'));
});

test('composition, layer counts, sparse records and evidence boundaries remain source-bound', () => {
  const h=harness();
  const formula=h.describe({title:'Transport in UTe₂, B₂CN and La₃Ni₂O₇',abstract:'DFT and BCS are methods, not compounds.'});
  assert.deepEqual(formula.materials.map(m=>m.text),['UTe2','B2CN','La3Ni2O7']);
  assert.equal(h.describe({title:'Six-layer graphene'}).layerCount,6);
  assert.equal(h.describe({title:'Bilayer graphene'}).layerCount,2);
  assert.deepEqual(h.describe({title:'Twisted bilayer-trilayer graphene'}).layerCounts,[2,3]);
  assert.equal(h.describe({title:'Twisted bilayer-trilayer graphene'}).layerCount,null);
  assert.deepEqual(h.describe({title:'Four- and five-layer graphene'}).layerCounts,[4,5]);
  assert.equal(h.describe({title:'Rhombohedral hexalayer graphene'}).layerCount,6);
  assert.deepEqual(h.describe({title:'Monolayer-Trilayer Phase of La3Ni2O7'}).layerCounts,[1,3]);
  assert.deepEqual(h.describe({title:'Graphene superconductivity',abstract:'Earlier work used bilayer graphene. Here we study a monolayer.'}).layerCounts,[1]);
  assert.equal(h.describe({title:'Infinite-layer nickelate'}).layerCount,null);
  assert.equal(h.describe({title:'Layered graphene'}).layerCount,null);
  const ambient=h.describe({title:'Nickelate films without applied pressure'});
  assert.equal(ambient.facts.some(f=>f.id==='pressure'),false);
  assert.equal(ambient.facts.some(f=>f.id==='ambient'),true);
  assert.equal(h.describe({title:'Superconductivity without pressure',abstract:'Earlier research required high pressure.'}).facts.some(f=>f.id==='pressure'),false);
  assert.equal(h.describe({title:'US scientists report a discovery'}).materials.length,0);
  assert.match(h.describe({title:'A phonon unlocks superconductivity in the Hubbard model',abstract:'Using numerically exact quantum Monte Carlo, we demonstrate a pairing relation.'}).evidence,/Theory \/ computation/);
  assert.match(h.describe({title:'Superconductivity was not observed in La3Ni2O7',abstract:'Resistance was measured down to 2 K.'}).evidence,/Negative claim/);
  const noHeat=h.describe({title:'A material study',abstract:'No heat capacity measurements were performed.'});
  assert.equal(noHeat.facts.some(f=>f.id==='thermal'),false);assert.doesNotMatch(noHeat.evidence,/Measurements mentioned/);
  assert.doesNotMatch(h.describe({title:'Ambient-pressure superconductivity',abstract:'No evidence for superconductivity existed before our discovery. We measured zero resistance.'}).evidence,/Negative claim/);
  const charge=h.describe({title:'Charge susceptibility in a lattice model',abstract:'We compute heat transport and optical susceptibility.'});
  assert.equal(charge.facts.some(f=>f.id==='magnetic'||f.id==='transport'),false);
  assert.equal(h.describe({title:'Unstrained superconducting films',abstract:'Earlier studies used tensile strain.'}).facts.some(f=>f.id==='strain'),false);
  assert.equal(h.describe({title:'Superconductivity without strain'}).facts.some(f=>f.id==='strain'),false);
  const unstableAmbient=h.describe({title:'Superconductivity is not stable at ambient pressure',abstract:'Here we study high pressure.'});
  assert.equal(unstableAmbient.facts.some(f=>f.id==='ambient'),false);
  assert.equal(unstableAmbient.facts.some(f=>f.id==='pressure'),true);
  const sparse=h.describe({title:'Unresolved question in material science',url:'https://example.org/paper'});
  assert.equal(sparse.mode,'question');assert.equal(sparse.sparse,true);assert.equal(sparse.materials.length,0);
  assert.match(sparse.evidence,/not established/);
  assert.match(h.describe({title:'Predicted superconductivity in LaH10'}).evidence,/not experimental proof/);
  assert.match(h.describe({title:'No superconductivity detected in a tested candidate'}).evidence,/Negative claim/);
});

test('article animation uses the existing reduced-motion, visibility and view lifecycle', () => {
  const frames=[], times=[],ctx={setTransform(){},clearRect(){},fillRect(){},save(){},restore(){}};
  const cv={clientWidth:360,clientHeight:170,isConnected:true};
  const it={cv,kind:'news-research',article:{key:'source'},t:0,vis:true,W:360,H:170,dpr:1,ctx};
  const c=vm.createContext({MINI:{items:[it],raf:0,last:1000},MINI_DRAW:{},MINI_STATIC:{},view:'papers',document:{hidden:false},window:{devicePixelRatio:1},
    newsArticleDraw:(_c,_C,_W,_H,t)=>times.push(t),colors:()=>({}),motionOK:()=>false,requestAnimationFrame:fn=>{frames.push(fn);return frames.length;}});
  vm.runInContext(read('js/definitions/mini-player.js'),c);
  vm.runInContext('miniFrame(1050)',c);assert.deepEqual(times,[1.2]);assert.equal(frames.length,0);
  c.motionOK=()=>true;vm.runInContext('miniFrame(1100)',c);assert.equal(it.t,.05);assert.equal(frames.length,1);
  c.document.hidden=true;vm.runInContext('miniFrame(1150)',c);assert.equal(times.length,2);
  c.document.hidden=false;c.view='progress';vm.runInContext('miniFrame(1200)',c);assert.equal(times.length,2);
  c.view='papers';it.vis=false;vm.runInContext('miniFrame(1250)',c);assert.equal(times.length,2);
});

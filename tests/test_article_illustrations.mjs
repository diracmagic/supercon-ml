import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const read = file => fs.readFileSync(new URL('../app/dist/' + file, import.meta.url), 'utf8');
class Element {
  constructor(tag) { this.tagName=tag; this.children=[]; this.attributes={}; this.className=''; this.isConnected=true; this.clientWidth=112; this.clientHeight=84; }
  setAttribute(key,value) { this.attributes[key]=String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  appendChild(node) { this.children.push(node); return node; }
  addEventListener() {}
}
const flatten = node => [node,...node.children.flatMap(flatten)];
const methods = ['setTransform','clearRect','save','restore','setLineDash','translate','rotate','scale','beginPath','closePath','stroke','fill','fillRect','strokeRect','rect','moveTo','lineTo','arc','ellipse','fillText'];
function recorder() {
  const calls=[];
  return {calls, canvas:Object.fromEntries(methods.map(name=>[name,(...args)=>{
    for(const arg of args) if(typeof arg==='number') assert.ok(Number.isFinite(arg),name);
    calls.push([name,...args]);
  }]))};
}
function harness() {
  const document={hidden:false,createElement:tag=>new Element(tag),createTextNode:text=>Object.assign(new Element('#text'),{textContent:text})};
  const context=vm.createContext({console,URL,document,Node:Element,window:{devicePixelRatio:1},
    stAlpha:value=>value,stRng:()=>()=>.5,mix:a=>a,stRound:()=>{},
    colors:()=>({surface:'#fff',surface2:'#fafafa',accent:'#368',ink:'#123',ink2:'#234',axis:'#678',grid:'#abc',muted:'#789',warm:'#c63',aqua:'#1a7',gold:'#b81'}),
    motionOK:()=>false,requestAnimationFrame:()=>1});
  for(const file of ['js/bindings.js','js/definitions/core.js','js/definitions/content.js','js/initialize/content.js','js/definitions/news-drawings.js','js/definitions/ai-view.js','js/definitions/mini-player.js','js/initialize/news-drawings.js','js/initialize/news-looks.js']) vm.runInContext(read(file),context);
  vm.runInContext("store={get(){return ''}}; REPO_URL='https://github.com/diracmagic/supercon-ml';initializeSuperconContent(); MINI={items:[],raf:0,last:0};MINI_DRAW={};MINI_STATIC={};MINI_ALT={};view='papers';initializeSuperconNewsDrawings();initializeSuperconNewsLooks();",context);
  context.content=JSON.parse(fs.readFileSync(new URL('../progress/content.json',import.meta.url),'utf8'));
  vm.runInContext('applyContent(content)',context);
  const describe=article=>{context.article=article;return JSON.parse(vm.runInContext('JSON.stringify(newsArticleDescribe(article))',context));};
  const figure=(article,kind)=>{context.article=article;context.kind=kind;return vm.runInContext('newsArticleFigure(article,kind)',context);};
  const render=(figure,width=112,height=84)=>{
    const node=flatten(figure).find(x=>x.tagName==='canvas'),r=recorder();
    node.clientWidth=width;node.clientHeight=height;node.getContext=()=>r.canvas;context.node=node;
    vm.runInContext('MINI.items=MINI.items.filter(function(it){return it.cv===node;});MINI.items[0].W=0;miniFrame(1200)',context);
    return r.calls;
  };
  return {context,describe,figure,render,recent:vm.runInContext('JSON.parse(JSON.stringify(RECENT))',context)};
}

test('every public feed and Recent entry retains one compact original-theme thumbnail and its source identity',()=>{
  const h=harness(),feed=JSON.parse(fs.readFileSync(new URL('../progress/papers.json',import.meta.url),'utf8'));
  const rows=['news','arxiv','journals','ai'].flatMap(channel=>(feed[channel]||[]).map(item=>({channel,item}))).concat(h.recent.map(item=>({channel:'RECENT',item})));
  assert.ok(rows.length>200);
  const kinds=new Set(),audit=[];
  for(const {channel,item} of rows){
    const info=h.describe(item),figure=h.figure(item),nodes=flatten(figure),canvas=nodes.find(n=>n.tagName==='canvas');
    assert.equal(figure.tagName,'div');assert.equal(figure.className,'news-art');assert.equal(nodes.length,2);
    assert.equal(nodes.filter(n=>n.tagName==='canvas').length,1);
    assert.equal(nodes.some(n=>['figure','figcaption','details','summary'].includes(n.tagName)),false);
    assert.equal(canvas.className,'mini');
    assert.equal(figure.getAttribute('data-article-key'),info.key);assert.equal(canvas.getAttribute('data-article-key'),info.key);
    assert.equal(figure.getAttribute('data-source-url'),info.url);assert.match(info.url,/^https:\/\//,info.title);
    assert.equal(canvas.getAttribute('title'),info.title);assert.ok(canvas.getAttribute('aria-label').includes(info.title));
    const kind=canvas.getAttribute('data-news-art');kinds.add(kind);
    h.context.selectedKind=kind;assert.equal(vm.runInContext('typeof MINI_DRAW[selectedKind]',h.context),'function');
    for(const [width,height] of [[112,84],[88,66]]){
      const calls=h.render(figure,width,height);
      assert.ok(calls.filter(c=>['stroke','fill','fillRect','strokeRect','fillText'].includes(c[0])).length>=3,info.title);
    }
    for(const fact of info.facts){assert.ok(['title','summary','abstract','curated text'].includes(fact.field));assert.ok(fact.derived||fact.excerpt.includes(fact.text));}
    audit.push({channel,key:info.key,title:info.title,source_url:info.url,theme:kind,evidence:info.evidence});
  }
  assert.ok(kinds.size>=10,'Existing subject animations remain varied; no unique crystal is invented for every article');
  if(process.env.ARTICLE_AUDIT_PATH) fs.writeFileSync(process.env.ARTICLE_AUDIT_PATH,JSON.stringify({feed_updated:feed.updated,row_count:rows.length,theme_count:kinds.size,compact_canvas_count:rows.length,limitations:['Related articles may share a topic schematic; badges, element dots and neutral colour or framing variants keep each thumbnail distinct.','Titles and source links retain individual identity; drawings are not measured structures or traces.','Feed text is not independent full-paper verification.'],rows:audit},null,2)+'\n');
});

test('explicit theme and AI selection are preserved without an expanded drawing or related illustration',()=>{
  const h=harness();
  const selected=h.figure({title:'Cuprate transport',topics:['Cuprates'],url:'https://example.org/paper'},'news-measurement');
  assert.equal(selected.children[0].getAttribute('data-news-art'),'news-measurement');
  assert.equal(selected.children.length,1);
  const ai=h.figure({title:'Guided diffusion for new superconductors',ai_kind:'generation',url:'https://example.org/ai'});
  assert.equal(ai.children[0].getAttribute('data-news-art'),'news-search');
  assert.doesNotMatch(read('js/definitions/news-drawings.js'),/What this drawing uses|Related concept illustration|article-figure|h\('details'/);
});

test('curated metadata and explicit ambient pressure or moire exclusions select faithful compact subjects',()=>{
  const h=harness(),kind=item=>h.figure(item).children[0].getAttribute('data-news-art');
  assert.equal(kind({h:'Vortices split into fractional vortices',x:'A scanning experiment.'}),'news-vortex');
  assert.equal(kind({h:'A single CuO₂ plane still superconducts',x:'A cuprate film.'}),'news-cuprate');
  assert.equal(kind({h:'Ambient-pressure nickelate films',x:'A bilayer nickelate.'}),'news-nickelate');
  assert.notEqual(kind({title:'Nickelates without applied pressure'}),'news-pressure');
  assert.equal(kind({title:'Pressure-quench recovery of ambient-pressure superconductivity'}),'news-pressure');
  assert.equal(kind({title:'Graphene superconductivity',summary:'Twisted layers make a moiré pattern.'}),'news-moire');
  assert.equal(kind({title:'Graphene superconductivity',summary:'Here it appears without a moiré pattern.'}),'news-layered');
  assert.equal(kind({title:'Properties of holographic superconductors from machine learning'}),'news-features');
});

test('an unregistered theme gets a legible neutral glyph, not a scaled-down text diagram',()=>{
  const h=harness(),figure=h.figure({title:'Unresolved material question',url:'https://example.org/question'},'unknown-theme');
  for(const [width,height] of [[112,84],[88,66]]){
    const calls=h.render(figure,width,height);
    assert.equal(calls.some(c=>c[0]==='fillText'),false,'No tiny article text is painted into a thumbnail');
    assert.equal(calls.filter(c=>c[0]==='strokeRect').length,1);
    assert.equal(calls.filter(c=>c[0]==='stroke').length,4);
    for(const [method,x,y,w,hh] of calls.filter(c=>c[0]==='strokeRect')){
      assert.ok(x>=0&&y>=0&&x+w<=width&&y+hh<=height);
    }
  }
  assert.match(figure.children[0].getAttribute('aria-label'),/no material structure or measured result/);
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

test('original theme drawing takes priority over article fallback through reduced-motion and visibility lifecycle',()=>{
  const frames=[],original=[],fallback=[],ctx={setTransform(){},clearRect(){},fillRect(){},save(){},restore(){}};
  const cv={clientWidth:112,clientHeight:84,isConnected:true};
  const it={cv,kind:'news-cuprate',article:{key:'source'},t:0,vis:true,W:112,H:84,dpr:1,ctx};
  const c=vm.createContext({MINI:{items:[it],raf:0,last:1000},MINI_DRAW:{'news-cuprate':(_c,_C,_W,_H,t)=>original.push(t)},MINI_STATIC:{'news-cuprate':1.2},view:'papers',document:{hidden:false},window:{devicePixelRatio:1},
    newsArticleDraw:(_c,_C,_W,_H,t)=>fallback.push(t),colors:()=>({}),motionOK:()=>false,requestAnimationFrame:fn=>{frames.push(fn);return frames.length;}});
  vm.runInContext(read('js/definitions/mini-player.js'),c);
  vm.runInContext('miniFrame(1050)',c);assert.deepEqual(original,[1.2]);assert.equal(fallback.length,0);assert.equal(frames.length,0);
  c.motionOK=()=>true;vm.runInContext('miniFrame(1100)',c);assert.equal(it.t,.05);assert.equal(frames.length,1);assert.equal(fallback.length,0);
  c.document.hidden=true;vm.runInContext('miniFrame(1150)',c);assert.equal(original.length,2);
  c.document.hidden=false;c.view='progress';vm.runInContext('miniFrame(1200)',c);assert.equal(original.length,2);
  c.view='papers';it.vis=false;vm.runInContext('miniFrame(1250)',c);assert.equal(original.length,2);
  it.vis=true;it.kind='unknown-theme';c.motionOK=()=>false;vm.runInContext('miniFrame(1300)',c);assert.deepEqual(fallback,[1.2]);assert.equal(original.length,2);
  it.cv.isConnected=false;vm.runInContext('miniFrame(1350)',c);assert.equal(fallback.length,1);
});

test('no two News & papers thumbnails are drawn alike, and every badge comes from the article text',()=>{
  const h=harness(),feed=JSON.parse(fs.readFileSync(new URL('../progress/papers.json',import.meta.url),'utf8'));
  const rows=['news','arxiv','journals','ai'].flatMap(channel=>feed[channel]||[]).concat(h.recent);
  const drawn=new Map(),seen=new Set();
  for(const item of rows){
    const figure=h.figure(item),canvas=flatten(figure).find(n=>n.tagName==='canvas'),id=canvas.getAttribute('data-news-art')+'\n'+canvas.getAttribute('data-article-key');
    if(seen.has(id))continue;
    seen.add(id);
    // Record colours and line styles as well as geometry: a colour set alone may tell two drawings apart.
    const calls=[],canvasNode=flatten(figure).find(n=>n.tagName==='canvas');
    canvasNode.getContext=()=>new Proxy({},{get:(_t,name)=>(...args)=>{calls.push([name,...args]);},set:(_t,name,value)=>{calls.push(['='+String(name),value]);return true;}});
    h.context.node=canvasNode;
    vm.runInContext('MINI.items=MINI.items.filter(function(it){return it.cv===node;});MINI.items[0].W=0;miniFrame(1200)',h.context);
    const info=h.describe(item),key=JSON.stringify(calls);
    assert.equal(drawn.has(key),false,'Same drawing for '+info.title+' and '+drawn.get(key));
    drawn.set(key,info.title);
    const look=JSON.parse(vm.runInContext('JSON.stringify(MINI.items[0].article.look)',h.context));
    if(look.formula) assert.ok(info.materials.some(m=>m.field==='title'&&m.text===look.formula),info.title);
    if(look.probe) assert.ok(look.from==='title'||info.facts.some(f=>f.field===look.from),info.title);
    if(look.tc) assert.match(info.title,/\d\s?m?K/);
    assert.match(canvas.getAttribute('aria-label'),/Colours and framing only tell thumbnails apart\./);
  }
  assert.ok(drawn.size>250);
});

test('badges, element dots and thermometers are read from the article and respect negation',()=>{
  const h=harness();
  const look=(article,kind)=>{h.render(h.figure(article,kind));return JSON.parse(vm.runInContext('JSON.stringify(MINI.items[0].article.look)',h.context));};
  const stm=look({title:'STM imaging of pair density waves in La₃Ni₂O₇ films near 80 K',url:'https://example.org/a'});
  assert.equal(stm.probe,'stm');assert.equal(stm.from,'title');assert.equal(stm.formula,'La3Ni2O7');assert.equal(stm.tc,80);
  assert.deepEqual(stm.comp.map(e=>[e.el,e.n]),[['La',3],['Ni',2],['O',7]]);
  assert.notEqual(look({title:'Nickelate films without applied pressure',abstract:'Earlier research required high pressure.',url:'https://example.org/b'}).probe,'anvil');
  assert.equal(look({title:'Author Correction: Magnetic field screening in hydrides',url:'https://example.org/c'}).notice,'fix');
  assert.equal(look({title:'Reply to: Conductance measurements in junctions',url:'https://example.org/d'}).notice,'reply');
  assert.equal(look({title:'Addendum: Magnetic field screening',url:'https://example.org/e'}).notice,'add');
  assert.equal(look({title:'The lutetium hydride room-temperature claim is retracted',url:'https://example.org/f'}).notice,'retract');
  assert.equal(look({title:'Charge order in 1T-TaS₂ flakes',url:'https://example.org/g'}).tesla,0,'A polytype is not a field value');
  assert.equal(look({title:'Superconductivity near 80 mK in a twisted bilayer',url:'https://example.org/h'}).tc,.08);
  assert.equal(look({title:'Pressure-induced superconductivity',url:'https://example.org/i'},'news-pressure').probe,'','A badge never repeats what the theme draws');
  const a=look({title:'First cuprate study',url:'https://example.org/j'},'news-cuprate'),b=look({title:'Second cuprate study',url:'https://example.org/k'},'news-cuprate');
  assert.notDeepEqual([a.v,a.p],[b.v,b.p]);
  assert.deepEqual(look({title:'First cuprate study',url:'https://example.org/j'},'news-cuprate'),a,'An article keeps its look when a list is redrawn');
  assert.equal(h.describe({title:'Scientists from NUS report a new superconductor'}).materials.length,0);
  assert.deepEqual(h.describe({title:'Superconductivity in FeSe and NbN films'}).materials.map(m=>m.text),['FeSe','NbN']);
});

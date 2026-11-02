'use strict';
// news-drawings: shared lexical function definitions; no startup side effects.

  const newsArt = function newsArt(n) {
    var tp = list(n.topics), head = String(n.title || ''), body = head + ' ' + String(n.summary || '') + ' ' + String(n.abstract || '');
    // Match the stated subject before broad tags. These are labelled subject schematics,
    // never reconstructed structures, measured traces or evidence of superconductivity.
    if (/\bStorm\b/i.test(head) && /range|interval|conformal/i.test(head)) return 'news-interval';
    if (/\bRadar\b/i.test(head)) return 'news-routing';
    if (/\bHurricane\b/i.test(head)) return /two.parts|two.stage|[2-9]\.0/i.test(head) ? 'news-two-stage' : 'news-tree';
    if (/\bStorm\b/i.test(head) && !/graph|network/i.test(head)) return 'news-tree';
    if (/literature|retrieval[- ]augmented|question answering|text mining|language model|corpus|structured extraction/i.test(head)) return 'news-literature';
    if (/stripes?|Hubbard|Kondo[- ]Heisenberg/i.test(head)) return 'news-stripes';
    if (/geometry of materials|common features|representation|tangent kernel/i.test(head)) return 'news-features';
    if (/density of states|spectroscop|Raman|muon stopping|ultrasound/i.test(head)) return 'news-spectrum';
    if (/vorti(?:ces|ex)/i.test(head)) return 'news-vortex';
    if (/graphene/i.test(head) && !/twist|moir[eé]/i.test(head)) return /(?:six|6)[- ]layer/i.test(head) ? 'news-layered-six' : 'news-layered';
    if (/electron[– -]phonon|phonon|breathing mode/i.test(head)) return 'news-eph';
    if (/magnon|spin wave/i.test(head) && !/circuit|qubit/i.test(head)) return 'news-stripes';
    if (/graph neural|line[- ]graph|ALIGNN|crystal[- ]graph/i.test(head)) return 'news-graph';
    if (/generat|diffusion|inverse design|structure search|physics judge/i.test(head)) return 'news-search';
    if (/terahertz|picosecond|laser|light pulse/i.test(head)) return 'news-light';
    if (/pressure|diamond anvil|\bGPa\b/i.test(head)) return 'news-pressure';
    if (/nanowire/i.test(head)) return 'news-topo';
    if (/kagome/i.test(head)) return 'news-kagome';
    if (n.ai_kind === 'experiment') return 'news-measurement';
    if (n.ai_kind === 'generation') return 'news-search';
    if (n.ai_kind === 'data' || n.ai_kind === 'review') return 'news-literature';
    var materialTopics = ['Hydrides', 'Cuprates', 'Nickelates', 'Iron-based', 'Moiré and 2D', 'Kagome', 'Heavy fermions'];
    if (materialTopics.filter(function (topic) { return tp.indexOf(topic) >= 0; }).length > 1) return 'news-features';
    if (tp.indexOf('Cuprates') >= 0) return 'news-cuprate';
    if (tp.indexOf('Nickelates') >= 0 && /\bbilayer\b|\bdouble[- ]layer\b/i.test(body) && !/\binfinite[- ]layer\b/i.test(body)) return 'news-nickelate';
    if (tp.indexOf('Nickelates') >= 0) return 'news-layered';
    if (tp.indexOf('Kagome') >= 0) return 'news-kagome';
    if (tp.indexOf('Moiré and 2D') >= 0 && /\btwist(?:ed|ing)?\b/i.test(body)) return 'news-moire';
    if (tp.indexOf('Moiré and 2D') >= 0) return 'news-layered';
    if (tp.indexOf('Iron-based') >= 0) return 'news-iron';
    if (tp.indexOf('Hydrides') >= 0) return 'news-hydride';
    if (tp.indexOf('Heavy fermions') >= 0) return 'news-heavy';
    if (tp.indexOf('Triplet and ruthenates') >= 0 && /triplet/i.test(body)) return 'news-triplet';
    if (tp.indexOf('Topological') >= 0) return 'news-topo';
    if (tp.indexOf('Electron–phonon') >= 0) return 'news-eph';
    if (tp.indexOf('Vortices and junctions') >= 0 && /junction/i.test(body)) return 'news-junction';
    if (tp.indexOf('AI and data') >= 0) return 'news-ai';
    // older feed entries carry "Quantum devices" for any story that mentions quantum computers, so look for a device word too
    if (/qubit|transmon|fluxonium|quantum (processor|computer|computing|information|memory|technolog)|superconducting circuit|circuit QED|single-photon/i.test(head) ||
        /qubit|transmon|fluxonium|circuit QED/i.test(body)) return 'news-qubit';
    if (/meissner|levitat/i.test(head)) return 'news-general';
    if (/experiment|measur|resistance|critical.current|magnet|two (?:quantum |superconducting )states|two flavors/i.test(head)) return 'news-measurement';
    return 'news-research';
  };

  // Article descriptions are assembled only from public source text. These are
  // diagrams of what the source discusses, not recovered crystal coordinates,
  // measured traces, proof of a mechanism or an independent literature review.
  const newsArticleDescribe = function newsArticleDescribe(article) {
    var n = article || {}, sub = '₀₁₂₃₄₅₆₇₈₉', fields = [];
    function plain(value) {
      return String(value || '').replace(/<[^>]*>/g, '').replace(/[₀-₉]/g, function (x) { return String(sub.indexOf(x)); })
        .replace(/\\(?:mathrm|text|textrm)\{([^}]+)\}/g, '$1').replace(/[$_{}]/g, '').replace(/\s+/g, ' ').trim();
    }
    [['title', n.title || n.h], ['summary', n.summary], ['abstract', n.abstract], ['curated text', n.x]].forEach(function (entry) {
      var text = plain(entry[1]); if (text) fields.push({ field: entry[0], text: text });
    });
    var title = fields.length ? fields[0].text : 'Research record', all = fields.map(function (f) { return f.text; }).join(' ');
    function evidence(pattern, positiveOnly) {
      for (var i = 0; i < fields.length; i++) {
        var scan=new RegExp(pattern.source,pattern.flags.replace(/g/g,'')+'g'), hit;
        while((hit=scan.exec(fields[i].text))){
          var before=fields[i].text.slice(0,hit.index).split(/[.!?;]/).pop(),after=fields[i].text.slice(hit.index+hit[0].length).split(/[.!?;]/)[0];
          var historical=fields[i].field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|prior studies|past studies|before our)\b/i.test(before.slice(-90)+' '+after.slice(0,50));
          var negated=/\b(?:no|not|without|neither|absence of|lack of)\b[^,;.!?]{0,55}$/i.test(before) || /^[^,;.!?]{0,40}\b(?:not|never)\s+(?:observed|measured|performed|applied|detected|used|present)/i.test(after);
          if(positiveOnly && (historical||negated)) continue;
          return { text: hit[0], field: fields[i].field, excerpt: fields[i].text.slice(Math.max(0, hit.index - 36), hit.index + hit[0].length + 56) };
        }
      }
      return null;
    }
    var facts = [];
    function add(id, label, pattern) {
      var hit = evidence(pattern, true);
      if (hit && id === 'pressure' && /\b(?:without|no)\s+(?:applied |external |high[- ])?pressure\b/i.test(hit.excerpt)) hit = null;
      if (hit) facts.push({ id: id, label: label, text: hit.text, field: hit.field, excerpt: hit.excerpt });
      return hit;
    }
    // Numeric layer counts are explicit in the source; "layered" alone has no
    // inferred layer count. "Infinite-layer" is a phase name, not one sheet.
    var layerMap = { mono: 1, bi: 2, tri: 3, tetra: 4, penta: 5, hexa: 6, hepta: 7, octa: 8, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8 }, layerValues = [], layerEvidence = null;
    for(var lf=0;lf<fields.length;lf++) {
      var layerText=fields[lf].text.replace(/\b(two|three|four|five|six|seven|eight|[1-8])-\s*(?:and|or)\s+(two|three|four|five|six|seven|eight|[1-8])-layer\b/gi,'$1-layer and $2-layer');
      var layerPattern=/\b(?:mono|bi|tri|tetra|penta|hexa|hepta|octa)layer\b|\b(?:mono|bi|tri|four|five|six|seven|eight|two|three|[1-8])[- ]layer\b/gi, found=[],layerMatch;
      while((layerMatch=layerPattern.exec(layerText))){
        var beforeLayer=layerText.slice(0,layerMatch.index).split(/[.!?;]/).pop(),afterLayer=layerText.slice(layerMatch.index+layerMatch[0].length).split(/[.!?;]/)[0];
        if(fields[lf].field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|prior studies|past studies|before our)\b/i.test(beforeLayer.slice(-90)+' '+afterLayer.slice(0,50)))continue;
        if(/\b(?:no|not|without|neither|absence of|lack of)\b[^,;.!?]{0,55}$/i.test(beforeLayer) || /^[^,;.!?]{0,40}\b(?:not|never)\s+(?:observed|measured|performed|applied|detected|used|present)/i.test(afterLayer))continue;
        found.push(layerMatch[0]);
      }
      if(found.length){found.forEach(function(s){var prefix=s.toLowerCase().replace(/[- ]?layer$/,''),v=layerMap[prefix]||parseInt(prefix,10);if(layerValues.indexOf(v)<0)layerValues.push(v);});
        layerEvidence={id:'layers',label:'Layer counts mentioned',text:found.join(' / '),field:fields[lf].field,excerpt:fields[lf].text,derived:true};break;}
    }
    var layerCount = layerValues.length===1 ? layerValues[0] : null;
    if(layerEvidence) facts.push(layerEvidence);
    var ambient = evidence(/\bambient[- ]pressure\b|\bwithout (?:applied )?pressure\b|\bpressure[- ]free\b/i,true);
    if(ambient) facts.push({id:'ambient',label:'Ambient pressure mentioned',text:ambient.text,field:ambient.field,excerpt:ambient.excerpt});
    add('pressure', 'Pressure discussed', /\b(?:high|hydrostatic|extreme|external|applied)[- ]pressure\b|\bpressure[- ](?:induced|driven|quench|tuning)\b|\bdiamond[- ]anvil\b|\b\d+(?:\.\d+)?\s*GPa\b/i);
    // An ambient/no-pressure headline is the article's scope. Historical high-
    // pressure background must not turn that headline into an anvil experiment.
    if(ambient && ambient.field==='title' && !/\bquench\b/i.test(title)) facts=facts.filter(function(f){return f.id!=='pressure'||f.field==='title';});
    add('strain', 'Strain discussed', /\b(?:tensile|compressive|uniaxial|biaxial)?\s*strain(?:ed|ing|[- ]tunable)?\b/i);
    if(/\b(?:unstrained|strain[- ]free|without strain)\b/i.test(title)) facts=facts.filter(function(f){return f.id!=='strain';});
    add('doping', 'Carrier control discussed', /\b(?:electron|hole|chemical|electrostatic)[- ]dop(?:ed|ing)\b|\bdual[- ]gate\b|\bgat(?:e[- ]tunable|ing)\b/i);
    add('light', 'Electromagnetic probe / drive', /\bterahertz\b|\bmillimeter[- ]wave\b|\blaser\b|\blight[- ](?:induced|pulse|driven)\b|\bpicosecond\b/i);
    add('four-probe', 'Four-terminal method mentioned', /\bfour[- ](?:probe|terminal|point)\b/i);
    add('transport', 'Electrical transport discussed', /\bresistivit(?:y|ies)\b|\bresistance\b|\b(?:charge|electrical|electron|electronic) transport\b|\bcurrent[- ]voltage\b/i);
    add('magnetic', 'Magnetic response discussed', /\bmagneti[sz]ation\b|\b(?:magnetic|spin) susceptibilit(?:y|ies)\b|\bmagnetic field\b|\bmuon[- ]spin\b/i);
    add('thermal', 'Thermodynamics discussed', /\bspecific heat\b|\bheat capacit(?:y|ies)\b|\bcalorimetr\w*\b|\bthermodynamic\w*\b/i);
    add('spectrum', 'Spectroscopy discussed', /\bphotoemission\b|\bARPES\b|\btunnell?ing spectroscop\w*\b|\bRaman\b|\bneutron scattering\b|\bdensity of states\b|\bspectroscop\w*\b/i);
    add('generation', 'Structure proposal method', /\bdiffusion models?\b|\bgenerative\b|\binverse design\b|\bstructure search\b|\bguided diffusion\b/i);
    add('network', 'Learned representation / predictor', /\b(?:graph |line[- ]graph |deep |convolutional )?neural networks?\b|\bALIGNN(?:\s*2\.0)?\b|\bneural tangent kernels?\b|\bmachine[- ]learning\b|\bdeep learning\b/i);
    add('literature', 'Document / data method', /\bretrieval[- ]augmented\b|\bstructured extraction\b|\btext mining\b|\blanguage models?\b|\bliterature\b|\bdatabase\b/i);
    add('calculation', 'Theoretical / numerical method', /\bDFPT\b|\bDFT\b|\bEliashberg\b|\bfirst[- ]principles\b|\bexact diagonalization\b|\bdensity[- ]functional\b|\bHubbard\b|\bHamiltonian\b|\bBogoliubov\b|\bMonte Carlo\b/i);
    add('junction', 'Device geometry discussed', /\bJosephson junction\w*\b|\bquantum dots?\b|\bnanowire\w*\b|\bqubits?\b|\btransmons?\b|\bthree[- ]terminal\b/i);
    add('phonon', 'Lattice coupling discussed', /\belectron[-– ]phonon\b|\bphonon\w*\b|\bbreathing mode\b/i);
    add('vortex', 'Vortex response discussed', /\bvort(?:ex|ices)\b/i);
    add('gap', 'Pairing / gap question', /\b(?:nodeless|nodal|d[- ]wave|s[- ]wave|p[- ]wave|chiral|triplet)\b|\bpairing\b|\bsuperconducting gap\b/i);
    add('correlations', 'Correlations / competing order', /\bstripes?\b|\bcharge[- ]density[- ]wave\b|\bChern insulators?\b|\bcorrelat(?:ed|ions?)\b|\bnematic\w*\b|\bquantum critical\w*\b/i);
    add('boundary', 'Topology / boundary question', /\btopolog\w*\b|\bMajorana\b|\bedge states?\b|\bKitaev\b/i);
    var symbols = ('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr').split(' ');
    var blocked = /^(?:BCS|BEC|DFT|DFPT|DOS|SOC|SC|AI|ML|THz|GHz|MHz|GPa|MPa|Pa|K|Tc|TA|PR|PI|US|UK|UN|SI|IS|AS|IT|ON|AT|IN|OR|AND|In|As|He|No|Bi|Fm)$/;
    var materials = [], materialSeen = {};
    fields.forEach(function (f) {
      var normalized = f.text.replace(/([A-Z][a-z]?)\s+(\d)/g, '$1$2').replace(/(\d)\s+([A-Z])/g, '$1$2');
      (normalized.match(/\b[A-Z][A-Za-z0-9]*(?:\.[0-9]+)?\b/g) || []).forEach(function (token) {
        if (blocked.test(token) || materialSeen[token] || token.length > 30) return;
        var parts = token.match(/[A-Z][a-z]?(?:\d+(?:\.\d+)?)?/g) || [];
        if (parts.join('') !== token || parts.length < 2 || parts.some(function (part) { return symbols.indexOf(part.match(/^[A-Z][a-z]?/)[0]) < 0; })) return;
        materialSeen[token] = true;
        materials.push({ text: token, field: f.field, components: parts.map(function (part) { var m = /^([A-Z][a-z]?)(.*)$/.exec(part); return { element: m[1], count: m[2] || '1' }; }) });
      });
    });
    var named = evidence(/\bgraphene\b|\bsamarium nickelates?\b|\bnickelates?\b|\bcuprates?\b|\bhydrides?\b|\bruthenates?\b|\biron[- ]based\b|\blithium[- ]6\b|\bHg[- ]1223\b|\bBi[- ]2223\b|\bkagome\b/i);
    var subjects = title.split(/\s+(?:in|of|using|via|under|through|with|from|for|and|on|over)\s+/i).map(function (x) { return x.trim().replace(/[.:;,]$/, ''); }).filter(function (x) { return x.length > 3; });
    // Text concepts are retained in sparse metadata cases rather than inventing
    // a sample or experiment. Different research questions remain different.
    var concepts = subjects.length ? subjects.slice(0, 5) : [title];
    var ids = facts.map(function (f) { return f.id; }), has = function (id) { return ids.indexOf(id) >= 0; };
    var modes = [['generation','generation'],['literature','documents'],['network','network'],['light','light'],['four-probe','transport'],
      ['transport','transport'],['spectrum','spectrum'],['thermal','thermal'],['magnetic','magnetic'],['junction','device'],['calculation','theory'],
      ['phonon','phonon'],['vortex','vortex'],['pressure','pressure'],['strain','strain'],['doping','carrier'],['layers','layers'],
      ['correlations','correlations'],['gap','pairing'],['boundary','boundary']];
    // A method/subject explicitly named in the headline has priority over a
    // keyword in abstract background. Body matches remain labelled mentions.
    var primary = modes.filter(function(pair){return facts.some(function(f){return f.id===pair[0] && f.field==='title';});})[0];
    if(!primary) primary=modes.filter(function(pair){return has(pair[0]);})[0];
    var mode = primary ? primary[1] : 'question';
    var theoretical = has('calculation') || /\b(?:theory|computation|theoretical|simulation|numerically exact|mean[- ]field|we compute|we calculate)\b/i.test(all+' '+(n.kind||n.k||''));
    var measured = evidence(/\b(?:we measure|measurements|experimentally|measured|synthesized|synthesised)\b/i,true);
    var negative = fields.some(function(f){return f.text.split(/[.!?;]/).some(function(sentence){
      if(f.field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|before|prior)\b/i.test(sentence))return false;
      return /\b(?:no|absence of|not observed|not detected)\s+(?:evidence (?:for|of)\s+)?superconductivity\b|\bsuperconductivity\s+(?:was |is |has been )?(?:not observed|not detected|absent)\b/i.test(sentence);
    });});
    var stage = negative ? 'Negative claim in source; tested conditions matter' :
      /\b(?:predict(?:ed|ion|s)?|propos(?:ed|al))\b/i.test(title) || n.ai_kind === 'prediction' || n.ai_kind === 'generation' ? 'Prediction / theory described; not experimental proof' :
      theoretical ? (measured ? 'Models and measurements mentioned; check their roles in the source' : 'Theory / computation discussed; not experimental proof') :
      measured ? 'Measurements mentioned; consult the source for criteria' : 'Evidence status is not established by this feed';
    var src = n.url || '', ref = n.ref && typeof REFS !== 'undefined' && REFS[n.ref];
    if (!src && ref) src = ref.url || ref.u || (ref.d ? 'https://doi.org/' + ref.d : '');
    if(/^http:\/\/(?:link\.aps\.org|dx\.doi\.org|doi\.org)\//i.test(src)) src=src.replace(/^http:/,'https:');
    if (!src && /^10\.\d+\//.test(n.doi || '')) src = 'https://doi.org/' + n.doi;
    var key = String(n.doi || n.url || n.id || n.ref || title);
    var result = { key: key, title: title, source: String(n.source || n.journal || 'Linked source'), url: src,
      materials: materials.slice(0, 4), namedSubject: named ? named.text : '', layerCount: layerCount, layerCounts: layerValues,
      facts: facts, concepts: concepts, mode: mode, evidence: stage, sparse: !n.summary && !n.abstract && !n.x,
      scope: 'Source-based schematic. Geometry, motion and connections are illustrative; no measured curve or crystal coordinates are reconstructed.' };
    result.signature = JSON.stringify({ materials: result.materials.map(function (m) { return m.text; }), layers: layerValues,
      mode: mode, facts: facts.map(function (f) { return [f.id, f.text.toLowerCase()]; }), concepts: concepts });
    return result;
  };

  const newsArticleDraw = function newsArticleDraw(c, C, W, H, t, info) {
    var k = Math.min(W / 360, H / 170), cx = W / 2, cy = H * .48, ids = info.facts.map(function (f) { return f.id; });
    var has = function (id) { return ids.indexOf(id) >= 0; }, ink = C.ink || '#222', accent = C.accent || '#456';
    function line(x, y, X, Y) { c.beginPath(); c.moveTo(x, y); c.lineTo(X, Y); c.stroke(); }
    function text(s, x, y, max) {
      c.fillStyle = ink; c.font = Math.max(10, 11 * k) + 'px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      var limit = Math.max(8, Math.floor((max || 25) * k)), words = String(s).split(/\s+/), rows = [''];
      words.forEach(function (word) { var last = rows.length - 1, next = rows[last] ? rows[last] + ' ' + word : word;
        if (next.length > limit && rows[last]) rows.push(word); else rows[last] = next; });
      rows.slice(0, 3).forEach(function (row, i) { c.fillText(row.length > limit ? row.slice(0, limit-1) + '…' : row, x, y + i * 13 * k); });
    }
    function box(x, y, w, hh) { c.strokeRect(x, y, w, hh); }
    function circle(x, y, r) { c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.stroke(); }
    function arrow(x, y, X, Y) { line(x, y, X, Y); var a = Math.atan2(Y-y, X-x); line(X,Y,X-5*k*Math.cos(a-.5),Y-5*k*Math.sin(a-.5)); line(X,Y,X-5*k*Math.cos(a+.5),Y-5*k*Math.sin(a+.5)); }
    function documentAt(x, y, w, hh, words) { box(x, y, w, hh); for (var i = 0; i < words; i++) line(x+5*k,y+(7+i*6)*k,x+w-5*k,y+(7+i*6)*k); }
    c.strokeStyle = accent; c.lineWidth = 1.4; c.lineCap = 'round';
    var material = info.materials[0], lx = W * .19, rx = W * .81, sy = cy;
    // Composition tokens are unbonded ingredients, never inferred atom positions.
    if (info.layerCounts.length) {
      info.layerCounts.slice(0,2).forEach(function(count,index){var offset=info.layerCounts.length>1?(index-.5)*38*k:0,width=info.layerCounts.length>1?30:56;
        for (var layer = 0; layer < count; layer++) { var yy = sy - 20*k + layer * Math.min(7, 42/count)*k; box(lx+offset-width/2*k,yy,width*k,4*k); }});
      text(info.layerCounts.join(' / ') + ' layers mentioned', lx, sy+38*k, 20);
    } else if (material) {
      material.components.slice(0, 5).forEach(function (part, i) { var x = lx + (i-(Math.min(5,material.components.length)-1)/2)*20*k;
        circle(x,sy,(7+Math.min(4,Math.log(1+Number(part.count))))*k); text(part.element,x,sy,5); text('×'+part.count,x,sy+18*k,7); });
      text(material.text,lx,sy+38*k,22);
    } else if (info.mode === 'documents' || info.mode === 'question' || info.mode === 'theory') {
      documentAt(lx-20*k,sy-25*k,40*k,48*k,5); text(info.namedSubject || 'Source question',lx,sy+38*k,22);
    } else { box(lx-28*k,sy-17*k,56*k,34*k); text(info.namedSubject || 'System in source',lx,sy+38*k,22); }
    if (has('pressure')) {
      [-1,1].forEach(function (s) { c.beginPath(); c.moveTo(lx-18*k,sy+s*48*k); c.lineTo(lx+18*k,sy+s*48*k); c.lineTo(lx+7*k,sy+s*28*k); c.lineTo(lx-7*k,sy+s*28*k); c.closePath(); c.stroke(); arrow(lx,sy+s*60*k,lx,sy+s*49*k); });
    } else if (has('strain')) {
      var tensile = info.facts.some(function(f){return f.id==='strain' && /tensile/i.test(f.text);});
      if(tensile){arrow(lx-33*k,sy,lx-52*k,sy);arrow(lx+33*k,sy,lx+52*k,sy);}
      else if(info.facts.some(function(f){return f.id==='strain' && /compressive/i.test(f.text);})){arrow(lx-52*k,sy,lx-33*k,sy);arrow(lx+52*k,sy,lx+33*k,sy);}
      else { line(lx-46*k,sy-15*k,lx-46*k,sy+15*k);line(lx+46*k,sy-15*k,lx+46*k,sy+15*k); }
    }
    if (has('doping')) { for (var d=0;d<3;d++) { circle(lx-20*k+d*20*k,sy-36*k,3*k); arrow(lx-20*k+d*20*k,sy-31*k,lx-20*k+d*20*k,sy-22*k); } }
    var pulse = .5+.5*Math.sin(t*1.6);
    // A paper can combine several probes or model ingredients. Render those
    // explicit mentions as different small symbols, not just a primary topic.
    // Their placement is a legend, not a claim that the methods form a causal
    // sequence or were all performed by the present authors.
    var secondary=info.facts.filter(function(f){return ['ambient','pressure','strain','doping','layers'].indexOf(f.id)<0 && f.id!==info.mode && !(info.mode==='theory'&&f.id==='calculation') && !(info.mode==='pairing'&&f.id==='gap') && !(info.mode==='documents'&&f.id==='literature') && !(info.mode==='device'&&f.id==='junction');}).slice(0,4);
    secondary.forEach(function(f,index){var x=cx+(index-(secondary.length-1)/2)*35*k,y=17*k;
      if(f.id==='phonon'){for(var z=0;z<3;z++){circle(x+(z-1)*7*k,y,2*k);if(z<2)line(x+(z-1)*7*k+2*k,y,x+z*7*k-2*k,y);}}
      else if(f.id==='gap'){circle(x-5*k,y,4*k);circle(x+5*k,y,4*k);}
      else if(f.id==='magnetic'){arrow(x,y+8*k,x,y-8*k);}
      else if(f.id==='thermal'){line(x,y-8*k,x,y+3*k);circle(x,y+6*k,3*k);}
      else if(f.id==='spectrum'){box(x-8*k,y-9*k,16*k,18*k);for(var z=0;z<3;z++)line(x-5*k,y+(z-1)*5*k,x+5*k,y+(z-1)*5*k);}
      else if(f.id==='light'){c.beginPath();for(var z=0;z<20;z++){var X=x+(z-10)*k,Y=y+Math.sin(z*.6)*4*k;if(z)c.lineTo(X,Y);else c.moveTo(X,Y);}c.stroke();}
      else if(f.id==='vortex'){circle(x,y,8*k);circle(x,y,3*k);}
      else if(f.id==='transport'||f.id==='four-probe'){box(x-8*k,y-4*k,16*k,8*k);var terminals=f.id==='four-probe'?4:2;for(var z=0;z<terminals;z++)line(x+(-6+12*z/(terminals-1))*k,y-4*k,x+(-6+12*z/(terminals-1))*k,y-9*k);}
      else if(f.id==='network'){circle(x-7*k,y+5*k,2*k);circle(x+7*k,y+5*k,2*k);circle(x,y-6*k,2*k);line(x-7*k,y+5*k,x,y-6*k);line(x+7*k,y+5*k,x,y-6*k);}
      else if(f.id==='generation'){arrow(x-8*k,y,x+7*k,y-6*k);arrow(x-8*k,y,x+7*k,y+6*k);}
      else if(f.id==='boundary'){box(x-9*k,y-8*k,18*k,16*k);box(x-5*k,y-4*k,10*k,8*k);}
      else if(f.id==='correlations'){box(x-10*k,y-5*k,7*k,10*k);box(x+3*k,y-5*k,7*k,10*k);line(x-3*k,y,x+3*k,y);}
      else if(f.id==='junction'){box(x-10*k,y-7*k,6*k,14*k);box(x+4*k,y-7*k,6*k,14*k);line(x-4*k,y,x+4*k,y);}
      else documentAt(x-7*k,y-9*k,14*k,18*k,2);
    });
    if (info.mode === 'generation') {
      box(cx-32*k,cy-18*k,25*k,36*k);
      [-1,0,1].forEach(function (v) { arrow(cx-5*k,cy,cx+17*k,cy+v*25*k); box(cx+19*k,cy+v*25*k-9*k,22*k,18*k); });
      text('Proposals, not samples',cx,cy+48*k,25);
    } else if (info.mode === 'network') {
      var layers = [[-30,[-18,18]],[0,[-28,0,28]],[30,[-12,12]]];
      for(var g=0;g<2;g++) layers[g][1].forEach(function(y){layers[g+1][1].forEach(function(Y){line(cx+layers[g][0]*k,cy+y*k,cx+layers[g+1][0]*k,cy+Y*k);});});
      layers.forEach(function(a,j){a[1].forEach(function(y){circle(cx+a[0]*k,cy+y*k,(4+((Math.floor(t)%3===j)?pulse:0))*k);});});
      text('Learned representation',cx,cy+48*k,26);
    } else if (info.mode === 'documents') {
      documentAt(cx-34*k,cy-27*k,26*k,44*k,4); arrow(cx-5*k,cy,cx+11*k,cy);
      for(var row=0;row<3;row++) box(cx+14*k,cy-23*k+row*16*k,29*k,12*k);
      text('Extract / retrieve',cx,cy+48*k,24);
    } else if (info.mode === 'transport') {
      box(cx-25*k,cy-10*k,50*k,20*k);
      var contacts = has('four-probe') ? [-21,-7,7,21] : [-21,21];
      contacts.forEach(function(x,i){line(cx+x*k,cy-10*k,cx+x*k,cy-(i%2?28:36)*k);circle(cx+x*k,cy-(i%2?29:37)*k,2*k);});
      text(has('four-probe')?'4-terminal method':'Transport quantity',cx,cy+38*k,25);
      text('No measured R(T) trace',cx,cy+54*k,27);
    } else if (info.mode === 'light') {
      c.beginPath();for(var p=0;p<=30;p++){var xx=cx-38*k+p*2*k,yy=cy+Math.sin(p*.45-t*2)*9*k;if(p)c.lineTo(xx,yy);else c.moveTo(xx,yy);}c.stroke();
      line(cx+29*k,cy-26*k,cx+29*k,cy+26*k); text('Incident radiation',cx,cy+43*k,23);
    } else if (info.mode === 'spectrum') {
      box(cx-34*k,cy-22*k,22*k,44*k); arrow(cx-8*k,cy,cx+10*k,cy); box(cx+14*k,cy-29*k,22*k,58*k);
      [0,1,2,3].forEach(function(i){line(cx+18*k,cy+(-21+i*14)*k,cx+32*k,cy+(-21+i*14)*k);});text('Probe → response',cx,cy+45*k,22);
    } else if (info.mode === 'thermal') {
      box(cx-27*k,cy-19*k,42*k,38*k);line(cx+27*k,cy-28*k,cx+27*k,cy+13*k);circle(cx+27*k,cy+20*k,7*k);
      arrow(cx-45*k,cy,cx-30*k,cy);text('Heat / temperature',cx,cy+46*k,24);
    } else if (info.mode === 'magnetic') {
      for(var m=0;m<4;m++) arrow(cx-28*k+m*18*k,cy+23*k,cx-28*k+m*18*k,cy-23*k);
      box(cx-21*k,cy-10*k,42*k,20*k);text('Magnetic response',cx,cy+46*k,24);
    } else if (info.mode === 'device') {
      box(cx-35*k,cy-20*k,22*k,40*k);box(cx+13*k,cy-20*k,22*k,40*k);line(cx-13*k,cy,cx+13*k,cy);text('Device / coupling',cx,cy+46*k,24);
    } else if (info.mode === 'theory') {
      box(cx-31*k,cy-25*k,62*k,50*k);text('Model',cx,cy-10*k,12);text('→ analysis',cx,cy+12*k,15);text('Theoretical relation',cx,cy+46*k,25);
    } else if (info.mode === 'phonon') {
      for(var ion=0;ion<4;ion++){var px=cx+(ion-1.5)*19*k,py=cy+Math.sin(t+ion*.7)*4*k;circle(px,py,5*k);if(ion<3)line(px+5*k,py,px+14*k,cy+Math.sin(t+(ion+1)*.7)*4*k);}
      text('Lattice response',cx,cy+39*k,22);text('Not a measured mode',cx,cy+54*k,25);
    } else if (info.mode === 'vortex') {
      [12,24].forEach(function(r){c.beginPath();c.arc(cx,cy,r*k,.3+t*.2,5.4+t*.2);c.stroke();});line(cx,cy-32*k,cx,cy+32*k);
      text('Flux / vortex question',cx,cy+46*k,26);
    } else if (info.mode === 'pressure' || info.mode === 'strain' || info.mode === 'carrier') {
      var branches=info.mode==='carrier'?3:2;
      for(var b=0;b<branches;b++){var yy=cy+(b-(branches-1)/2)*26*k;box(cx+4*k,yy-9*k,33*k,18*k);arrow(cx-28*k,cy,cx+1*k,yy);}
      text(info.mode==='carrier'?'Carrier control':info.mode==='pressure'?'Pressure conditions':'Strain conditions',cx,cy+46*k,25);
    } else if (info.mode === 'layers') {
      info.layerCounts.slice(0,2).forEach(function(count,index){var offset=info.layerCounts.length>1?(index-.5)*34*k:0,width=info.layerCounts.length>1?26:58;
        for(var l=0;l<count;l++){var yy=cy+(l-(count-1)/2)*Math.min(8,45/Math.max(1,count))*k;box(cx+offset-width/2*k,yy,width*k,3*k);}});
      text('Layer-dependent question',cx,cy+46*k,28);
    } else if (info.mode === 'correlations') {
      box(cx-39*k,cy-17*k,28*k,34*k);box(cx+11*k,cy-17*k,28*k,34*k);
      arrow(cx-7*k,cy-7*k,cx+7*k,cy-7*k);arrow(cx+7*k,cy+7*k,cx-7*k,cy+7*k);
      text('Interacting orders',cx,cy+46*k,23);
    } else if (info.mode === 'pairing') {
      circle(cx-20*k,cy,12*k);circle(cx+20*k,cy,12*k);c.setLineDash([3*k,3*k]);line(cx-8*k,cy,cx+8*k,cy);c.setLineDash([]);
      text('Pairing / gap question',cx,cy+39*k,25);text('Mechanism not asserted',cx,cy+54*k,26);
    } else if (info.mode === 'boundary') {
      box(cx-31*k,cy-24*k,62*k,48*k);box(cx-22*k,cy-15*k,44*k,30*k);c.setLineDash([3*k,3*k]);line(cx-31*k,cy-24*k,cx+31*k,cy-24*k);c.setLineDash([]);
      text('Bulk / boundary question',cx,cy+46*k,29);
    } else {
      var steps = Math.min(4, info.concepts.length);
      for(var s=0;s<steps;s++) {var yy=cy+(s-(steps-1)/2)*18*k;box(cx-31*k,yy-7*k,62*k,14*k);if(s<steps-1)arrow(cx,yy+7*k,cx,yy+11*k);}
      text('Question / concepts',cx,cy+46*k,25);
    }
    // The target box names the paper's scientific question, not a made-up result.
    var target = info.concepts.length > 1 ? info.concepts[info.concepts.length-1] : info.concepts[0];
    box(rx-49*k,cy-31*k,98*k,62*k);text(target,rx,cy-14*k,20);
    c.globalAlpha=.55;arrow(lx+54*k,cy,cx-48*k,cy);arrow(cx+48*k,cy,rx-54*k,cy);c.globalAlpha=1;
    // The moving dot is a reading guide through the diagram, not a charge or
    // a measured time evolution. Reduced-motion rendering fixes t upstream.
    var guide=(t%4)/4;c.fillStyle=accent;c.beginPath();c.arc(lx+54*k+(cx-lx-102*k)*guide,cy,2*k,0,Math.PI*2);c.fill();
    c.font=Math.max(10,10*k)+'px sans-serif';c.fillStyle=C.ink2||ink;c.textAlign='left';
    var controls=info.facts.filter(function(f){return ['ambient','pressure','strain','doping','layers'].indexOf(f.id)>=0;}).map(function(f){return f.text;});
    c.fillText((controls.length?controls.join(' · '):'Concepts, not measured data').slice(0,55),8,H-10);
  };

  const newsArticleFigure = function newsArticleFigure(item) {
    var info = newsArticleDescribe(item), art = item.ai_kind && typeof aiArticleArt === 'function' ? aiArticleArt(item) : newsArt(item), drawing = miniCanvas(art, item);
    var figure = h('figure', { class: 'article-figure', 'data-article-key': info.key, 'data-article-mode': info.mode }, drawing);
    var caption = h('figcaption', null, h('span', { text: 'Source-based schematic · ' + info.evidence }));
    if (isHttps(info.url)) caption.appendChild(h('a', { href: info.url, text: 'Original source' }));
    var details = h('details', { class: 'article-figure-evidence' }, h('summary', { text: 'What this drawing uses' }), h('p', { text: info.scope }));
    details.appendChild(h('p', { text: 'Question: ' + info.concepts.join(' → ') }));
    if (info.materials.length) details.appendChild(h('p', { text: 'Composition text: ' + info.materials.map(function(m){return m.text;}).join(', ') + '. Symbols show composition, not atomic coordinates.' }));
    info.facts.forEach(function(f){details.appendChild(h('p',{text:f.label+': '+f.text+' ('+f.field+').'}));});
    if (info.sparse) details.appendChild(h('p', { text: 'Only the available title is used. Methods, outcomes and material structure are not independently verified here.' }));
    // Keep the original topic animations available with their original limits.
    // Article-specific construction is the primary graphic above.
    var kind = newsArt(item), alt = typeof MINI_ALT !== 'undefined' ? MINI_ALT[kind] : '';
    if (alt && kind !== 'news-research') details.appendChild(h('div', { class: 'article-topic-concept' }, miniCanvas(kind), h('p', { text: 'Related concept illustration: ' + alt })));
    caption.appendChild(details); figure.appendChild(caption); return figure;
  };

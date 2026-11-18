// test-offline.cjs — DOM-stub smoke test for the GENERATED offline index.html
'use strict';
const fs = require('fs');

function makeEl(id){
  return {
    id, innerHTML:'', textContent:'', className:'', title:'', href:'', tabIndex:0, disabled:false, value:'', hidden:false,
    style:{ setProperty(){}, cssText:'', opacity:'', overflow:'' },
    dataset:{}, files:[],
    classList:{ add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    addEventListener(){}, appendChild(){}, remove(){}, scrollIntoView(){}, click(){}, focus(){},
    setAttribute(){}, getAttribute(){ return null; },
    querySelector(){ return makeEl(id + '-q'); },
    querySelectorAll(){ return []; },
  };
}
const elCache = {};
const documentStub = {
  querySelector(sel){ if (!elCache[sel]) elCache[sel] = makeEl(sel); return elCache[sel]; },
  getElementById(id){ return documentStub.querySelector('#' + id); },
  createElement(){ return makeEl('dyn-' + Math.random().toString(36).slice(2, 8)); },
  querySelectorAll(sel){
    if (sel === '#docTabs .tab') return [makeEl('tab1'), makeEl('tab2'), makeEl('tab3'), makeEl('tab4')];
    return [];
  },
  addEventListener(){},
  documentElement:{ setAttribute(){}, getAttribute(){ return 'dark'; } },
  body:{ style:{} },
};
global.window = global;
global.document = documentStub;
global.localStorage = { getItem(){ return null; }, setItem(){} };
global.location = { search:'', protocol:'http:', href:'' };
global.matchMedia = () => ({ matches:false, addEventListener(){} });
global.performance = { now: () => Date.now() };
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
global.addEventListener = () => {};

const html = fs.readFileSync('index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length < 2){ console.error('expected 2 script blocks, got', scripts.length); process.exit(1); }

let code = scripts.join('\n;\n') + `
;(async () => {
  try {
    await new Promise(r => setTimeout(r, 200));
    if (!CATALOG || !CATALOG.papers || !CATALOG.papers.length) throw new Error('no catalog');
    console.log('catalog:', CATALOG.count, 'present:', CATALOG.presentCount);
    const subjCount = new Set(PRESENT.map(x => x.s)).size;
    if (subjects.filter(s => s.present > 0).length !== subjCount)
      throw new Error('subject index mismatch');
    console.log('subjects with files:', subjCount);

    selectSubject('Mathematics');
    if (!subjects.find(s => s.name === 'Mathematics').units.find(u => u.code === 'WMA11'))
      throw new Error('WMA11 unit missing');
    selectUnit('WMA11');
    console.log('unit WMA11 sessions:', unitSessions(S.unit).length, 'latest:', S.session);

    const qps = currentPapers().filter(x => x.p);
    if (!qps.length) throw new Error('no present papers for latest WMA11 session');
    console.log('present papers (latest session):', qps.length);

    // single view
    const qp = currentPapers().find(x => x.t === 'QP' && x.p);
    const ms = currentPapers().find(x => x.t === 'MS' && x.p);
    if (qp) openViewer(qp);
    closeViewer();
    // side-by-side: prefer a real QP+MS pair, else any two present entries
    if (qp && ms){ openSplit(qp, ms); closeViewer(); console.log('split view (real QP+MS pair) OK'); }
    else {
      const any2 = PRESENT.slice(0, 2);
      if (any2.length === 2){ openSplit(any2[0], any2[1]); closeViewer(); console.log('split view (2 frames + divider) OK'); }
      else console.log('split view skipped (no pairs available)');
    }

    // all-sessions mode
    S.session = 'all'; renderSessions(); renderResults();
    console.log('all-mode papers:', currentPapers().length);

    // missing toggle
    S.showMissing = true; renderSubjects(); renderUnits(); renderSessions(); renderResults();
    console.log('missing-toggle OK (visible pool:', visiblePool().length + ')');

    console.log('OFFLINE SMOKE OK');
    process.exit(0);
  } catch(e){
    console.error('OFFLINE SMOKE FAIL:', e && e.stack || e);
    process.exit(1);
  }
})();`;

try { eval(code); } catch(e){ console.error('EVAL FAIL:', e); process.exit(1); }

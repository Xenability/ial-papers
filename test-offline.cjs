// test-offline.cjs — DOM-stub smoke test for the GENERATED offline index.html
'use strict';
const fs = require('fs');

function makeEl(id){
  return {
    id, innerHTML:'', textContent:'', className:'', title:'', href:'', tabIndex:0, disabled:false, value:'', hidden:false,
    style:{ setProperty(){}, cssText:'', opacity:'', overflow:'' },
    dataset:{}, files:[],
    classList:{ add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    addEventListener(){}, appendChild(){}, remove(){}, scrollIntoView(){}, click(){}, focus(){}, blur(){}, select(){},
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
    if (sel === '.links a') return [];
    if (sel === '.reveal') return [];
    return [];
  },
  addEventListener(){},
  documentElement:{ setAttribute(){}, getAttribute(){ return 'dark'; }, dataset:{}, classList:{toggle(){}} },
  body:{ style:{} },
  activeElement: null,
};
global.window = global;
global.document = documentStub;
global.localStorage = { getItem(){ return null; }, setItem(){} };
global.location = { search:'', protocol:'https:', href:'https://xenability.github.io/ial-papers/', pathname:'/ial-papers/index.html' };
global.matchMedia = () => ({ matches:false, addEventListener(){} });
global.performance = { now: () => Date.now() };
global.requestAnimationFrame = fn => setTimeout(() => fn(Date.now()), 16);
global.addEventListener = () => {};
global.scrollY = 0;
global.scrollTo = () => {};
global.open = () => {};
global.history = { replaceState(){} };
global.IntersectionObserver = class {
  constructor(cb){ this.cb = cb; }
  observe(){ }  // don't fire callbacks at boot
  unobserve(){ }
};

const html = fs.readFileSync('index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (!scripts.length){ console.error('no script found'); process.exit(1); }

let code = scripts.join('\n;\n') + `
;(async () => {
  try {
    await new Promise(r => setTimeout(r, 200));
    if (!CATALOG || !CATALOG.papers || !CATALOG.papers.length) throw new Error('no catalog');
    console.log('catalog:', CATALOG.count, 'present:', CATALOG.presentCount);
    const subjCount = new Set(PRESENT.map(x => x.s)).size;
    if (subjects.filter(s => s.present > 0).length !== subjCount) throw new Error('subject index mismatch');
    console.log('subjects with files:', subjCount);
    if (!ALL.length) throw new Error('ALL empty');

    selectSubject('Mathematics');
    if (!subjects.find(s => s.name === 'Mathematics').units.find(u => u.code === 'WMA11'))
      throw new Error('WMA11 unit missing');
    selectUnit('WMA11');
    console.log('unit WMA11 sessions:', unitSessions(S.unit).length, 'latest:', S.session);

    const qps = papersFor().filter(x => x.p);
    if (!qps.length) throw new Error('no present papers for latest WMA11 session');
    console.log('present papers (latest session):', qps.length);

    // single view
    const qp = papersFor().find(x => x.t === 'QP' && x.p);
    const ms = papersFor().find(x => x.t === 'MS' && x.p);
    if (qp) openViewer(qp);
    closeViewer();
    // side-by-side (new API: openViewer(qp, ms))
    if (qp && ms){ openViewer(qp, ms); closeViewer(); console.log('split view (real QP+MS pair) OK'); }
    else { console.log('split view skipped (no pair)'); }

    // all-sessions mode
    S.session = 'all'; renderSessions(); renderResults();
    console.log('all-mode papers:', papersFor().length);

    // missing toggle
    showMissing = true; refresh();
    console.log('missing-toggle OK (pool:', pool().length + ')');
    showMissing = false; refresh();

    // legacy/current merge check (Chemistry Unit 1 = WCH01 + WCH11)
    selectSubject('Chemistry');
    const chemUnits = subjects.find(s => s.name === 'Chemistry').units;
    console.log('Chemistry units (expect 6 merged):', chemUnits.length);
    const u1 = chemUnits.find(u => u.label === 'Unit 1');
    if (!u1 || !u1.codes.has('WCH01') || !u1.codes.has('WCH11'))
      throw new Error('Unit 1 merge failed: ' + JSON.stringify(u1 ? [...u1.codes] : null));
    selectUnit('WCH01');  // select via the legacy code
    const ss = unitSessions(S.unit);
    console.log('merged Unit 1 sessions:', ss.length, 'oldest', ss[ss.length-1], 'newest', ss[0]);
    if (!ss.includes('2026-01')) throw new Error('merged unit missing 2026 session');

    // zip writer sanity (store-only)
    const zbuf = new Uint8Array(await makeZip([{name:'a.txt', data:new TextEncoder().encode('hello world')}]).arrayBuffer());
    if (zbuf[0] !== 0x50 || zbuf[1] !== 0x4b) throw new Error('zip header invalid');
    console.log('zip writer OK (', zbuf.length, 'bytes)');

    // mobile PDF card sanity
    const pc = pdfCard(qp);
    if (!pc || !String(pc.innerHTML).includes('Open PDF')) throw new Error('pdfCard broken');
    console.log('mobile pdfCard OK');

    // mobile google-viewer path sanity
    if (!gview(qp).includes('docs.google.com')) throw new Error('gview failed');
    if (!absoluteUrl(qp.f).startsWith('https://xenability.github.io/ial-papers/papers/')) throw new Error('absoluteUrl failed: ' + absoluteUrl(qp.f));
    console.log('mobile google-viewer path OK');

    // search index sanity
    if (!UNIT_INDEX || !UNIT_INDEX.length) throw new Error('UNIT_INDEX empty');
    console.log('search index entries:', UNIT_INDEX.length);

    console.log('OFFLINE SMOKE OK');
    process.exit(0);
  } catch(e){
    console.error('OFFLINE SMOKE FAIL:', e && e.stack || e);
    process.exit(1);
  }
})();`;

try { eval(code); } catch(e){ console.error('EVAL FAIL:', e); process.exit(1); }

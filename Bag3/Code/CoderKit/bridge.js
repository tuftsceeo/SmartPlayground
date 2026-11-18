/**
 * Runs a front end in a sandboxed frame (no same-origin) and gives it a
 * window.kit that talks to the real kit in this page by postMessage.
 */
export const SHIM = `<script>(function(){
  var state = {log:[],link:'idle',messages:[],code:{},choices:[],busy:false,progress:null,error:null,gameName:null,deviceName:null};
  var fns = new Set(), calls = {}, seq = 0;
  function call(name, args){ return new Promise(function(res){ var id=++seq; calls[id]=res; parent.postMessage({kit:'call',id:id,name:name,args:args||[]},'*'); }); }
  addEventListener('message', function(e){
    var d = e.data; if (!d || !d.kit || e.source !== parent) return;
    if (d.kit === 'state') { kit.state = state = d.state; fns.forEach(function(f){ try{f(state)}catch(err){console.error(err)} }); }
    if (d.kit === 'result' && calls[d.id]) { calls[d.id](d.value); delete calls[d.id]; }
  });
  window.kit = {
    get state(){ return state; }, set state(v){ state = v; },
    on: function(t,f){ if(t==='change'){ fns.add(f); return function(){fns.delete(f)}; } },
    chat: function(t){ return call('chat',[t]); },
    connect: function(){ return call('connect'); },
    reconnect: function(){ return call('reconnect'); },
    disconnect: function(){ return call('disconnect'); },
    send: function(){ return call('send'); },
    reset: function(){ return call('reset'); },
    setGameName: function(n){ return call('setGameName',[n]); },
    setCode: function(r,c){ return call('setCode',[r,c]); },
    log: function(t,l){ return call('log',[t,l]); },
    newGame: function(){ return call('newGame'); },
    prevVersion: function(r){ return call('prevVersion',[r]); }, nextVersion: function(r){ return call('nextVersion',[r]); },
    startInterview: function(){ return call('startInterview'); }, answer: function(t){ return call('answer',[t]); },
    finishInterview: function(){ return call('finishInterview'); }, makeFromBrief: function(){ return call('makeFromBrief'); },
    cancelInterview: function(){ return call('cancelInterview'); },
    openExample: function(i){ return call('openExample',[i]); }, remixExample: function(i){ return call('remixExample',[i]); },
    saveGame: function(n){ return call('saveGame',[n]); }, openSaved: function(i){ return call('openSaved',[i]); },
    renameSaved: function(i,n){ return call('renameSaved',[i,n]); }, deleteSaved: function(i){ return call('deleteSaved',[i]); },
    refreshGames: function(){ return call('refreshGames'); }, selectGame: function(s){ return call('selectGame',[s]); },
    deleteGame: function(s){ return call('deleteGame',[s]); }, fixSimError: function(){ return call('fixSimError'); },
    clearLog: function(){ return call('clearLog'); },
    hasSerial: true, ready: Promise.resolve(),
    // The simulator can't run inside this frame: report where its slot is,
    // and the runner draws the real one on top of it.
    mountSimulator: function(el){
      function report(){ var r = el.getBoundingClientRect(); var vis = el.offsetParent !== null && r.width > 0 && r.height > 0;
        parent.postMessage({kit:'sim-slot', rect: vis ? {x:r.left,y:r.top,w:r.width,h:r.height} : null}, '*'); }
      if (window.ResizeObserver) new ResizeObserver(report).observe(el);
      addEventListener('scroll', report, true); addEventListener('resize', report);
      setInterval(report, 500); report();
      return {};
    },
    get roles(){ return state.rolesList || []; },
    examples: function(){ return state.examplesList || {categories:[],list:[]}; },
    saved: function(){ return state.savedList || []; },
    distribute: { open: function(s){ return call('distribute.open',[s]); }, scan: function(){ return call('distribute.scan'); },
      toggle: function(m,o,v){ return call('distribute.toggle',[m,o,v]); }, send: function(s){ return call('distribute.send',[s]); },
      find: function(m){ return call('distribute.find',[m]); }, close: function(){ return call('distribute.close'); } }
  };
  parent.postMessage({kit:'hello'},'*');
})();<\/script>`;

const METHODS = new Set(['chat', 'connect', 'reconnect', 'disconnect', 'send', 'reset', 'setGameName', 'setCode', 'log', 'clearLog',
    'newGame', 'prevVersion', 'nextVersion', 'startInterview', 'answer', 'finishInterview', 'makeFromBrief', 'cancelInterview',
    'openExample', 'remixExample', 'saveGame', 'openSaved', 'renameSaved', 'deleteSaved', 'refreshGames', 'selectGame',
    'deleteGame', 'fixSimError', 'distribute.open', 'distribute.scan', 'distribute.toggle', 'distribute.send',
    'distribute.find', 'distribute.close']);

/** Put the shim first in the head so the design's scripts find window.kit. */
export function withShim(html) {
    // The design's own kit script is for artifacts; here the shim is the kit.
    html = html.replace(/<script[^>]*src=["'][^"']*coderkit\.js["'][^>]*>\s*<\/script>/gi, '');
    if (/<head[^>]*>/i.test(html)) return html.replace(/<head[^>]*>/i, m => m + SHIM);
    return SHIM + html;
}

/** Wire `frame` (an iframe) to `kit`. Returns a function that loads a design. */
export function hostFrontEnd(frame, kit, { simLayer = null } = {}) {
    frame.setAttribute('sandbox', 'allow-scripts allow-forms allow-modals');
    const post = (msg) => frame.contentWindow?.postMessage(msg, '*');
    // Lists the design reads synchronously ride along with the state.
    const plain = () => JSON.parse(JSON.stringify({ ...kit.state, examplesList: kit.examples(), rolesList: kit.roles, savedList: kit.saved() }));
    let simMounted = false;
    const placeSim = (rect) => {
        if (!simLayer) return;
        if (!rect) { simLayer.style.display = 'none'; return; }
        const f = frame.getBoundingClientRect();
        Object.assign(simLayer.style, { display: 'block', left: `${f.left + rect.x}px`, top: `${f.top + rect.y}px`, width: `${rect.w}px`, height: `${rect.h}px` });
        if (!simMounted) { simMounted = true; kit.mountSimulator(simLayer); }
    };
    kit.on('change', () => post({ kit: 'state', state: plain() }));
    addEventListener('message', async (e) => {
        if (e.source !== frame.contentWindow || !e.data?.kit) return;
        const d = e.data;
        if (d.kit === 'hello') return post({ kit: 'state', state: plain() });
        if (d.kit === 'sim-slot') return placeSim(d.rect);
        if (d.kit !== 'call' || !METHODS.has(d.name)) return;
        let value = null;
        const [obj, fn] = d.name.includes('.') ? [kit[d.name.split('.')[0]], d.name.split('.')[1]] : [kit, d.name];
        try { value = await obj[fn](...(d.args || [])); } catch (err) { value = { ok: false, error: err.message }; }
        post({ kit: 'result', id: d.id, value: JSON.parse(JSON.stringify(value ?? null)) });
    });
    return (html) => { if (simLayer) simLayer.style.display = 'none'; frame.srcdoc = withShim(html); };
}

/** Compress a design into a URL-safe string for #f= links. */
export async function packDesign(html) {
    const s = new Blob([html]).stream().pipeThrough(new CompressionStream('deflate-raw'));
    const b = new Uint8Array(await new Response(s).arrayBuffer());
    let bin = ''; for (const x of b) bin += String.fromCharCode(x);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
export async function unpackDesign(str) {
    const bin = atob(str.replace(/-/g, '+').replace(/_/g, '/'));
    const b = Uint8Array.from(bin, c => c.charCodeAt(0));
    const s = new Blob([b]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Response(s).text();
}

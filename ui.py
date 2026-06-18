"""
VIVARIUM - UI minimale : la page humaine de l'organisme

Page HTML autonome (CSS + JS inline, aucune dependance externe / CDN) servie par
le meme FastAPI. On y decrit une intention, l'organisme fabrique, on voit le
verdict + le code, et le catalogue des produits deja fabriques.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VIVARIUM</title>
<style>
  :root { --bg:#0a0e14; --panel:#121821; --line:#1f2a3a; --txt:#e6edf3; --mut:#8b98a9;
          --acc:#4fd1c5; --ok:#3fb950; --ko:#f85149; --warn:#d29922; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:15px/1.5 ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif; }
  header { padding:22px 28px; border-bottom:1px solid var(--line); }
  header h1 { margin:0; font-size:22px; letter-spacing:3px; }
  header h1 b { color:var(--acc); }
  header p { margin:4px 0 0; color:var(--mut); font-size:13px; }
  main { max-width:980px; margin:0 auto; padding:24px 28px; display:grid;
         grid-template-columns:1fr; gap:24px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px; }
  textarea { width:100%; min-height:90px; resize:vertical; background:#0d131c; color:var(--txt);
             border:1px solid var(--line); border-radius:8px; padding:12px; font-size:15px; }
  .row { display:flex; align-items:center; gap:14px; margin-top:12px; }
  .row label { color:var(--mut); font-size:13px; }
  .row input[type=number] { width:56px; background:#0d131c; color:var(--txt);
             border:1px solid var(--line); border-radius:6px; padding:6px; }
  .row.caps { flex-wrap:wrap; gap:10px 18px; }
  .capslabel { color:var(--mut); font-size:13px; }
  .row.caps label { color:var(--txt); display:flex; align-items:center; gap:6px; cursor:pointer; }
  .hint { color:var(--mut); font-size:12px; }
  #domaines { width:100%; margin-top:10px; background:#0d131c; color:var(--txt);
             border:1px solid var(--line); border-radius:6px; padding:9px; font-size:14px; }
  button { background:var(--acc); color:#06231f; border:0; border-radius:8px; padding:10px 20px;
           font-weight:700; cursor:pointer; font-size:15px; }
  button:disabled { opacity:.5; cursor:wait; }
  button.ghost { background:transparent; color:var(--acc); border:1px solid var(--acc); }
  #proposition { margin-top:14px; padding:14px; border:1px solid var(--acc); border-radius:8px;
             background:rgba(79,209,197,.06); font-size:14px; }
  #proposition h3 { margin:0 0 8px; font-size:14px; color:var(--acc); letter-spacing:.5px; }
  #proposition .ligne { margin:4px 0; }
  #proposition .reform { margin-top:8px; color:var(--warn); }
  #proposition .murs { margin-top:8px; color:var(--mut); font-size:13px; }
  #status { margin-top:14px; font-size:14px; }
  .tag { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:700; }
  .tag.ok { background:rgba(63,185,80,.15); color:var(--ok); }
  .tag.ko { background:rgba(248,81,73,.15); color:var(--ko); }
  .meta { color:var(--mut); font-size:13px; margin-top:6px; }
  .lecons { color:var(--warn); font-size:13px; margin-top:6px; white-space:pre-wrap; }
  pre.code { background:#0d131c; border:1px solid var(--line); border-radius:8px; padding:14px;
             overflow:auto; max-height:420px; font:13px/1.45 ui-monospace,Consolas,monospace;
             color:#c9d6e3; margin-top:14px; }
  h2 { font-size:15px; margin:0 0 12px; color:var(--mut); font-weight:600; letter-spacing:.5px; }
  h2 span { color:var(--acc); }
  ul { list-style:none; margin:0; padding:0; }
  li { padding:10px 12px; border:1px solid var(--line); border-radius:8px; margin-bottom:8px;
       cursor:pointer; transition:border-color .15s; }
  li:hover { border-color:var(--acc); }
  li .t { font-size:14px; }
  li .s { color:var(--mut); font-size:12px; margin-top:2px; }
  .hidden { display:none; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .dot.on { background:var(--ok); } .dot.off { background:var(--ko); }
</style>
</head>
<body>
<header>
  <h1>VIVA<b>RIUM</b></h1>
  <p>Une intention parlee devient une application gouvernee, generee et executee en conteneur durci. <span id="docker"></span></p>
</header>
<main>
  <section class="panel">
    <textarea id="intention" placeholder="Decris ce que tu veux fabriquer, en une phrase. Ex : un convertisseur de temperature celsius/fahrenheit"></textarea>
    <div class="row caps">
      <span class="capslabel">Capacites accordees :</span>
      <label><input type="checkbox" id="persistance"> persistance <span class="hint">(disque isole)</span></label>
      <label><input type="checkbox" id="reseau"> reseau <span class="hint">(liste blanche)</span></label>
    </div>
    <input type="text" id="domaines" class="hidden" placeholder="domaines autorises, separes par des virgules (ex: api.stripe.com)">
    <div class="row">
      <label>tentatives <input type="number" id="max" value="2" min="1" max="5"></label>
      <label><input type="checkbox" id="juger"> mode juge <span class="hint">(2 strategies, garde la meilleure)</span></label>
      <button id="analyser" class="ghost">Analyser</button>
      <button id="go">Fabriquer</button>
    </div>
    <div id="proposition" class="hidden"></div>
    <div id="status"></div>
    <pre id="code" class="code hidden"></pre>
  </section>
  <section class="panel">
    <h2>Catalogue <span id="count"></span></h2>
    <ul id="produits"></ul>
  </section>
</main>
<script>
const $ = s => document.querySelector(s);

async function health() {
  try {
    const h = await (await fetch('/health')).json();
    $('#docker').innerHTML = '<span class="dot ' + (h.docker?'on':'off') + '"></span>' +
      (h.docker ? 'Docker actif (' + h.docker_info + ')' : 'Docker indisponible');
  } catch(e) { $('#docker').textContent = ''; }
}

async function showCode(id) {
  const d = await (await fetch('/produits/' + encodeURIComponent(id))).json();
  $('#code').textContent = d.code || '';
  $('#code').classList.remove('hidden');
  $('#code').scrollIntoView({behavior:'smooth', block:'nearest'});
}

async function loadProduits() {
  const d = await (await fetch('/produits')).json();
  const list = d.produits || [];
  $('#count').textContent = '(' + list.length + ')';
  const ul = $('#produits'); ul.innerHTML = '';
  list.slice().reverse().forEach(p => {
    const li = document.createElement('li');
    li.innerHTML = '<div class="t">' + p.intention.replace(/[<>]/g,'') +
                   (p.promouvable ? ' <span class="tag ok">appli</span>' : '') + '</div>' +
                   '<div class="s">' + p.lignes + ' lignes | ' + p.verdict + '</div>';
    li.onclick = () => showCode(p.id);
    if (p.promouvable) {
      const b = document.createElement('button'); b.className = 'ghost';
      b.textContent = "Produire l'appli"; b.style.marginTop = '8px';
      b.onclick = async (e) => {
        e.stopPropagation(); b.disabled = true; b.textContent = 'Promotion...';
        try {
          const r = await (await fetch('/produits/' + encodeURIComponent(p.id) + '/promouvoir', {method:'POST'})).json();
          if (r.app) window.open(r.app, '_blank');
        } catch(err) { alert(err); }
        finally { b.disabled = false; b.textContent = "Ouvrir l'appli"; }
      };
      li.appendChild(b);
    }
    ul.appendChild(li);
  });
}

$('#reseau').onchange = () => {
  $('#domaines').classList.toggle('hidden', !$('#reseau').checked);
};

const esc = s => (s || '').replace(/[<>]/g, '');

$('#analyser').onclick = async () => {
  const intention = $('#intention').value.trim();
  if (intention.length < 3) { $('#status').innerHTML = '<span class="tag ko">vide</span> ecris une intention.'; return; }
  $('#analyser').disabled = true;
  $('#proposition').classList.add('hidden');
  $('#status').innerHTML = 'L\'organisme analyse l\'intention et propose un ADN...';
  try {
    const p = await (await fetch('/proposer', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({intention})
    })).json();
    const d = p.discernement || {};
    // pre-cocher les capacites proposees par l'organisme
    $('#persistance').checked = !!p.persistance;
    $('#reseau').checked = !!p.reseau;
    $('#domaines').value = (p.domaines_proposes || []).join(', ');
    $('#domaines').classList.toggle('hidden', !p.reseau);
    let html = '<h3>Proposition de l\'organisme</h3>';
    html += '<div class="ligne">Discernement : ' + (d.merite_attaque ? 'merite qu\'on s\'y attaque' : 'a recadrer') +
            ' (valeur ' + d.valeur + ', faisabilite ' + d.faisabilite + ', clarte ' + d.clarte + ')</div>';
    html += '<div class="ligne">' + esc(d.raison) + '</div>';
    if (d.reformulation) html += '<div class="reform">Reformulation suggeree : ' + esc(d.reformulation) + '</div>';
    const caps = (p.persistance ? 'persistance ' : '') + (p.reseau ? 'reseau ' : '');
    html += '<div class="ligne">Capacites proposees : ' + (caps.trim() || 'aucune (produit pur)') + '</div>';
    if (p.murs_proposes && p.murs_proposes.length) html += '<div class="murs">Murs proposes : ' + p.murs_proposes.map(esc).join(', ') + '</div>';
    html += '<div class="ligne" style="margin-top:8px;color:var(--mut)">Ajuste les capacites ci-dessus si besoin, puis Fabriquer.</div>';
    $('#proposition').innerHTML = html;
    $('#proposition').classList.remove('hidden');
    $('#status').innerHTML = '';
  } catch(e) {
    $('#status').innerHTML = '<span class="tag ko">erreur</span> ' + e;
  } finally { $('#analyser').disabled = false; }
};

$('#go').onclick = async () => {
  const intention = $('#intention').value.trim();
  if (intention.length < 3) { $('#status').innerHTML = '<span class="tag ko">vide</span> ecris une intention.'; return; }
  const max = parseInt($('#max').value) || 2;
  const persistance = $('#persistance').checked;
  const reseau = $('#reseau').checked;
  const juger = $('#juger').checked;
  const domaines = $('#domaines').value.split(',').map(s => s.trim()).filter(Boolean);
  $('#go').disabled = true;
  $('#code').classList.add('hidden');
  $('#status').innerHTML = 'L\'organisme travaille : forge de l\'ADN, generation, 3 garde-fous, execution en conteneur...';
  try {
    const r = await fetch('/fabriquer', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({intention, max_tentatives:max, juger, persistance, reseau, domaines_autorises:domaines})
    });
    const d = await r.json();
    if (r.status !== 200) { $('#status').innerHTML = '<span class="tag ko">erreur</span> ' + (d.detail||''); }
    else {
      const tag = d.succes ? '<span class="tag ok">execute</span>' : '<span class="tag ko">echec</span>';
      let html = tag + ' ' + d.verdict;
      html += '<div class="meta">' + d.tentatives + ' tentative(s) | ' + d.lignes + ' lignes' +
              (d.produit_id ? ' | enregistre' : '') + '</div>';
      if (d.capacites) html += '<div class="meta">capacites : ' + d.capacites + '</div>';
      if (d.classement && d.classement.length) html += '<div class="meta">strategies jugees : ' +
        d.classement.map(c => c[0] + ' ' + c[1]).join(' | ') + ' (la meilleure est retenue)</div>';
      if (d.lecons && d.lecons.length) html += '<div class="lecons">' + d.lecons.join('\n') + '</div>';
      $('#status').innerHTML = html;
      await loadProduits();
      if (d.produit_id) showCode(d.produit_id);
    }
  } catch(e) {
    $('#status').innerHTML = '<span class="tag ko">erreur</span> ' + e;
  } finally { $('#go').disabled = false; }
};

health();
loadProduits();
</script>
</body>
</html>
"""

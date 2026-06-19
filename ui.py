"""
VIVARIUM - UI : glassmorphism 3D sur fond blanc anime

Landing : 6 couches de verre transparentes en perspective 3D inclinee.
Fond blanc avec 5 blobs de couleur en derive lente (effet onde/aurora).
Glassmorphism : backdrop-filter + white glass + bordures iridescentes.
Sections : Creation (live), Production (live), 4 placeholders.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-19.
"""

PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VIVARIUM</title>
<style>
:root {
  --txt:#0f172a; --mut:#64748b; --line:rgba(15,23,42,.08);
  --acc:#0891b2; --ok:#16a34a; --ko:#dc2626; --warn:#d97706;
  --c-creation:#0891b2; --c-production:#16a34a; --c-compte:#7c3aed;
  --c-analyse:#2563eb; --c-integration:#ea580c; --c-don:#db2777;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#fff;color:var(--txt);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;min-height:100vh;overflow-x:hidden;}

/* ===== FOND ANIME ===== */
.bg{position:fixed;inset:0;z-index:0;background:#ffffff;overflow:hidden;pointer-events:none;}
.blob{position:absolute;border-radius:50%;filter:blur(110px);}
.b1{width:680px;height:680px;background:radial-gradient(circle,rgba(168,85,247,.22),rgba(139,92,246,.1));top:-220px;right:-80px;animation:b1 24s ease-in-out infinite;}
.b2{width:580px;height:580px;background:radial-gradient(circle,rgba(6,182,212,.2),rgba(20,184,166,.1));top:35%;left:-180px;animation:b2 19s ease-in-out infinite;}
.b3{width:540px;height:540px;background:radial-gradient(circle,rgba(34,197,94,.18),rgba(16,185,129,.09));bottom:-160px;left:28%;animation:b3 22s ease-in-out infinite;}
.b4{width:440px;height:440px;background:radial-gradient(circle,rgba(251,113,133,.18),rgba(244,63,94,.08));top:8%;left:8%;animation:b4 28s ease-in-out infinite;}
.b5{width:400px;height:400px;background:radial-gradient(circle,rgba(251,191,36,.15),rgba(245,158,11,.07));bottom:15%;right:-60px;animation:b5 26s ease-in-out infinite;}
@keyframes b1{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(-80px,60px) scale(1.1)}}
@keyframes b2{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(70px,-50px) scale(1.08)}66%{transform:translate(-40px,60px) scale(.94)}}
@keyframes b3{0%,100%{transform:translate(0,0) scale(1)}40%{transform:translate(-50px,-40px) scale(1.07)}80%{transform:translate(60px,30px) scale(.96)}}
@keyframes b4{0%,100%{transform:translate(0,0) scale(1)}60%{transform:translate(80px,50px) scale(1.12)}}
@keyframes b5{0%,100%{transform:translate(0,0) scale(1)}45%{transform:translate(-60px,-30px) scale(1.08)}}

/* ===== HEADER ===== */
header{position:sticky;top:0;z-index:100;padding:18px 32px;
  background:rgba(255,255,255,.75);backdrop-filter:blur(20px) saturate(180%);
  -webkit-backdrop-filter:blur(20px) saturate(180%);
  border-bottom:1px solid rgba(15,23,42,.07);
  display:flex;align-items:center;justify-content:space-between;}
header h1{font-size:19px;letter-spacing:3px;cursor:pointer;color:var(--txt);font-weight:300;}
header h1 b{color:var(--acc);font-weight:700;}
#docker-status{color:var(--mut);font-size:13px;display:flex;align-items:center;gap:7px;}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.dot.on{background:var(--ok);box-shadow:0 0 6px var(--ok);}
.dot.off{background:var(--ko);}

/* ===== BREADCRUMB ===== */
.breadcrumb{position:sticky;top:57px;z-index:99;padding:10px 32px;
  background:rgba(255,255,255,.65);backdrop-filter:blur(12px);
  border-bottom:1px solid rgba(15,23,42,.06);
  color:var(--mut);font-size:13px;display:none;align-items:center;gap:8px;
  cursor:pointer;transition:color .15s;user-select:none;}
.breadcrumb:hover{color:var(--txt);}
.breadcrumb.visible{display:flex;}

/* ===== LANDING ===== */
#landing{position:relative;z-index:1;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  min-height:calc(100vh - 58px);padding:40px 20px 60px;}

.landing-title{text-align:center;margin-bottom:52px;}
.landing-title h2{font-size:38px;letter-spacing:4px;font-weight:200;color:var(--txt);}
.landing-title h2 b{font-weight:700;color:var(--acc);}
.landing-title p{color:var(--mut);font-size:14px;margin-top:10px;max-width:460px;line-height:1.7;}

/* 3D SCENE */
.stack-scene{perspective:900px;perspective-origin:50% 28%;}
.stack{
  transform:rotateX(30deg) rotateY(-15deg);
  transform-style:preserve-3d;
  position:relative;width:540px;height:470px;
}

/* COUCHES VERRE */
.layer{
  position:absolute;width:100%;height:72px;border-radius:20px;cursor:pointer;
  /* glassmorphism sur fond blanc */
  background:rgba(255,255,255,.25);
  backdrop-filter:blur(28px) saturate(200%);
  -webkit-backdrop-filter:blur(28px) saturate(200%);
  border:1px solid rgba(255,255,255,.75);
  box-shadow:0 4px 24px rgba(15,23,42,.06),inset 0 1px 0 rgba(255,255,255,.9);
  display:flex;align-items:center;padding:0 22px;gap:14px;
  transition:transform .35s cubic-bezier(.23,1,.32,1),box-shadow .3s;
}
/* bordure iridescente */
.layer::before{
  content:'';position:absolute;inset:-1.5px;border-radius:21.5px;
  background:linear-gradient(125deg,#ff6b9d,#c44dff,#4dc8ff,#43e97b,#f9ca24,#ff6b9d,#c44dff);
  background-size:300% 300%;animation:iris 5s linear infinite;
  z-index:-1;opacity:.35;transition:opacity .3s;
}
.layer:hover::before{opacity:.85;}
/* glow bas */
.layer::after{
  content:'';position:absolute;bottom:-2px;left:8%;right:8%;height:3px;
  background:var(--lc,var(--acc));border-radius:0 0 20px 20px;
  filter:blur(6px);opacity:.55;transition:opacity .3s,filter .3s;
}
.layer:hover::after{opacity:1;filter:blur(10px);}

@keyframes iris{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}

/* positions Z */
.layer:nth-child(1){top:0px;  transform:translateZ(130px);--lc:var(--c-creation);}
.layer:nth-child(2){top:74px; transform:translateZ(78px); --lc:var(--c-production);}
.layer:nth-child(3){top:148px;transform:translateZ(26px); --lc:var(--c-compte);}
.layer:nth-child(4){top:222px;transform:translateZ(-26px);--lc:var(--c-analyse);}
.layer:nth-child(5){top:296px;transform:translateZ(-78px);--lc:var(--c-integration);}
.layer:nth-child(6){top:370px;transform:translateZ(-130px);--lc:var(--c-don);}
/* hover : monte en Z + translateY */
.layer:nth-child(1):hover{transform:translateZ(155px) translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(8,145,178,.18);}
.layer:nth-child(2):hover{transform:translateZ(103px) translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(22,163,74,.18);}
.layer:nth-child(3):hover{transform:translateZ(51px)  translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(124,58,237,.18);}
.layer:nth-child(4):hover{transform:translateZ(-1px)  translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(37,99,235,.18);}
.layer:nth-child(5):hover{transform:translateZ(-53px) translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(234,88,12,.18);}
.layer:nth-child(6):hover{transform:translateZ(-105px) translateY(-6px);box-shadow:0 28px 60px rgba(15,23,42,.09),0 0 40px rgba(219,39,119,.18);}

.layer-marker{width:10px;height:10px;border-radius:50%;background:var(--lc,var(--acc));
  box-shadow:0 0 10px var(--lc,var(--acc));flex-shrink:0;}
.layer-label{flex:1;}
.layer-label h3{font-size:15px;font-weight:700;letter-spacing:.3px;color:var(--txt);}
.layer-label p{font-size:12px;color:var(--mut);margin-top:1px;}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:700;flex-shrink:0;}
.badge.live{background:rgba(22,163,74,.1);color:var(--ok);border:1px solid rgba(22,163,74,.2);}
.badge.soon{background:rgba(100,116,139,.07);color:var(--mut);border:1px solid rgba(100,116,139,.14);}
.layer-arrow{color:var(--mut);font-size:18px;transition:transform .2s,color .2s;}
.layer:hover .layer-arrow{transform:translateX(5px);color:var(--acc);}

/* ===== SECTIONS ===== */
.section{display:none;position:relative;z-index:1;max-width:1020px;margin:0 auto;padding:28px 32px 60px;}
.section.active{display:block;}
.sec-header{margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--line);}
.sec-header h2{font-size:22px;letter-spacing:.5px;display:flex;align-items:center;gap:10px;color:var(--txt);}
.sec-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;}
.sec-header p{color:var(--mut);font-size:14px;margin-top:6px;}

/* GLASS PANEL */
.panel{background:rgba(255,255,255,.5);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.7);border-radius:16px;padding:20px;margin-bottom:18px;
  box-shadow:0 2px 16px rgba(15,23,42,.05);}

/* PLACEHOLDER */
.placeholder{background:rgba(255,255,255,.4);backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.7);border-radius:20px;
  padding:60px 40px;text-align:center;margin-top:8px;
  box-shadow:0 4px 24px rgba(15,23,42,.05);}
.ph-icon{font-size:44px;margin-bottom:14px;opacity:.45;}
.placeholder h3{font-size:17px;margin-bottom:8px;color:var(--txt);}
.placeholder p{color:var(--mut);font-size:14px;max-width:440px;margin:0 auto;line-height:1.6;}

/* FORMULAIRES */
textarea{width:100%;min-height:90px;resize:vertical;
  background:rgba(255,255,255,.7);color:var(--txt);
  border:1px solid rgba(15,23,42,.1);border-radius:10px;
  padding:12px;font-size:15px;font-family:inherit;transition:border-color .15s,box-shadow .15s;}
textarea:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
textarea::placeholder{color:var(--mut);}
.row{display:flex;align-items:center;gap:14px;margin-top:12px;flex-wrap:wrap;}
.row label{color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px;cursor:pointer;}
.row input[type=number]{width:52px;background:rgba(255,255,255,.7);color:var(--txt);
  border:1px solid rgba(15,23,42,.1);border-radius:6px;padding:6px;font-size:14px;}
.hint{color:var(--mut);font-size:12px;}
#domaines{width:100%;margin-top:10px;background:rgba(255,255,255,.7);color:var(--txt);
  border:1px solid rgba(15,23,42,.1);border-radius:8px;padding:9px;font-size:14px;}

button{background:var(--acc);color:#fff;border:0;border-radius:10px;
  padding:10px 22px;font-weight:700;cursor:pointer;font-size:15px;
  transition:opacity .15s,transform .1s,box-shadow .15s;
  box-shadow:0 2px 8px rgba(8,145,178,.3);}
button:hover{opacity:.88;box-shadow:0 4px 16px rgba(8,145,178,.35);}
button:active{transform:scale(.98);}
button:disabled{opacity:.4;cursor:wait;box-shadow:none;}
button.ghost{background:transparent;color:var(--acc);border:1.5px solid rgba(8,145,178,.35);box-shadow:none;}
button.ghost:hover{background:rgba(8,145,178,.06);box-shadow:none;}

#proposition{margin-top:14px;padding:16px;border:1px solid rgba(8,145,178,.2);border-radius:12px;
  background:rgba(8,145,178,.04);font-size:14px;}
#proposition h3{margin:0 0 8px;font-size:14px;color:var(--acc);letter-spacing:.4px;}
#proposition .ligne{margin:4px 0;color:var(--txt);}
#proposition .reform{margin-top:8px;color:var(--warn);}
#proposition .murs{margin-top:8px;color:var(--mut);font-size:13px;}
#status{margin-top:14px;font-size:14px;color:var(--txt);}
.tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700;}
.tag.ok{background:rgba(22,163,74,.12);color:var(--ok);}
.tag.ko{background:rgba(220,38,38,.1);color:var(--ko);}
.meta{color:var(--mut);font-size:13px;margin-top:6px;}
.lecons{color:var(--warn);font-size:13px;margin-top:6px;white-space:pre-wrap;}
pre.code,#code-view{background:#0d1117;border:1px solid #30363d;border-radius:12px;
  padding:14px;overflow:auto;max-height:420px;
  font:13px/1.45 ui-monospace,Consolas,monospace;color:#c9d6e3;margin-top:14px;
  box-shadow:0 4px 20px rgba(0,0,0,.12);}
#code-view{max-height:500px;margin-top:20px;}

/* PRODUCTION */
.produit-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;}
.produit-card{background:rgba(255,255,255,.5);backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.7);border-radius:14px;padding:16px;
  transition:border-color .15s,transform .2s,box-shadow .2s;
  box-shadow:0 2px 12px rgba(15,23,42,.04);}
.produit-card:hover{border-color:var(--acc);transform:translateY(-2px);box-shadow:0 8px 24px rgba(8,145,178,.12);}
.produit-card .ct{font-size:14px;font-weight:600;margin-bottom:6px;color:var(--txt);}
.produit-card .cs{color:var(--mut);font-size:12px;margin-bottom:12px;}
.produit-card .cactions{display:flex;gap:8px;flex-wrap:wrap;}
.produit-card button{font-size:13px;padding:7px 14px;}

.hidden{display:none !important;}

/* RESPONSIVE */
@media(max-width:600px){
  .stack{width:90vw;height:415px;}
  .layer{height:66px;}
  .layer:nth-child(1){top:0;   transform:translateZ(108px);}
  .layer:nth-child(2){top:64px;transform:translateZ(65px);}
  .layer:nth-child(3){top:128px;transform:translateZ(22px);}
  .layer:nth-child(4){top:192px;transform:translateZ(-22px);}
  .layer:nth-child(5){top:256px;transform:translateZ(-65px);}
  .layer:nth-child(6){top:320px;transform:translateZ(-108px);}
  .layer:nth-child(1):hover{transform:translateZ(125px) translateY(-4px);}
  .layer:nth-child(2):hover{transform:translateZ(82px)  translateY(-4px);}
  .layer:nth-child(3):hover{transform:translateZ(38px)  translateY(-4px);}
  .layer:nth-child(4):hover{transform:translateZ(-5px)  translateY(-4px);}
  .layer:nth-child(5):hover{transform:translateZ(-48px) translateY(-4px);}
  .layer:nth-child(6):hover{transform:translateZ(-92px) translateY(-4px);}
  header{padding:14px 16px;}
  .section{padding:16px 16px 40px;}
  .landing-title h2{font-size:28px;}
}
</style>
</head>
<body>

<!-- FOND ANIME -->
<div class="bg" aria-hidden="true">
  <div class="blob b1"></div>
  <div class="blob b2"></div>
  <div class="blob b3"></div>
  <div class="blob b4"></div>
  <div class="blob b5"></div>
</div>

<header>
  <h1 onclick="showLanding()">VIVA<b>RIUM</b></h1>
  <div id="docker-status"><span class="dot off"></span>chargement...</div>
</header>

<div id="breadcrumb" class="breadcrumb" onclick="showLanding()">
  <span style="font-size:16px">←</span>
  <span id="bc-label">Accueil</span>
</div>

<!-- LANDING 3D GLASS -->
<div id="landing">
  <div class="landing-title">
    <h2>VIVA<b>RIUM</b></h2>
    <p>Une intention devient une application gouvernee, generee et executee en conteneur durci.</p>
  </div>
  <div class="stack-scene">
    <div class="stack">

      <div class="layer" onclick="showSection('creation')">
        <span class="layer-marker" style="--lc:var(--c-creation)"></span>
        <div class="layer-label"><h3>Creation</h3><p>Nouvelle intention, ADN co-construit, fabrication</p></div>
        <span class="badge live">live</span>
        <span class="layer-arrow">›</span>
      </div>

      <div class="layer" onclick="showSection('production')">
        <span class="layer-marker" style="--lc:var(--c-production)"></span>
        <div class="layer-label"><h3>Production</h3><p>Catalogue des produits generes et promus</p></div>
        <span class="badge live">live</span>
        <span class="layer-arrow">›</span>
      </div>

      <div class="layer" onclick="showSection('compte')">
        <span class="layer-marker" style="--lc:var(--c-compte)"></span>
        <div class="layer-label"><h3>Compte</h3><p>Profil, historique, preferences</p></div>
        <span class="badge soon">bientot</span>
        <span class="layer-arrow">›</span>
      </div>

      <div class="layer" onclick="showSection('analyse')">
        <span class="layer-marker" style="--lc:var(--c-analyse)"></span>
        <div class="layer-label"><h3>Analyse</h3><p>Diagnostics avances, metriques d'evolution</p></div>
        <span class="badge soon">bientot</span>
        <span class="layer-arrow">›</span>
      </div>

      <div class="layer" onclick="showSection('integrations')">
        <span class="layer-marker" style="--lc:var(--c-integration)"></span>
        <div class="layer-label"><h3>Integrations</h3><p>Connecte tes propres outils et comptes</p></div>
        <span class="badge soon">bientot</span>
        <span class="layer-arrow">›</span>
      </div>

      <div class="layer" onclick="showSection('don')">
        <span class="layer-marker" style="--lc:var(--c-don)"></span>
        <div class="layer-label"><h3>Soutenir</h3><p>Contribuer au projet VIVARIUM</p></div>
        <span class="badge soon">bientot</span>
        <span class="layer-arrow">›</span>
      </div>

    </div>
  </div>
</div>

<!-- CREATION -->
<div id="section-creation" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-creation)"></span>Creation</h2>
    <p>Decris une intention, l'organisme propose un ADN, tu valides, il fabrique.</p>
  </div>
  <div class="panel">
    <textarea id="intention" placeholder="Ex : un convertisseur de temperature celsius / fahrenheit"></textarea>
    <div class="row">
      <label><input type="checkbox" id="persistance"> persistance <span class="hint">(disque isole)</span></label>
      <label><input type="checkbox" id="reseau"> reseau <span class="hint">(liste blanche)</span></label>
      <label>tentatives <input type="number" id="max" value="2" min="1" max="5"></label>
      <label><input type="checkbox" id="juger"> mode juge <span class="hint">(2 strategies)</span></label>
    </div>
    <input type="text" id="domaines" class="hidden" placeholder="domaines autorises, virgule">
    <div class="row" style="margin-top:16px">
      <button id="btn-analyser" class="ghost">Analyser</button>
      <button id="btn-conseils" class="ghost">Conseils</button>
      <button id="btn-fabriquer">Fabriquer</button>
    </div>
    <div id="proposition" class="hidden"></div>
    <div id="status"></div>
    <pre id="code-creation" class="code hidden"></pre>
  </div>
</div>

<!-- PRODUCTION -->
<div id="section-production" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-production)"></span>Production</h2>
    <p>Produits generes, valides, prets a l'emploi.</p>
  </div>
  <div id="produit-grid" class="produit-grid"></div>
  <pre id="code-view" class="hidden"></pre>
</div>

<!-- COMPTE -->
<div id="section-compte" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-compte)"></span>Compte</h2>
    <p>Ton profil, historique et preferences.</p>
  </div>
  <div class="placeholder"><div class="ph-icon">◎</div><h3>Bientot disponible</h3>
    <p>Historique de production, preferences, parametres de gouvernance personnalises.</p></div>
</div>

<!-- ANALYSE -->
<div id="section-analyse" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-analyse)"></span>Analyse</h2>
    <p>Diagnostics avances, metriques d'evolution, conformite.</p>
  </div>
  <div class="placeholder"><div class="ph-icon">◈</div><h3>Bientot disponible</h3>
    <p>Metriques des produits, evolution du genome, courbes Anti-Goodhart.</p></div>
</div>

<!-- INTEGRATIONS -->
<div id="section-integrations" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-integration)"></span>Integrations</h2>
    <p>Connecte tes propres comptes et outils a VIVARIUM.</p>
  </div>
  <div class="placeholder"><div class="ph-icon">⊛</div><h3>Bientot disponible</h3>
    <p>Connecte tes comptes : NotebookLM, OpenLegi, TikTok, Instagram, Magnific et plus, avec tes propres credentials. VIVARIUM orchestre, tu gardes le controle.</p></div>
</div>

<!-- DON -->
<div id="section-don" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-don)"></span>Soutenir VIVARIUM</h2>
    <p>Contribuer au developpement du projet.</p>
  </div>
  <div class="placeholder"><div class="ph-icon">♡</div><h3>Bientot disponible</h3>
    <p>Soutenir VIVARIUM via Stripe. Chaque contribution finance le calcul, l'hebergement et le developpement de nouveaux organes.</p></div>
</div>

<script>
const $ = s => document.querySelector(s);
const errMsg = x => {
  if (x == null) return '';
  if (typeof x === 'string') return x;
  if (x.message) return x.message;
  try { return JSON.stringify(x); } catch(e) { return String(x); }
};
const esc = s => (s||'').replace(/[<>]/g,'');
const LABELS = {creation:'Creation',production:'Production',compte:'Compte',analyse:'Analyse',integrations:'Integrations',don:'Soutenir'};

function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $('#landing').style.display = 'none';
  const s = $('#section-' + name);
  if (s) s.classList.add('active');
  $('#breadcrumb').classList.add('visible');
  $('#bc-label').textContent = LABELS[name] || name;
  if (name === 'production') loadProduits();
}
function showLanding() {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  $('#landing').style.display = '';
  $('#breadcrumb').classList.remove('visible');
  if ($('#code-view')) $('#code-view').classList.add('hidden');
}
async function health() {
  try {
    const h = await (await fetch('/health')).json();
    $('#docker-status').innerHTML = '<span class="dot '+(h.docker?'on':'off')+'"></span>'+(h.docker?'Docker actif ('+h.docker_info+')':'Docker indisponible');
  } catch(e) {}
}
$('#reseau').onchange = () => { $('#domaines').classList.toggle('hidden', !$('#reseau').checked); };

function liste(titre, arr) {
  if (!arr||!arr.length) return '';
  return '<div class="ligne"><b>'+titre+'</b><ul style="margin:4px 0 0;padding-left:18px">'+arr.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>';
}

$('#btn-analyser').onclick = async () => {
  const intention = $('#intention').value.trim();
  if (intention.length < 3) { $('#status').innerHTML='<span class="tag ko">vide</span> ecris une intention.'; return; }
  $('#btn-analyser').disabled = true;
  $('#proposition').classList.add('hidden');
  $('#status').innerHTML = "L'organisme analyse et propose un ADN...";
  try {
    const p = await (await fetch('/proposer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({intention})})).json();
    const d = p.discernement||{};
    $('#persistance').checked = !!p.persistance;
    $('#reseau').checked = !!p.reseau;
    $('#domaines').value = (p.domaines_proposes||[]).join(', ');
    $('#domaines').classList.toggle('hidden', !p.reseau);
    let html = '<h3>Proposition de l\'organisme</h3>';
    html += '<div class="ligne">Discernement : '+(d.merite_attaque?'merite d\'y aller':'a recadrer')+' (valeur '+d.valeur+', faisabilite '+d.faisabilite+', clarte '+d.clarte+')</div>';
    html += '<div class="ligne">'+esc(d.raison)+'</div>';
    if (d.reformulation) html += '<div class="reform">Reformulation : '+esc(d.reformulation)+'</div>';
    const caps = (p.persistance?'persistance ':'')+(p.reseau?'reseau ':'');
    html += '<div class="ligne">Capacites : '+(caps.trim()||'aucune (pur)')+'</div>';
    if (p.murs_proposes&&p.murs_proposes.length) html += '<div class="murs">Murs : '+p.murs_proposes.map(esc).join(', ')+'</div>';
    html += '<div class="ligne" style="margin-top:8px;color:var(--mut)">Ajuste les capacites si besoin, puis Fabriquer.</div>';
    $('#proposition').innerHTML = html;
    $('#proposition').classList.remove('hidden');
    $('#status').innerHTML = '';
  } catch(e) { $('#status').innerHTML = '<span class="tag ko">erreur</span> '+errMsg(e); }
  finally { $('#btn-analyser').disabled = false; }
};

$('#btn-conseils').onclick = async () => {
  const intention = $('#intention').value.trim();
  if (intention.length < 3) { $('#status').innerHTML='<span class="tag ko">vide</span> ecris une intention.'; return; }
  $('#btn-conseils').disabled = true;
  $('#proposition').classList.add('hidden');
  $('#status').innerHTML = 'Le conseiller analyse (conformite + cadrage)...';
  try {
    const c = await (await fetch('/conseil',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({intention})})).json();
    if (c.detail) { $('#status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(c.detail); $('#btn-conseils').disabled=false; return; }
    const cf = c.conformite||{}, cd = c.cadrage||{};
    let html = '<h3>Conseil (indicatif IA)</h3>';
    html += '<div class="ligne"><b>Conformite</b> (risque '+esc(cf.niveau_risque||'?')+')</div>';
    html += '<ul style="margin:4px 0;padding-left:18px">'+(cf.points||[]).map(p=>'<li>'+esc(p)+'</li>').join('')+'</ul>';
    html += liste('Questions cles',cd.questions_cles);
    html += liste('Donnees a collecter',cd.donnees_a_collecter);
    html += liste('Sources a chercher',cd.sources_a_chercher);
    html += liste('Pieges',cd.pieges);
    html += '<div class="reform">'+esc(cf.avertissement||'Indicatif, confirmer par un juriste.')+'</div>';
    $('#proposition').innerHTML = html;
    $('#proposition').classList.remove('hidden');
    $('#status').innerHTML = '';
  } catch(e) { $('#status').innerHTML = '<span class="tag ko">erreur</span> '+errMsg(e); }
  finally { $('#btn-conseils').disabled = false; }
};

$('#btn-fabriquer').onclick = async () => {
  const intention = $('#intention').value.trim();
  if (intention.length < 3) { $('#status').innerHTML='<span class="tag ko">vide</span> ecris une intention.'; return; }
  const max = parseInt($('#max').value)||2;
  const persistance = $('#persistance').checked, reseau = $('#reseau').checked, juger = $('#juger').checked;
  const domaines = $('#domaines').value.split(',').map(s=>s.trim()).filter(Boolean);
  $('#btn-fabriquer').disabled = true;
  $('#code-creation').classList.add('hidden');
  $('#status').innerHTML = "L'organisme travaille : forge ADN, generation, garde-fous, conteneur...";
  try {
    const r = await fetch('/fabriquer',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({intention,max_tentatives:max,juger,persistance,reseau,domaines_autorises:domaines})});
    const d = await r.json();
    if (r.status !== 200) {
      $('#status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(d.detail!=null?d.detail:d);
    } else {
      const tag = d.succes?'<span class="tag ok">execute</span>':'<span class="tag ko">echec</span>';
      let html = tag+' '+d.verdict;
      html += '<div class="meta">'+d.tentatives+' tentative(s) | '+d.lignes+' lignes'+(d.produit_id?' | enregistre':'')+'</div>';
      if (d.capacites) html += '<div class="meta">capacites : '+d.capacites+'</div>';
      if (d.classement&&d.classement.length) html += '<div class="meta">strategies : '+d.classement.map(c=>c[0]+' '+c[1]).join(' | ')+'</div>';
      if (d.lecons&&d.lecons.length) html += '<div class="lecons">'+d.lecons.join('\n')+'</div>';
      $('#status').innerHTML = html;
      if (d.produit_id) {
        const prod = await (await fetch('/produits/'+encodeURIComponent(d.produit_id))).json();
        $('#code-creation').textContent = prod.code||'';
        $('#code-creation').classList.remove('hidden');
      }
    }
  } catch(e) { $('#status').innerHTML = '<span class="tag ko">erreur</span> '+errMsg(e); }
  finally { $('#btn-fabriquer').disabled = false; }
};

async function loadProduits() {
  const d = await (await fetch('/produits')).json();
  const list = (d.produits||[]).slice().reverse();
  const grid = $('#produit-grid');
  grid.innerHTML = '';
  if (!list.length) {
    grid.innerHTML = '<div class="placeholder"><div class="ph-icon">◻</div><h3>Aucun produit</h3><p>Va dans Creation pour fabriquer ton premier produit.</p></div>';
    return;
  }
  list.forEach(p => {
    const card = document.createElement('div'); card.className = 'produit-card';
    card.innerHTML = '<div class="ct">'+esc(p.intention)+(p.promouvable?' <span class="tag ok">appli</span>':'')+'</div>'+
                     '<div class="cs">'+p.lignes+' lignes | '+esc(p.verdict)+'</div>';
    const actions = document.createElement('div'); actions.className = 'cactions';
    const btnCode = document.createElement('button'); btnCode.className='ghost'; btnCode.textContent='Code';
    btnCode.onclick = async () => {
      const prod = await (await fetch('/produits/'+encodeURIComponent(p.id))).json();
      const cv = $('#code-view'); cv.textContent = prod.code||''; cv.classList.remove('hidden');
      cv.scrollIntoView({behavior:'smooth',block:'nearest'});
    };
    actions.appendChild(btnCode);
    if (p.promouvable) {
      const btnApp = document.createElement('button'); btnApp.textContent="Ouvrir l'appli";
      btnApp.onclick = async (e) => {
        e.stopPropagation(); btnApp.disabled=true; btnApp.textContent='...';
        try { const r = await (await fetch('/produits/'+encodeURIComponent(p.id)+'/promouvoir',{method:'POST'})).json();
          if (r.app) window.open(r.app,'_blank'); }
        catch(err) { alert(errMsg(err)); }
        finally { btnApp.disabled=false; btnApp.textContent="Ouvrir l'appli"; }
      };
      actions.appendChild(btnApp);
    }
    card.appendChild(actions); grid.appendChild(card);
  });
}

health();
</script>
</body>
</html>
"""

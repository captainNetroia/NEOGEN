"""
NEOGEN - UI : Bento 3D interactif + shader WebGL

Fond  : fragment shader GLSL (domain-warped fBm, pastels fluides), fallback gradient.
Bento : 6 onglets de nav en VRAI 3D (perspective + preserve-3d), depths varies,
        parallaxe a la souris (rotation du plan vers le curseur + float idle).
Verre : frosted SIMULE (gradients translucides + reflet specular suivant la souris).
        PAS de backdrop-filter sur les cartes : il casse preserve-3d. Sur le fond
        shader doux, rend comme du verre depoli (style UI Bento).
        Aucune dependance externe, aucun CDN.
Nav   : clic carte -> showSection(). Sections en Liquid Glass (.glass, panels 2D).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-19.
"""

PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEOGEN</title>
<style>
:root {
  --txt:#0f172a; --mut:#64748b; --line:rgba(15,23,42,.08);
  --acc:#0891b2; --ok:#16a34a; --ko:#dc2626; --warn:#d97706;
  --c-creation:#0891b2; --c-production:#16a34a; --c-compte:#7c3aed;
  --c-analyse:#2563eb; --c-integration:#ea580c; --c-don:#db2777;
}
/* MODE SOMBRE */
body.dark{--txt:#e2e8f0;--mut:#94a3b8;--line:rgba(226,232,240,.08);
  background:linear-gradient(135deg,#1e1b4b 0%,#0f172a 45%,#1e1040 100%)!important;}
body.dark .panel,body.dark .glass{background:rgba(15,10,40,.65)!important;border-color:rgba(255,255,255,.1)!important;}
body.dark header{background:rgba(10,8,30,.9)!important;border-color:rgba(255,255,255,.1)!important;}
body.dark .sidebar{background:rgba(10,8,30,.85)!important;border-color:rgba(255,255,255,.09)!important;}
body.dark input,body.dark textarea,body.dark select{background:rgba(255,255,255,.07)!important;color:var(--txt)!important;border-color:rgba(255,255,255,.15)!important;}
body.dark input::placeholder,body.dark textarea::placeholder{color:rgba(148,163,184,.65)!important;}
/* Menus deroulants : les <option> natives doivent etre lisibles en sombre */
body.dark select option{background:#1a1330!important;color:#e2e8f0!important;}
body.dark .side-item:hover,body.dark .side-item.active{background:rgba(255,255,255,.07)!important;}
body.dark .ac-msg.agent{background:rgba(255,255,255,.06)!important;color:#e2e8f0!important;}
body.dark .ac-msg.agent .ac-md{color:#e2e8f0!important;}
body.dark .ac-msg.user{background:rgba(8,145,178,.35)!important;color:#fff!important;}
body.dark .ac-trace{color:rgba(148,163,184,.7)!important;}
/* Onglets provider + pills : lisibles en sombre */
body.dark .prov-tab{border-color:rgba(255,255,255,.15)!important;color:var(--mut)!important;}
body.dark .prov-tab:hover:not(.active){background:rgba(255,255,255,.1)!important;color:#e2e8f0!important;}
body.dark .consent-btn{border-color:rgba(255,255,255,.15)!important;}
/* Boutons ghost + secondaires en sombre */
body.dark button.ghost{background:rgba(255,255,255,.08)!important;color:#e2e8f0!important;border-color:rgba(255,255,255,.18)!important;}
/* Stepper du studio (1 Intention, 2 ADN...) */
body.dark .step-title{color:#f1f5f9!important;}
body.dark .step-pill,body.dark .stepper-item{color:#cbd5e1!important;}
body.dark .srail-step{background:rgba(255,255,255,.06)!important;border-color:rgba(255,255,255,.12)!important;color:#94a3b8!important;}
body.dark .srail-step.active{background:rgba(124,58,237,.28)!important;color:#f1f5f9!important;}
body.dark .srail-step.done{color:#cbd5e1!important;}
/* Cartes integ + items */
body.dark .integ-act-head:hover{background:rgba(255,255,255,.06)!important;}
body.dark .integ-act-name,body.dark .integ-name{color:#e2e8f0!important;}
body.dark .hist-item{border-color:rgba(255,255,255,.08)!important;}
/* Tags neutres */
body.dark .tag{background:rgba(255,255,255,.1)!important;}
/* Modals (deploy + auth) : fond sombre au lieu de blanc */
body.dark .deploy-modal,body.dark #modal-auth>div{background:#1a1330!important;color:#e2e8f0!important;}
body.dark .imit-item:hover{background:rgba(255,255,255,.08)!important;}
body.dark .stat-card{background:rgba(255,255,255,.05)!important;}
/* Page d'accueil (cartes bento) en mode sombre : verre liquide nocturne */
body.dark .layer{
  background:linear-gradient(135deg,rgba(40,32,80,.55),rgba(20,16,45,.30) 52%,rgba(35,28,70,.45))!important;
  border-color:rgba(255,255,255,.16)!important;
  box-shadow:inset 0 2px 0 rgba(255,255,255,.18),inset 0 -16px 30px rgba(0,0,0,.18),0 26px 50px rgba(0,0,0,.4),0 8px 16px rgba(0,0,0,.3)!important;}
body.dark .layer-label h3{color:#f1f5f9!important;}
body.dark .layer-label p{color:#a5b0c4!important;}
body.dark .landing-title h2{color:#f1f5f9!important;}
body.dark .landing-title p{color:#a5b0c4!important;}
body.dark .layer:hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.3),0 34px 64px rgba(124,58,237,.35),0 10px 20px rgba(0,0,0,.4)!important;}
/* Toggle dark mode */
.dark-toggle{display:flex;align-items:center;gap:10px;cursor:pointer;}
.dark-toggle input[type=checkbox]{width:36px;height:20px;appearance:none;background:var(--mut);border-radius:99px;position:relative;cursor:pointer;transition:background .2s;flex-shrink:0;}
.dark-toggle input[type=checkbox]:checked{background:var(--c-compte);}
.dark-toggle input[type=checkbox]::after{content:'';position:absolute;width:14px;height:14px;border-radius:50%;background:#fff;top:3px;left:3px;transition:left .2s;}
.dark-toggle input[type=checkbox]:checked::after{left:19px;}
/* Boutons consentement */
.consent-btns{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;}
.consent-btn{padding:5px 12px;border-radius:99px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--mut);transition:all .15s;}
.consent-btn.active{background:var(--c-compte);color:#fff;border-color:var(--c-compte);}
.consent-btn.danger.active{background:#dc2626;border-color:#dc2626;}
.consent-btn.safe.active{background:#16a34a;border-color:#16a34a;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:linear-gradient(135deg,#ede9fe 0%,#dbeafe 40%,#fde8f7 100%);
  color:var(--txt);
  font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
  min-height:100vh;overflow-x:hidden;}

/* SHADER CANVAS - fond fixe */
#bg-canvas{position:fixed;inset:0;z-index:0;pointer-events:none;width:100%;height:100%;}

/* HEADER - liquid glass */
header{position:sticky;top:0;z-index:100;padding:18px 32px;
  background:rgba(255,255,255,.55);
  backdrop-filter:blur(40px) saturate(200%);
  -webkit-backdrop-filter:blur(40px) saturate(200%);
  border-bottom:1px solid rgba(255,255,255,.45);
  box-shadow:inset 0 -1px 0 rgba(255,255,255,.3),0 1px 20px rgba(0,0,0,.04);
  display:flex;align-items:center;justify-content:space-between;}
header h1{font-size:19px;letter-spacing:3px;cursor:pointer;color:var(--txt);font-weight:300;}
header h1 b{color:var(--acc);font-weight:700;}
#docker-status{color:var(--mut);font-size:13px;display:flex;align-items:center;gap:7px;}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.dot.on{background:var(--ok);box-shadow:0 0 6px var(--ok);}
.dot.off{background:var(--ko);}

/* BREADCRUMB */
.breadcrumb{position:sticky;top:57px;z-index:99;padding:10px 32px;
  background:rgba(255,255,255,.5);backdrop-filter:blur(24px);
  -webkit-backdrop-filter:blur(24px);
  border-bottom:1px solid rgba(255,255,255,.4);
  color:var(--mut);font-size:13px;display:none;align-items:center;gap:8px;
  cursor:pointer;transition:color .15s;user-select:none;}
.breadcrumb:hover{color:var(--txt);}
.breadcrumb.visible{display:flex;}

/* LANDING */
#landing{position:relative;z-index:1;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  min-height:calc(100vh - 58px);padding:40px 20px 60px;}

.landing-title{text-align:center;margin-bottom:56px;}
.landing-title h2{font-size:38px;letter-spacing:4px;font-weight:200;color:var(--txt);}
.landing-title h2 b{font-weight:700;color:var(--acc);}
.landing-title p{color:var(--mut);font-size:14px;margin-top:10px;max-width:460px;line-height:1.7;}

/* ============ BENTO 3D INTERACTIF ============
   Plan incline en VRAI 3D (preserve-3d) + parallaxe souris (JS).
   Verre frosted SIMULE (gradients + reflet specular), PAS de
   backdrop-filter : il casserait preserve-3d. Sur le fond shader
   doux ca rend comme du verre depoli, fidele a UI Bento. */
.bento{
  perspective:1250px;
  width:min(960px,94vw);
  margin:8px auto 0;
  padding:26px 10px 36px;
}
.bento-3d{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  grid-auto-rows:128px;
  gap:22px;
  transform-style:preserve-3d;
  transform:rotateX(14deg) rotateY(-16deg);
  will-change:transform;
}

/* CARTE BENTO */
.layer{
  position:relative;
  border-radius:22px;
  cursor:pointer;
  transform-style:preserve-3d;
  transform:translateZ(var(--z,0px));
  background:linear-gradient(135deg,
     rgba(255,255,255,.68), rgba(255,255,255,.24) 52%, rgba(255,255,255,.42));
  border:1px solid rgba(255,255,255,.72);
  box-shadow:
    inset 0 2px 0 rgba(255,255,255,.95),
    inset 0 -16px 30px rgba(255,255,255,.10),
    0 26px 50px rgba(15,23,42,.18),
    0 8px 16px rgba(15,23,42,.10);
  display:flex;align-items:center;gap:14px;padding:0 22px;
  transition:transform .4s cubic-bezier(.23,1,.32,1),box-shadow .3s;
  overflow:hidden;
}
/* reflet specular qui suit la souris (--mx/--my heritees de .bento-3d) */
.layer::before{
  content:'';position:absolute;inset:0;border-radius:22px;pointer-events:none;
  background:radial-gradient(220px 220px at var(--mx,30%) var(--my,0%),
     rgba(255,255,255,.6),rgba(255,255,255,0) 62%);
  opacity:.5;mix-blend-mode:screen;transition:opacity .3s;
}
/* ligne d'accent bas */
.layer::after{
  content:'';position:absolute;bottom:0;left:12%;right:12%;height:2px;
  background:var(--lc,var(--acc));border-radius:0 0 22px 22px;
  opacity:.55;transition:opacity .25s,height .2s;
  box-shadow:0 0 10px var(--lc,var(--acc));
}
.layer:hover::after{opacity:1;height:3px;}
.layer:hover::before{opacity:.8;}

/* profondeurs variees (effet bento) + couleur d'accent */
.layer:nth-child(1){--z:70px; --lc:var(--c-creation);}
.layer:nth-child(2){--z:28px; --lc:var(--c-production);}
.layer:nth-child(3){--z:54px; --lc:var(--c-compte);}
.layer:nth-child(4){--z:40px; --lc:var(--c-analyse);}
.layer:nth-child(5){--z:62px; --lc:var(--c-integration);}
.layer:nth-child(6){--z:20px; --lc:var(--c-don);}

/* hover : avance vers l'utilisateur + glow couleur */
.layer:hover{transform:translateZ(calc(var(--z,0px) + 40px)) scale(1.02);}
.layer:nth-child(1):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(8,145,178,.32),0 10px 20px rgba(15,23,42,.12);}
.layer:nth-child(2):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(22,163,74,.32),0 10px 20px rgba(15,23,42,.12);}
.layer:nth-child(3):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(124,58,237,.32),0 10px 20px rgba(15,23,42,.12);}
.layer:nth-child(4):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(37,99,235,.32),0 10px 20px rgba(15,23,42,.12);}
.layer:nth-child(5):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(234,88,12,.32),0 10px 20px rgba(15,23,42,.12);}
.layer:nth-child(6):hover{box-shadow:inset 0 2px 0 rgba(255,255,255,.95),0 34px 64px rgba(219,39,119,.32),0 10px 20px rgba(15,23,42,.12);}

.layer-marker{width:10px;height:10px;border-radius:50%;background:var(--lc,var(--acc));
  box-shadow:0 0 8px var(--lc,var(--acc));flex-shrink:0;position:relative;z-index:1;}
.layer-label{flex:1;position:relative;z-index:1;}
.layer-label h3{font-size:16px;font-weight:700;letter-spacing:.3px;color:var(--txt);}
.layer-label p{font-size:12px;color:var(--mut);margin-top:2px;line-height:1.35;}
.badge{display:inline-block;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:700;flex-shrink:0;position:relative;z-index:1;}
.badge.live{background:rgba(22,163,74,.14);color:var(--ok);border:1px solid rgba(22,163,74,.28);}
.badge.soon{background:rgba(100,116,139,.12);color:var(--mut);border:1px solid rgba(100,116,139,.22);}
.badge.warn{background:rgba(217,119,6,.14);color:var(--warn);border:1px solid rgba(217,119,6,.30);}
.integ-status-dot.warn{background:var(--warn);box-shadow:0 0 6px var(--warn);}
.tag.warn{background:rgba(217,119,6,.14);color:var(--warn);border:1px solid rgba(217,119,6,.30);}
.layer-arrow{color:var(--mut);font-size:18px;transition:transform .2s,color .2s;position:relative;z-index:1;}
.layer:hover .layer-arrow{transform:translateX(5px);color:var(--acc);}

/* SECTIONS */
.section{display:none;position:relative;z-index:1;max-width:1020px;margin:0 auto;padding:28px 32px 60px;}
.section.active{display:block;}
.sec-header{margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid rgba(15,23,42,.08);}
.sec-header h2{font-size:22px;letter-spacing:.5px;display:flex;align-items:center;gap:10px;color:var(--txt);}
.sec-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;}
.sec-header p{color:var(--mut);font-size:14px;margin-top:6px;}

/* Glassmorphism pour les panels internes */
.glass{
  background:rgba(255,255,255,.18);
  backdrop-filter:blur(32px) saturate(200%);
  -webkit-backdrop-filter:blur(32px) saturate(200%);
  border:1px solid rgba(255,255,255,.72);
  box-shadow:
    inset 0 2px 0 rgba(255,255,255,.9),
    inset 0 0 0 0.5px rgba(255,255,255,.4),
    0 24px 56px rgba(80,40,180,.1),
    0 6px 16px rgba(0,0,0,.06);
  border-radius:20px;
}
.panel{padding:20px;margin-bottom:18px;border-radius:16px;}
.panel.glass{border-radius:16px;}
.placeholder{padding:60px 40px;text-align:center;margin-top:8px;}
.ph-icon{font-size:44px;margin-bottom:14px;opacity:.45;}
.placeholder h3{font-size:17px;margin-bottom:8px;color:var(--txt);}
.placeholder p{color:var(--mut);font-size:14px;max-width:440px;margin:0 auto;line-height:1.6;}

/* Formulaires */
textarea{width:100%;min-height:90px;resize:vertical;
  background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:10px;
  padding:12px;font-size:15px;font-family:inherit;
  transition:border-color .15s,box-shadow .15s;
  backdrop-filter:blur(10px);}
textarea:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
textarea::placeholder{color:var(--mut);}
.row{display:flex;align-items:center;gap:14px;margin-top:12px;flex-wrap:wrap;}
.row label{color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px;cursor:pointer;}
.row input[type=number]{width:52px;background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:6px;padding:6px;font-size:14px;}
.hint{color:var(--mut);font-size:12px;}

/* Toggle pill glassmorphism */
.toggle-wrap{display:flex;align-items:center;gap:9px;cursor:pointer;
  user-select:none;color:var(--mut);font-size:13px;}
.toggle-inp{position:absolute;opacity:0;width:0;height:0;pointer-events:none;}
.toggle-pill{position:relative;width:42px;height:24px;border-radius:99px;flex-shrink:0;
  background:rgba(100,116,139,.22);
  border:1px solid rgba(255,255,255,.5);
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  box-shadow:inset 0 1px 4px rgba(0,0,0,.08),0 1px 0 rgba(255,255,255,.5);
  transition:background .22s,box-shadow .22s;}
.toggle-inp:checked~.toggle-pill{
  background:linear-gradient(135deg,var(--c-integration),var(--acc));
  box-shadow:0 0 12px rgba(8,145,178,.35),inset 0 1px 0 rgba(255,255,255,.3);}
.toggle-pill::after{content:'';position:absolute;top:3px;left:3px;
  width:16px;height:16px;border-radius:50%;
  background:#fff;
  box-shadow:0 1px 5px rgba(0,0,0,.18),0 0 0 0.5px rgba(255,255,255,.8);
  transition:transform .22s cubic-bezier(.23,1,.32,1);}
.toggle-inp:checked~.toggle-pill::after{transform:translateX(18px);}
.toggle-label{display:flex;align-items:center;gap:5px;}
#domaines{width:100%;margin-top:10px;background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.45);border-radius:8px;padding:9px;font-size:14px;}

button{background:var(--acc);color:#fff;border:0;border-radius:10px;
  padding:10px 22px;font-weight:700;cursor:pointer;font-size:15px;
  transition:opacity .15s,transform .1s,box-shadow .15s;
  box-shadow:0 2px 8px rgba(8,145,178,.3);}
button:hover{opacity:.88;box-shadow:0 4px 16px rgba(8,145,178,.35);}
button:active{transform:scale(.98);}
button:disabled{opacity:.4;cursor:wait;box-shadow:none;}
button.ghost{background:rgba(255,255,255,.2);backdrop-filter:blur(10px);
  color:var(--acc);border:1px solid rgba(8,145,178,.3);box-shadow:none;}
button.ghost:hover{background:rgba(255,255,255,.35);box-shadow:none;}

#proposition{margin-top:14px;padding:16px;border-radius:12px;font-size:14px;
  background:rgba(255,255,255,.1);backdrop-filter:blur(20px);
  border:1px solid rgba(8,145,178,.2);}
#proposition h3{margin:0 0 8px;font-size:14px;color:var(--acc);}
#proposition .ligne{margin:4px 0;color:var(--txt);}
#proposition .reform{margin-top:8px;color:var(--warn);}
#proposition .murs{margin-top:8px;color:var(--mut);font-size:13px;}
#status{margin-top:14px;font-size:14px;color:var(--txt);}
.tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700;}
.tag.ok{background:rgba(22,163,74,.12);color:var(--ok);}
.tag.ko{background:rgba(220,38,38,.1);color:var(--ko);}
.meta{color:var(--mut);font-size:13px;margin-top:6px;}
.lecons{color:var(--warn);font-size:13px;margin-top:6px;white-space:pre-wrap;}
pre.code,#code-view{background:#0d1117;border:1px solid rgba(255,255,255,.1);border-radius:12px;
  padding:14px;overflow:auto;max-height:420px;
  font:13px/1.45 ui-monospace,Consolas,monospace;color:#c9d6e3;margin-top:14px;
  box-shadow:0 4px 20px rgba(0,0,0,.15);}
#code-view{max-height:500px;margin-top:20px;}

/* ===== STUDIO A->Z ===== */
.studio-rail{display:flex;align-items:center;gap:6px;margin-bottom:20px;flex-wrap:wrap;}
.srail-step{display:flex;align-items:center;gap:8px;padding:7px 14px;border-radius:99px;
  background:rgba(255,255,255,.4);border:1px solid rgba(255,255,255,.5);
  font-size:13px;color:var(--mut);transition:all .25s;cursor:default;}
.srail-step .srail-num{display:flex;align-items:center;justify-content:center;
  width:22px;height:22px;border-radius:50%;background:rgba(100,116,139,.25);
  color:#fff;font-size:12px;font-weight:700;flex-shrink:0;transition:all .25s;}
.srail-step.active{background:rgba(255,255,255,.78);color:var(--txt);font-weight:600;
  box-shadow:0 2px 12px rgba(8,145,178,.15);}
.srail-step.active .srail-num{background:linear-gradient(135deg,var(--c-creation),var(--acc));
  box-shadow:0 0 10px rgba(8,145,178,.4);}
.srail-step.done .srail-num{background:var(--ok);}
.srail-step.done{color:var(--txt);}

.studio-step{display:none;animation:stepIn .35s cubic-bezier(.23,1,.32,1);}
.studio-step.active{display:block;}
@keyframes stepIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
.step-title{font-size:16px;font-weight:700;color:var(--txt);margin-bottom:10px;}
.step-help{color:var(--mut);font-size:13px;margin-bottom:14px;}
.step-nav{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:20px;}

/* Bulles de murs */
.bulle-zone{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px;min-height:40px;}
.bulle{display:inline-flex;align-items:center;gap:8px;padding:9px 14px;border-radius:99px;
  font-size:13px;font-weight:600;cursor:default;user-select:none;
  border:1px solid rgba(255,255,255,.6);transition:all .2s;animation:stepIn .3s;}
.bulle.indispensable{background:rgba(8,145,178,.12);color:var(--acc);border-color:rgba(8,145,178,.35);}
.bulle.important{background:rgba(217,119,6,.1);color:var(--warn);border-color:rgba(217,119,6,.3);}
.bulle .bulle-crit{font-size:10px;text-transform:uppercase;letter-spacing:.6px;opacity:.7;}
.bulle .bulle-x{cursor:pointer;font-size:16px;line-height:1;opacity:.6;transition:opacity .15s;}
.bulle .bulle-x:hover{opacity:1;}
.bulle-add{margin-bottom:16px;}
.bulle-add-lbl{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;display:block;}
.bulle-dispo-row{display:flex;flex-wrap:wrap;gap:8px;}
.bulle-dispo{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:99px;
  font-size:12px;cursor:pointer;background:rgba(255,255,255,.4);color:var(--mut);
  border:1px dashed rgba(100,116,139,.4);transition:all .18s;}
.bulle-dispo:hover{background:rgba(255,255,255,.7);color:var(--txt);border-style:solid;}
.bulle-dispo::before{content:'+';font-weight:700;}
.caps-bulles{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px;}
.cap-bulle{display:inline-flex;align-items:center;gap:7px;padding:8px 13px;border-radius:99px;
  font-size:13px;font-weight:600;background:rgba(124,58,237,.1);color:var(--c-compte);
  border:1px solid rgba(124,58,237,.25);}

/* Composition */
.compo-objectif{font-size:15px;color:var(--txt);margin-bottom:14px;line-height:1.5;}
.compo-section-lbl{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
  color:var(--mut);margin:14px 0 8px;}
.compo-item{display:flex;gap:9px;align-items:flex-start;padding:7px 0;font-size:14px;
  border-bottom:1px solid rgba(15,23,42,.06);}
.compo-item:last-child{border-bottom:none;}
.compo-item .ci-key{font-weight:600;color:var(--acc);flex-shrink:0;min-width:170px;}
.compo-premiere{margin-top:16px;padding:14px 16px;border-radius:12px;
  background:rgba(8,145,178,.07);border:1px solid rgba(8,145,178,.2);
  font-size:14px;color:var(--txt);line-height:1.55;}

/* Capacites cards */
.cap-choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-bottom:14px;}
.cap-card{display:block;padding:14px 16px;border-radius:14px;cursor:pointer;
  background:rgba(255,255,255,.4);border:1px solid rgba(255,255,255,.5);transition:all .2s;}
.cap-card:hover{background:rgba(255,255,255,.6);}
.cap-card-head{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.cap-card-name{font-weight:700;font-size:14px;color:var(--txt);}
.cap-card-desc{font-size:12px;color:var(--mut);line-height:1.45;}
.cap-useful{margin-left:auto;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:2px 8px;border-radius:99px;}
.cap-useful.yes{background:rgba(22,163,74,.14);color:var(--ok);}
.cap-useful.no{background:rgba(100,116,139,.14);color:var(--mut);}
.power-gauge{font-size:13px;color:var(--mut);display:inline-flex;align-items:center;gap:7px;}
.power-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:rgba(100,116,139,.25);}
.power-dot.on{background:linear-gradient(135deg,var(--warn),var(--ko));box-shadow:0 0 7px rgba(217,119,6,.5);}

/* Forge live */
.forge-flow{display:flex;flex-direction:column;gap:9px;margin-bottom:16px;}
.forge-evt{display:flex;align-items:center;gap:11px;padding:11px 14px;border-radius:11px;
  background:rgba(255,255,255,.4);border:1px solid rgba(255,255,255,.5);
  font-size:14px;color:var(--txt);animation:stepIn .3s;}
.forge-evt .fe-icon{width:24px;height:24px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#fff;}
.forge-evt.run .fe-icon{background:var(--acc);animation:pulse 1.1s infinite;}
.forge-evt.ok .fe-icon{background:var(--ok);}
.forge-evt.ko .fe-icon{background:var(--ko);}
.forge-evt .fe-sub{color:var(--mut);font-size:12px;margin-top:2px;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.45;}}
#forge-result{margin-top:8px;font-size:14px;}

/* Mur personnalise */
.bulle.custom{background:rgba(124,58,237,.1);border-color:rgba(124,58,237,.35);}
.bulle.custom .bulle-crit{color:#7c3aed;}
.bulle-custom-add{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap;}
.bulle-custom-add input{flex:1;min-width:180px;padding:6px 10px;border-radius:8px;
  border:1px solid rgba(15,23,42,.15);font-size:13px;background:rgba(255,255,255,.6);}

/* Capacite bulle interactive */
.cap-bulle{cursor:pointer;user-select:none;
  transition:opacity .15s,background .15s,border-color .15s;opacity:.5;}
.cap-bulle.active{opacity:1;background:rgba(8,145,178,.14);
  border-color:var(--acc);color:var(--acc);}

/* Delegation agentique (orchestrateur) : cartes sous-agents */
.deleg-flow{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin:12px 0;}
.deleg-card{border-radius:12px;padding:12px 14px;background:rgba(255,255,255,.32);
  border:1px solid rgba(15,23,42,.1);transition:all .25s;position:relative;overflow:hidden;}
.deleg-card.en_cours{border-color:var(--acc);box-shadow:0 0 14px rgba(8,145,178,.18);}
.deleg-card.fait{border-color:rgba(22,163,74,.5);background:rgba(22,163,74,.06);}
.deleg-card.echec{border-color:rgba(220,38,38,.5);background:rgba(220,38,38,.05);}
.deleg-card.en_cours::after{content:'';position:absolute;left:0;bottom:0;height:3px;width:100%;
  background:linear-gradient(90deg,transparent,var(--acc),transparent);animation:slide 1.2s infinite;}
@keyframes slide{0%{transform:translateX(-100%);}100%{transform:translateX(100%);}}
.deleg-head{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.deleg-name{font-weight:700;font-size:13px;color:var(--txt);font-family:ui-monospace,monospace;}
.deleg-icon{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;}
.deleg-card.en_cours .deleg-icon{background:var(--acc);animation:pulse 1.1s infinite;}
.deleg-card.fait .deleg-icon{background:var(--ok);}
.deleg-card.echec .deleg-icon{background:var(--ko);}
.deleg-role{font-size:12px;color:var(--mut);line-height:1.4;margin-bottom:8px;}
.deleg-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.deleg-tier{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;
  padding:2px 7px;border-radius:99px;}
.deleg-tier.fort{background:rgba(220,38,38,.12);color:var(--ko);}
.deleg-tier.moyen{background:rgba(217,119,6,.14);color:var(--warn);}
.deleg-tier.leger{background:rgba(22,163,74,.12);color:var(--ok);}
.deleg-model{font-size:11px;color:var(--mut);font-family:ui-monospace,monospace;}

/* Strategies dual-window (mode juge) */
.strategies-dual{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0;}
.strat-card{border-radius:12px;padding:12px 14px;background:rgba(255,255,255,.25);
  border:1px solid rgba(15,23,42,.1);}
.strat-card.gagnant{border-color:rgba(22,163,74,.5);background:rgba(22,163,74,.07);}
.strat-card.perdant{opacity:.72;}
.strat-card-head{display:flex;align-items:center;gap:8px;margin-bottom:8px;
  font-size:13px;font-weight:600;}
.strat-score{font-size:11px;color:var(--mut);background:rgba(15,23,42,.06);
  border-radius:6px;padding:2px 7px;margin-left:auto;}
.strat-code{max-height:180px;overflow:auto;font-size:11px;line-height:1.45;
  background:rgba(0,0,0,.85);color:#e5e7eb;border-radius:8px;padding:10px;margin:0;}

/* Production */
.produit-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;}

/* Compte */
.profil-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px;}
.profil-field{display:flex;flex-direction:column;gap:5px;}
.profil-field label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--mut);}
.profil-field input{background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:8px;
  padding:8px 12px;font-size:14px;font-family:inherit;}
.profil-field input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
.hist-item{display:flex;align-items:center;gap:10px;padding:9px 0;
  border-bottom:1px solid rgba(15,23,42,.06);font-size:13px;}
.hist-item:last-child{border-bottom:none;}
.hist-intention{flex:1;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.hist-meta{color:var(--mut);font-size:12px;flex-shrink:0;}

/* Auth */
.auth-tabs{display:flex;gap:0;margin-bottom:20px;border-radius:10px;overflow:hidden;background:rgba(100,116,139,.1);}
.auth-tab{flex:1;padding:8px;text-align:center;font-size:13px;font-weight:600;cursor:pointer;color:var(--mut);transition:all .15s;}
.auth-tab.active{background:rgba(255,255,255,.7);color:var(--txt);}
.auth-form{display:flex;flex-direction:column;gap:12px;}
.auth-field{display:flex;flex-direction:column;gap:5px;}
.auth-field label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:var(--mut);}
.auth-field input{background:rgba(255,255,255,.55);color:var(--txt);border:1px solid rgba(255,255,255,.55);border-radius:8px;padding:10px 12px;font-size:14px;font-family:inherit;}
.auth-field input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
.auth-error{font-size:13px;color:var(--ko);padding:8px 10px;border-radius:8px;background:rgba(239,68,68,.08);}
.star-row{display:flex;gap:4px;}
.star{font-size:22px;cursor:pointer;color:rgba(100,116,139,.3);transition:color .1s;line-height:1;}
.star.on{color:#f59e0b;}
#fb-msg{width:100%;min-height:80px;padding:10px 12px;border-radius:9px;border:1px solid rgba(100,116,139,.22);background:rgba(255,255,255,.5);font-size:14px;resize:vertical;box-sizing:border-box;font-family:inherit;color:var(--txt);}
#fb-msg:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
.fb-item{padding:12px 0;border-bottom:1px solid rgba(100,116,139,.1);}
.fb-item:last-child{border-bottom:none;}
.fb-header{display:flex;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap;}
.fb-name{font-weight:600;font-size:13px;color:var(--txt);}
.fb-date{font-size:11px;color:var(--mut);}
.fb-msg{font-size:13px;color:var(--txt);line-height:1.5;}

/* Analyse */
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:18px;}
.stat-card{padding:18px 16px;border-radius:14px;text-align:center;}
.stat-val{font-size:30px;font-weight:700;color:var(--txt);line-height:1;letter-spacing:-1px;}
.stat-lbl{font-size:11px;color:var(--mut);margin-top:5px;text-transform:uppercase;letter-spacing:.7px;}
.cap-bar-wrap{margin-bottom:12px;}
.cap-bar-wrap:last-child{margin-bottom:0;}
.cap-bar-label{display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px;color:var(--txt);}
.cap-bar{height:6px;border-radius:99px;background:rgba(100,116,139,.15);}
.cap-bar-fill{height:100%;border-radius:99px;background:var(--acc);
  transition:width .7s cubic-bezier(.23,1,.32,1);}

/* Integrations */
.integ-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:4px;}
.integ-category{padding:16px 18px;border-radius:16px;}
.integ-cat-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;
  color:var(--mut);margin-bottom:10px;}
.integ-item{display:flex;align-items:center;gap:9px;padding:8px 0;
  border-bottom:1px solid rgba(15,23,42,.06);font-size:14px;color:var(--txt);}
.integ-item:last-child{border-bottom:none;padding-bottom:0;}
.integ-icon{font-size:14px;width:20px;text-align:center;flex-shrink:0;opacity:.8;}
.integ-name{flex:1;}
.integ-status-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;
  background:rgba(100,116,139,.3);transition:background .2s,box-shadow .2s;}
.integ-status-dot.ok{background:var(--ok);box-shadow:0 0 6px var(--ok);}
.integ-status-dot.ko{background:var(--ko);}
.integ-section-label{font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:.9px;color:var(--mut);margin-bottom:10px;}
/* Provider tabs */
.prov-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;}
.prov-tab{padding:4px 12px;border-radius:99px;font-size:12px;font-weight:600;
  cursor:pointer;border:1px solid rgba(15,23,42,.12);
  background:rgba(255,255,255,.35);color:var(--mut);
  transition:background .15s,color .15s,border-color .15s;user-select:none;}
.prov-tab:hover:not(.active){background:rgba(255,255,255,.6);color:var(--txt);}
.prov-tab.active{background:var(--acc);color:#fff;border-color:var(--acc);}
/* Model row */
.integ-model-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;}
.integ-model-row select{flex:1;min-width:160px;
  background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:8px;
  padding:8px 12px;font-size:14px;font-family:inherit;}
.integ-model-row select:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
/* Key input with live dot inside */
.integ-key-wrap{position:relative;flex:2;min-width:200px;display:flex;align-items:center;}
.integ-key-wrap input{width:100%;padding:8px 32px 8px 12px;
  background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:8px;
  font-size:14px;font-family:inherit;}
.integ-key-wrap input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px rgba(8,145,178,.1);}
.integ-model-dot{position:absolute;right:10px;width:9px;height:9px;border-radius:50%;
  background:rgba(100,116,139,.3);transition:background .2s,box-shadow .2s;pointer-events:none;}
.integ-model-dot.ok{background:var(--ok);box-shadow:0 0 7px var(--ok);}
.integ-model-dot.ko{background:var(--ko);box-shadow:0 0 5px var(--ko);}
#integ-status{margin-top:10px;font-size:13px;min-height:20px;}
/* Custom integration form */
.integ-add-btn{font-size:13px;color:var(--acc);cursor:pointer;
  padding:8px 0 2px;font-weight:600;transition:opacity .15s;}
.integ-add-btn:hover{opacity:.7;}
#integ-add-form{margin-top:10px;display:flex;flex-direction:column;gap:7px;}
#integ-add-form input{background:rgba(255,255,255,.55);color:var(--txt);
  border:1px solid rgba(255,255,255,.55);border-radius:8px;
  padding:7px 10px;font-size:13px;font-family:inherit;width:100%;}
#integ-add-form input:focus{outline:none;border-color:var(--acc);}
.produit-card{padding:16px;border-radius:14px;
  transition:transform .2s,box-shadow .2s;}
.produit-card.glass:hover{transform:translateY(-2px);
  box-shadow:inset 0 1.5px 0 rgba(255,255,255,.8),0 16px 40px rgba(8,145,178,.12);}
.produit-card .ct{font-size:14px;font-weight:600;margin-bottom:6px;color:var(--txt);}
.produit-card .cs{color:var(--mut);font-size:12px;margin-bottom:12px;}
.produit-card .cactions{display:flex;gap:8px;flex-wrap:wrap;}
.produit-card button{font-size:13px;padding:7px 14px;}
.gen-badge{display:inline-block;font-size:11px;font-weight:700;padding:1px 8px;border-radius:99px;
  background:rgba(124,58,237,.12);color:#7c3aed;margin-left:6px;}

/* Arbre de genealogie (Phase 4) */
.lineage-view{margin-top:16px;}
/* Lignee inline (expand sous la carte cliquee) */
.lineage-inline{
  grid-column:1/-1;padding:22px 24px;border-radius:14px;
  animation:lineageIn .3s ease;overflow:hidden;
  margin-top:4px;margin-bottom:8px;
}
@keyframes lineageIn{from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:translateY(0);}}
.produit-card.selected{
  border-color:rgba(8,145,178,.6)!important;
  box-shadow:inset 0 1.5px 0 rgba(255,255,255,.9),0 4px 24px rgba(8,145,178,.18)!important;
  transform:translateY(-3px) scale(1.01)!important;
}
.lineage-head{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;}
.lineage-head h3{font-size:16px;font-weight:600;color:var(--txt);}
.lineage-tree{display:flex;flex-direction:column;gap:0;}
.gen-node{position:relative;padding:14px 16px;border-radius:12px;margin-left:18px;
  background:rgba(255,255,255,.32);border:1px solid rgba(15,23,42,.1);margin-bottom:18px;}
.gen-node.actif{border-color:rgba(8,145,178,.55);background:rgba(8,145,178,.06);
  box-shadow:0 2px 14px rgba(8,145,178,.12);}
.gen-node::before{content:'';position:absolute;left:-18px;top:24px;width:18px;height:2px;
  background:rgba(15,23,42,.18);}
.gen-node:not(:last-child)::after{content:'';position:absolute;left:-18px;top:24px;
  width:2px;height:calc(100% + 18px);background:rgba(15,23,42,.18);}
.gen-node-head{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}
.gen-num{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;
  background:linear-gradient(135deg,var(--c-compte),#7c3aed);color:#fff;font-size:12px;font-weight:700;flex-shrink:0;}
.gen-node.actif .gen-num{background:linear-gradient(135deg,var(--c-creation),var(--acc));}
.gen-meta{color:var(--mut);font-size:12px;}
.gen-delta{font-size:11px;font-weight:600;}
.gen-delta .add{color:var(--ok);}.gen-delta .del{color:var(--ko);}
.gen-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px;}
.gen-actions button{font-size:12px;padding:5px 11px;}
.gen-diff{margin-top:10px;max-height:240px;overflow:auto;font-size:11px;line-height:1.45;
  background:rgba(0,0,0,.85);color:#e5e7eb;border-radius:8px;padding:10px;white-space:pre;display:none;}
.gen-diff .dadd{color:#86efac;}.gen-diff .ddel{color:#fca5a5;}.gen-diff .dhdr{color:#7dd3fc;}
.gen-gov{display:flex;flex-wrap:wrap;gap:5px;margin:5px 0;font-size:11px;}
.gen-gov .dadd{background:rgba(134,239,172,.12);color:#86efac;padding:2px 7px;border-radius:4px;}
.gen-gov .ddel{background:rgba(252,165,165,.12);color:#fca5a5;padding:2px 7px;border-radius:4px;}

/* Integ activation — accordion */
/* Item bientot : style plat */
.integ-item{display:flex;align-items:center;gap:9px;padding:8px 0;
  border-bottom:1px solid rgba(15,23,42,.05);font-size:14px;color:var(--txt);}
.integ-item:last-child{border-bottom:none;}
/* Item activatable : accordion */
.integ-activatable{border-radius:10px;overflow:hidden;
  border:1px solid rgba(15,23,42,.08);margin-bottom:6px;
  transition:border-color .22s,box-shadow .22s;}
.integ-activatable:last-child{margin-bottom:0;}
.integ-activatable.active{border-color:rgba(22,163,74,.45);
  box-shadow:0 0 14px rgba(22,163,74,.1);}
.integ-activatable.open{border-color:rgba(8,145,178,.4);
  box-shadow:0 2px 16px rgba(8,145,178,.12);}
.integ-act-head{display:flex;align-items:center;gap:9px;padding:10px 12px;
  cursor:pointer;user-select:none;transition:background .15s;border-radius:10px;}
.integ-act-head:hover{background:rgba(255,255,255,.55);}
.integ-activatable.open .integ-act-head{border-radius:10px 10px 0 0;
  background:rgba(255,255,255,.4);}
.integ-act-name{flex:1;font-size:14px;color:var(--txt);font-weight:500;}
.integ-act-right{display:flex;align-items:center;gap:6px;flex-shrink:0;}
.ia-chev{font-size:11px;color:var(--mut);transition:transform .3s cubic-bezier(.23,1,.32,1);
  display:inline-block;}
/* Corps accordion : expansion par max-height */
.integ-act-body{max-height:0;overflow:hidden;
  transition:max-height .35s cubic-bezier(.4,0,.2,1);}
.integ-act-body.open{max-height:280px;}
.iam-inner{padding:10px 12px 14px;border-top:1px solid rgba(15,23,42,.06);}
.iam-desc{font-size:12px;color:var(--mut);margin-bottom:10px;line-height:1.5;}
.iam-inner input{width:100%;padding:7px 10px;border-radius:8px;
  border:1px solid rgba(15,23,42,.12);font-size:12px;
  background:rgba(255,255,255,.65);margin-bottom:8px;font-family:inherit;}
.iam-inner input:focus{outline:none;border-color:var(--acc);}
.iam-inner button{width:100%;font-size:12px;padding:7px;}
.iam-inner button+button{margin-top:5px;}
/* Don modal preset buttons */
.don-preset{background:rgba(219,39,119,.07);border:1px solid rgba(219,39,119,.2);
  border-radius:9px;padding:9px 6px;font-size:13px;font-weight:600;
  color:var(--c-don);cursor:pointer;transition:background .15s,border-color .15s;}
.don-preset:hover{background:rgba(219,39,119,.15);}
.don-preset.sel{background:rgba(219,39,119,.18);border-color:rgba(219,39,119,.6);
  box-shadow:0 0 10px rgba(219,39,119,.15);}
.btn-iam-deact{background:rgba(220,38,38,.07);color:var(--ko);
  border:1px solid rgba(220,38,38,.25);border-radius:8px;
  cursor:pointer;font-size:12px;padding:7px;width:100%;
  transition:background .15s;font-weight:600;}
.btn-iam-deact:hover{background:rgba(220,38,38,.14);}
/* Outils actifs (creation step 1) */
.outils-actifs{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:8px 12px;border-radius:9px;margin-top:10px;
  background:rgba(22,163,74,.07);border:1px solid rgba(22,163,74,.2);
  font-size:12px;color:var(--ok);}
.outil-chip{padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;
  background:rgba(22,163,74,.14);color:var(--ok);border:1px solid rgba(22,163,74,.25);}

.hidden{display:none !important;}

/* ===== RPA Agent Status Panel ===== */
.rpa-panel{margin-top:16px;}
.rpa-status-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:12px;
  background:rgba(255,255,255,.35);border:1px solid rgba(255,255,255,.55);margin-bottom:12px;}
.rpa-status-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;
  transition:background .3s,box-shadow .3s;}
.rpa-status-dot.connected{background:var(--ok);box-shadow:0 0 10px var(--ok);animation:pulse 1.8s infinite;}
.rpa-status-dot.disconnected{background:var(--ko);box-shadow:0 0 5px rgba(220,38,38,.3);}
.rpa-status-label{font-size:14px;font-weight:600;color:var(--txt);}
.rpa-status-sub{font-size:12px;color:var(--mut);}
.rpa-queue-badge{margin-left:auto;font-size:11px;font-weight:700;padding:3px 10px;
  border-radius:99px;background:rgba(8,145,178,.12);color:var(--acc);}

/* Imitation Recording controls */
.imit-controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;}
.imit-controls button{font-size:13px;padding:8px 16px;}
.imit-rec-dot{display:inline-block;width:10px;height:10px;border-radius:50%;
  background:var(--ko);animation:pulse 0.8s infinite;vertical-align:middle;margin-right:5px;}

/* Recordings list */
.imit-list{max-height:360px;overflow-y:auto;}
.imit-item{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:10px;
  margin-bottom:6px;background:rgba(255,255,255,.3);
  border:1px solid rgba(15,23,42,.06);transition:all .2s;}
.imit-item:hover{background:rgba(255,255,255,.55);border-color:rgba(8,145,178,.25);}
.imit-item-name{flex:1;font-weight:600;font-size:14px;color:var(--txt);}
.imit-item-meta{font-size:12px;color:var(--mut);}
.imit-item-actions{display:flex;gap:5px;flex-shrink:0;}
.imit-item-actions button{font-size:11px;padding:5px 10px;}

/* Deploy modal */
.deploy-modal-backdrop{position:fixed;inset:0;z-index:9999;
  background:rgba(15,23,42,.55);backdrop-filter:blur(6px);
  display:flex;align-items:center;justify-content:center;}
.deploy-modal{background:#fff;border-radius:18px;padding:28px 24px;max-width:440px;width:92%;
  box-shadow:0 24px 64px rgba(0,0,0,.22);position:relative;animation:stepIn .3s ease;}
.deploy-modal .dm-close{position:absolute;top:14px;right:16px;background:none;border:none;
  font-size:20px;cursor:pointer;color:var(--mut);line-height:1;padding:2px 6px;}
.deploy-modal h3{font-size:17px;font-weight:700;color:var(--txt);margin-bottom:6px;}
.deploy-modal .dm-desc{font-size:13px;color:var(--mut);margin-bottom:16px;line-height:1.5;}
.deploy-modal input[type=text]{width:100%;padding:10px 12px;border-radius:9px;font-size:14px;
  border:1px solid rgba(15,23,42,.15);background:rgba(255,255,255,.8);color:var(--txt);
  font-family:inherit;margin-bottom:12px;}
.deploy-modal input[type=text]:focus{outline:none;border-color:var(--acc);
  box-shadow:0 0 0 3px rgba(8,145,178,.1);}
.deploy-modal .dm-log{max-height:160px;overflow-y:auto;font-size:12px;color:var(--mut);
  padding:8px 10px;border-radius:8px;background:rgba(15,23,42,.04);margin-top:10px;
  border:1px solid rgba(15,23,42,.06);line-height:1.6;display:none;}
.deploy-modal .dm-status{font-size:13px;margin-top:10px;min-height:18px;text-align:center;}

/* SIDEBAR — visible uniquement en mode section */
.sidebar{
  position:fixed;left:0;top:57px;
  width:220px;height:calc(100vh - 57px);
  background:rgba(255,255,255,.55);
  backdrop-filter:blur(40px) saturate(200%);
  -webkit-backdrop-filter:blur(40px) saturate(200%);
  border-right:1px solid rgba(255,255,255,.45);
  box-shadow:2px 0 20px rgba(0,0,0,.04);
  display:none;flex-direction:column;
  z-index:90;padding:16px 0;overflow-y:auto;
}
body.in-section .sidebar{display:flex;}
body.in-section .section.active{margin-left:220px;max-width:none;}
body.in-section #breadcrumb{display:none !important;}

.side-home{display:flex;align-items:center;gap:8px;
  padding:0 16px 14px;border-bottom:1px solid rgba(15,23,42,.08);
  margin-bottom:10px;cursor:pointer;transition:color .15s;}
.side-home:hover .side-title{color:var(--acc);}
.side-title{font-size:15px;letter-spacing:2px;font-weight:300;color:var(--txt);}
.side-title b{color:var(--acc);font-weight:700;}
.side-back{font-size:13px;color:var(--mut);transition:color .15s;}
.side-home:hover .side-back{color:var(--acc);}

.side-item{display:flex;align-items:center;gap:9px;
  padding:9px 16px;cursor:pointer;border-radius:10px;
  margin:1px 8px;transition:background .15s,color .15s,box-shadow .2s;
  color:var(--mut);font-size:14px;will-change:transform;}
.side-item:hover{background:rgba(255,255,255,.65);color:var(--txt);
  box-shadow:2px 3px 18px rgba(0,0,0,.09),inset 0 1px 0 rgba(255,255,255,.7);}
.side-item.active{background:rgba(255,255,255,.78);color:var(--txt);font-weight:600;
  box-shadow:2px 3px 14px rgba(0,0,0,.07),inset 0 1px 0 rgba(255,255,255,.7);}
.side-dot{width:8px;height:8px;border-radius:50%;background:var(--lc,var(--mut));
  flex-shrink:0;box-shadow:0 0 5px var(--lc,transparent);
  transition:box-shadow .2s;}
.side-item:hover .side-dot,.side-item.active .side-dot{
  box-shadow:0 0 8px var(--lc,transparent),0 0 18px var(--lc,transparent);}
.side-badge{font-size:10px;font-weight:700;padding:2px 6px;border-radius:99px;margin-left:auto;}
.side-badge.live{background:rgba(22,163,74,.14);color:var(--ok);}
.side-badge.soon{background:rgba(100,116,139,.12);color:var(--mut);}

/* RESPONSIVE */
@media(max-width:780px){
  .bento-3d{grid-template-columns:repeat(2,1fr);transform:rotateX(10deg) rotateY(-10deg);}
}
@media(max-width:700px){
  .sidebar{display:none !important;}
  body.in-section .section.active{margin-left:0 !important;}
  body.in-section #breadcrumb{display:flex !important;}
}
@media(max-width:600px){
  .bento{perspective:900px;}
  .bento-3d{grid-template-columns:1fr;grid-auto-rows:84px;gap:16px;transform:rotateX(6deg) rotateY(-6deg);}
  .layer:nth-child(n){--z:24px;}
  header{padding:14px 16px;}
  .section{padding:16px 16px 40px;}
  .landing-title h2{font-size:28px;}
}
/* ===== AGENTS CONVERSATIONNELS ===== */
.agent-chat{display:flex;flex-direction:column;margin-bottom:18px}
.agent-chat-head{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:15px}
.agent-chat-head .agent-chat-dot{width:9px;height:9px;border-radius:50%;background:#a855f7;box-shadow:0 0 9px #a855f7}
.agent-chat-head .agent-chat-sub{color:var(--mut);font-size:12px;font-weight:400}
.agent-chat-log{overflow-y:auto;min-height:90px;max-height:46vh;padding:6px 2px;display:flex;flex-direction:column;gap:9px}
.agent-chat-log:empty::before{content:"Ecris un message pour commencer.";color:var(--mut);font-size:13px;padding:8px 2px}
.ac-msg{max-width:88%;padding:10px 13px;border-radius:14px;font-size:14px;line-height:1.55;word-wrap:break-word;overflow-wrap:anywhere}
.ac-msg.user{align-self:flex-end;background:linear-gradient(135deg,#0ea5b7,#0c8ea0);color:#fff;border-bottom-right-radius:4px}
.ac-msg.agent{align-self:flex-start;background:rgba(15,23,42,.05);color:#0f172a;border:1px solid rgba(15,23,42,.08);border-bottom-left-radius:4px}
.ac-trace{align-self:flex-start;max-width:94%;font-size:12px;color:var(--mut);padding:1px 4px;border-left:2px solid rgba(168,85,247,.4);margin-left:2px;line-height:1.4}
.ac-trace.action{color:#0c8ea0;border-left-color:#0c8ea0}
.ac-trace.deleg{color:#a855f7;font-weight:600;border-left-color:#a855f7}
.agent-chat-input{display:flex;gap:8px;margin-top:10px;align-items:flex-end}
.agent-chat-input textarea{flex:1;resize:none;border-radius:12px;border:1px solid rgba(15,23,42,.14);padding:10px 12px;font:inherit;font-size:14px;max-height:130px;background:rgba(255,255,255,.55)}
.agent-chat-send{padding:10px 18px;border-radius:12px;border:none;background:linear-gradient(135deg,#0ea5b7,#0c8ea0);color:#fff;font-weight:600;cursor:pointer}
.agent-chat-send:disabled{opacity:.5;cursor:default}
.agent-chat-clear{margin-left:auto;background:none;border:none;cursor:pointer;font-size:14px;opacity:.45;padding:2px 6px}
.agent-chat-clear:hover{opacity:.9}
.ac-md h3{font-size:15px;margin:8px 0 4px}.ac-md ul{margin:4px 0 4px 18px}.ac-md li{margin:2px 0}
.ac-md code{background:rgba(15,23,42,.08);padding:1px 5px;border-radius:5px;font-size:12px}
.eco-toggle{display:inline-flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;font-weight:600;color:var(--mut);margin-left:auto;margin-right:8px;user-select:none}
.eco-toggle input{width:30px;height:16px;appearance:none;background:rgba(100,116,139,.35);border-radius:99px;position:relative;cursor:pointer;transition:background .2s;flex-shrink:0}
.eco-toggle input:checked{background:var(--ok)}
.eco-toggle input::after{content:'';position:absolute;width:12px;height:12px;border-radius:50%;background:#fff;top:2px;left:2px;transition:left .2s}
.eco-toggle input:checked::after{left:16px}
.ac-md table{border-collapse:collapse;margin:8px 0;font-size:12px;width:100%}
.ac-md td,.ac-md th{border:1px solid rgba(15,23,42,.15);padding:5px 9px;text-align:left}
.ac-md th{background:rgba(15,23,42,.06);font-weight:700}
.ac-md tr:nth-child(even) td{background:rgba(15,23,42,.025)}
body.dark .ac-md td,body.dark .ac-md th{border-color:rgba(255,255,255,.14)}
body.dark .ac-md th{background:rgba(255,255,255,.08)}
body.dark .ac-md tr:nth-child(even) td{background:rgba(255,255,255,.03)}
body.dark .ac-md code{background:rgba(255,255,255,.1)}
</style>
</head>
<body>

<!-- SHADER CANVAS (fond fixe) -->
<canvas id="bg-canvas"></canvas>

<header>
  <h1 onclick="showLanding()">NEO<b>GEN</b></h1>
  <div id="docker-status"><span class="dot off"></span>chargement...</div>
</header>

<div id="breadcrumb" class="breadcrumb" onclick="showLanding()">
  <span style="font-size:16px">←</span>
  <span id="bc-label">Accueil</span>
</div>

<!-- SIDEBAR (flottant, visible en mode section) -->
<nav class="sidebar" id="sidebar">
  <div class="side-home" onclick="showLanding()">
    <span class="side-back">←</span>
    <span class="side-title">NEO<b>GEN</b></span>
  </div>
  <div class="side-item" style="--lc:#a855f7" onclick="showSection('cerveau')" id="side-cerveau">
    <span class="side-dot"></span>Cerveaux
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-creation)" onclick="showSection('creation')" id="side-creation">
    <span class="side-dot"></span>Creation
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-production)" onclick="showSection('production')" id="side-production">
    <span class="side-dot"></span>Production
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-compte)" onclick="showSection('compte')" id="side-compte">
    <span class="side-dot"></span>Compte
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-analyse)" onclick="showSection('analyse')" id="side-analyse">
    <span class="side-dot"></span>Analyse
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-integration)" onclick="showSection('integrations')" id="side-integrations">
    <span class="side-dot"></span>Integrations
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-don)" onclick="showSection('don')" id="side-don">
    <span class="side-dot"></span>Soutenir
    <span class="side-badge live">live</span>
  </div>
</nav>

<!-- LANDING -->
<div id="landing">
  <div class="landing-title">
    <h2>NEO<b>GEN</b></h2>
    <p>Une intention devient une application gouvernee, generee et executee en conteneur durci.</p>
  </div>

  <div class="bento">
    <div class="bento-3d">

    <div class="layer" onclick="showSection('cerveau')">
      <span class="layer-marker" style="--lc:#a855f7"></span>
      <div class="layer-label"><h3>Cerveaux</h3><p>Le super-agent qui coordonne les autres et agit pour toi</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

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
      <div class="layer-label"><h3>Compte</h3><p>Profil, modele actif, historique, retours</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('analyse')">
      <span class="layer-marker" style="--lc:var(--c-analyse)"></span>
      <div class="layer-label"><h3>Analyse</h3><p>Metriques de production et capacites utilisees</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('integrations')">
      <span class="layer-marker" style="--lc:var(--c-integration)"></span>
      <div class="layer-label"><h3>Integrations</h3><p>Modele IA, outils tiers, API personnalisees</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('don')">
      <span class="layer-marker" style="--lc:var(--c-don)"></span>
      <div class="layer-label"><h3>Soutenir</h3><p>Financer le calcul et le developpement</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    </div>
  </div>
</div>

<!-- CREATION : Studio A->Z -->
<div id="section-creation" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-creation)"></span>Creation</h2>
    <p>Construis ton produit etape par etape : intention, ADN, capacites, forge en direct.</p>
  </div>
  <div class="agent-chat-mount" data-agent="createur" data-titre="🔨 Le Forgeron" data-sub="Decris ton projet (app, SaaS, gadget), je le cree de A a Z."></div>

  <!-- Rail des etapes -->
  <div class="studio-rail" id="studio-rail">
    <div class="srail-step active" data-step="1"><span class="srail-num">1</span><span class="srail-lbl">Intention</span></div>
    <div class="srail-step" data-step="2"><span class="srail-num">2</span><span class="srail-lbl">ADN</span></div>
    <div class="srail-step" data-step="3"><span class="srail-num">3</span><span class="srail-lbl">Composition</span></div>
    <div class="srail-step" data-step="4"><span class="srail-num">4</span><span class="srail-lbl">Production</span></div>
    <div class="srail-step" data-step="5"><span class="srail-num">5</span><span class="srail-lbl">Forge</span></div>
  </div>

  <!-- ETAPE 1 : Intention + discernement -->
  <div class="studio-step active panel glass" data-step="1">
    <div class="step-title">Decris ton intention</div>
    <textarea id="intention" placeholder="Ex : un convertisseur de temperature celsius / fahrenheit"></textarea>
    <div class="row" style="margin-top:14px">
      <button id="btn-scan">Scanner l'intention</button>
      <button id="btn-conseils" class="ghost">Conseils (conformite)</button>
    </div>
    <div class="row" style="margin-top:8px;gap:8px">
      <button id="btn-openlegi" class="ghost" style="font-size:12px;padding:6px 12px">⊜ OpenLegi (Legifrance)</button>
      <button id="btn-notebooklm" class="ghost" style="font-size:12px;padding:6px 12px" onclick="ouvrirNotebookLM()">◫ NotebookLM</button>
    </div>
    <div id="outils-actifs-banner" class="outils-actifs hidden"></div>
    <div id="stale-notice" class="hidden" style="margin-top:8px;padding:5px 12px;border-radius:8px;
      background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.25);
      font-size:12px;color:var(--warn);display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      Intention modifiee &mdash; resultats anterieurs ci-dessous
      <button id="btn-reanalyse" style="padding:3px 10px;font-size:12px">&#8635; Refaire l'analyse</button>
    </div>
    <div id="discernement" class="hidden"></div>
    <div id="conseil-box" class="hidden"></div>
    <div id="openlegi-box" class="hidden"></div>
    <div id="scan-status"></div>
    <div class="step-nav">
      <span></span>
      <button id="to-step2" class="hidden">Composer l'ADN &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 2 : Bulles de murs (ADN) -->
  <div class="studio-step panel glass" data-step="2">
    <div class="step-title">Genere l'ADN : choisis les murs de gouvernance</div>
    <p class="step-help">L'organisme propose des murs. Garde les indispensables, ajoute ou retire selon ton projet.</p>
    <div class="bulle-zone" id="bulles-murs"></div>
    <div class="bulle-add">
      <span class="bulle-add-lbl">Ajouter un mur :</span>
      <div id="bulles-dispo" class="bulle-dispo-row"></div>
      <div class="bulle-custom-add">
        <input type="text" id="mur-custom-input" placeholder="Definir un mur personnalise...">
        <button class="ghost" id="btn-add-custom-mur">+ Ajouter</button>
      </div>
    </div>
    <div class="caps-bulles" id="bulles-caps"></div>
    <div class="step-nav">
      <button class="ghost" data-goto="1">&lsaquo; Retour</button>
      <button id="to-step3">Valider l'ADN &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 3 : Composition -->
  <div class="studio-step panel glass" data-step="3">
    <div class="step-title">Composition de l'ADN</div>
    <div id="composition-box"><div class="step-help">Chargement...</div></div>
    <div class="step-nav">
      <button class="ghost" data-goto="2">&lsaquo; Retour</button>
      <button id="to-step4">Configurer la production &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 4 : Production (capacites) -->
  <div class="studio-step panel glass" data-step="4">
    <div class="step-title">Production : capacites et puissance</div>
    <p class="step-help">Active uniquement ce dont le projet a besoin. Plus de puissance = plus de cout.</p>
    <div class="cap-choices">
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="juger" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Mode juge</span>
          <span class="cap-useful" id="useful-juger"></span>
        </div>
        <div class="cap-card-desc">Genere 2 strategies et garde la meilleure. Plus lent, plus robuste.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="deleguer" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Mode delegation</span>
          <span class="cap-useful" id="useful-deleguer"></span>
        </div>
        <div class="cap-card-desc">L'orchestrateur decompose en organes et delegue chacun a un sous-agent au tier adapte (fort/moyen/leger). Gouverne, visible en direct.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="persistance" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Persistance</span>
          <span class="cap-useful" id="useful-persistance"></span>
        </div>
        <div class="cap-card-desc">Un espace disque isole et jetable (volume dedie). Pour coffre, journal, sauvegarde.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="reseau" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Reseau</span>
          <span class="cap-useful" id="useful-reseau"></span>
        </div>
        <div class="cap-card-desc">Sortie reseau limitee a une liste blanche de domaines. Aucun autre acces.</div>
        <input type="text" id="domaines" class="hidden" placeholder="domaines autorises, separes par virgule">
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="bureau" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Bureau (RPA)</span>
          <span class="cap-useful" id="useful-bureau"></span>
        </div>
        <div class="cap-card-desc">Piloter le clavier et la souris de l'hote via l'agent local (RPA / computer-use).</div>
      </div>
    </div>
    <div class="row" style="margin-top:6px">
      <label style="color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px">
        tentatives d'auto-reparation <input type="number" id="max" value="2" min="1" max="5">
      </label>
      <span class="power-gauge" id="power-gauge"></span>
    </div>
    <div class="step-nav">
      <button class="ghost" data-goto="3">&lsaquo; Retour</button>
      <button id="btn-forger">Lancer la forge (ultracode) &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 5 : Forge en direct (SSE) -->
  <div class="studio-step panel glass" data-step="5">
    <div class="step-title">Forge en direct</div>
    <div class="forge-flow" id="forge-flow"></div>
    <div id="deleg-flow" class="deleg-flow hidden"></div>
    <div id="strategies-dual" class="strategies-dual hidden"></div>
    <div id="forge-result"></div>
    <pre id="code-creation" class="code hidden"></pre>
    <div class="step-nav">
      <button class="ghost" id="btn-recommencer">Produire</button>
      <button id="btn-voir-catalogue" class="hidden">Archiver &rsaquo;</button>
    </div>
  </div>
</div>

<!-- CERVEAUX : super-agent orchestrateur -->
<div id="section-cerveau" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:#a855f7"></span>Cerveaux</h2>
    <p>Le Cerveau coordonne les agents (Forgeron, Genealogiste, Secretaire), parle pour toi et agit.</p>
  </div>
  <div class="agent-chat-mount" data-agent="cerveau" data-titre="🧠 Le Cerveau" data-sub="Je comprends, je delegue aux agents et je synthetise. Demande-moi n'importe quoi."></div>

  <!-- Competences auto-creees par l'agent (skills vivants) -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Competences apprises (skills)</div>
      <button class="ghost" id="skills-refresh" style="font-size:12px;padding:4px 10px">Rafraichir</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Le Cerveau forge ses propres competences quand il reussit une tache reproductible. Elles deviennent invocables tout de suite.</div>
    <div id="skills-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>

  <!-- Memoire cross-session : ce que l'agent retient de toi -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Memoire de l'agent</div>
      <button class="ghost" id="mem-refresh" style="font-size:12px;padding:4px 10px">Rafraichir</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Ce que l'agent retient de toi d'une session a l'autre (preferences, projets, faits). Il s'en sert pour personnaliser ses reponses.</div>
    <div id="mem-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>

  <!-- Taches autonomes (cron : l'agent agit tout seul a intervalle) -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Taches autonomes</div>
      <button class="ghost" id="tache-add-btn" style="font-size:12px;padding:4px 10px">+ Nouvelle tache</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">L'agent agit tout seul a intervalle regulier (veille, rapport...). Tourne sur le modele local gratuit (aucun credit consomme).</div>
    <div id="tache-form" class="hidden" style="margin-bottom:12px;display:flex;flex-direction:column;gap:7px">
      <input type="text" id="tache-nom" placeholder="Nom (ex: Veille quotidienne)">
      <select id="tache-agent"><option value="cerveau">Le Cerveau</option><option value="genealogiste">Le Genealogiste</option><option value="secretaire">Le Secretaire</option></select>
      <textarea id="tache-msg" rows="2" placeholder="Que doit faire l'agent ? (ex: resume l'etat de mes creations)"></textarea>
      <div style="display:flex;gap:8px;align-items:center">
        <span style="font-size:12px;color:var(--mut)">Toutes les</span>
        <input type="number" id="tache-interval" value="60" min="5" style="width:80px"><span style="font-size:12px;color:var(--mut)">minutes (min 5)</span>
        <button id="tache-save" style="margin-left:auto;font-size:13px;padding:6px 14px">Creer</button>
      </div>
    </div>
    <div id="tache-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>
</div>

<!-- PRODUCTION -->
<div id="section-production" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-production)"></span>Production</h2>
    <p>Produits generes, valides, prets a l'emploi.</p>
  </div>
  <div class="agent-chat-mount" data-agent="genealogiste" data-titre="🧬 Le Genealogiste" data-sub="Je gere, classe et explique la genetique de tes creations."></div>
  <div id="produit-grid" class="produit-grid"></div>
  <pre id="code-view" class="hidden"></pre>
</div>

<!-- COMPTE -->
<div id="section-compte" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-compte)"></span>Compte</h2>
    <p>Ton profil, modele actif et historique de production.</p>
  </div>
  <!-- Quotas freemium : compteurs visibles -->
  <div class="panel glass" style="margin-bottom:18px" id="quotas-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Ton plan</div>
      <span id="quotas-badge"></span>
    </div>
    <div id="quotas-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
    <div id="quotas-cta" style="margin-top:12px"></div>
  </div>

  <!-- Panel Preferences toujours visible (sans connexion requise) -->
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Preferences</div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <span style="font-size:13px;color:var(--txt)">Mode sombre</span>
      <label class="dark-toggle"><input type="checkbox" id="dark-toggle-cb"></label>
    </div>
    <div style="margin-bottom:6px">
      <div style="font-size:13px;color:var(--txt);margin-bottom:8px">Autorisation agent ecran</div>
      <div class="consent-btns">
        <button class="consent-btn safe" data-level="always" data-dur="0" title="Popup avant chaque action">Toujours demander</button>
        <button class="consent-btn" data-level="sequence" data-dur="120">2 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="600">10 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="1800">30 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="3600">1 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="7200">2 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="18000">5 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="43200">12 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="86400">24 h</button>
        <button class="consent-btn danger" data-level="auto" data-dur="0" title="Aucune popup, auto-approuve tout">Auto</button>
      </div>
    </div>
    <div style="margin-top:14px;display:flex;align-items:center;gap:10px">
      <span id="agent-local-status" style="font-size:13px;color:var(--mut)">Agent local...</span>
      <button class="ghost" id="clear-chats-btn" style="font-size:12px;padding:5px 12px;margin-left:auto">Effacer tous les chats</button>
    </div>
  </div>
  <div class="agent-chat-mount" data-agent="secretaire" data-titre="📋 Le Secretaire" data-sub="Ton conseiller, administrateur et assistant au quotidien."></div>
  <div id="compte-root"></div>
</div>

<!-- ANALYSE -->
<div id="section-analyse" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-analyse)"></span>Analyse</h2>
    <p>Metriques de production, capacites utilisees, repartition tentatives.</p>
  </div>
  <div class="stat-grid" id="analyse-stats"></div>
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Auto-amelioration (l'usage nourrit le systeme)</div>
    <div id="analyse-auto"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Capacites utilisees</div>
    <div id="analyse-caps"></div>
  </div>
  <div class="panel glass">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Repartition tentatives</div>
    <div id="analyse-tentatives"></div>
  </div>
</div>

<!-- INTEGRATIONS -->
<div id="section-integrations" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-integration)"></span>Integrations</h2>
    <p>Connecte ton modele IA et tes comptes. NEOGEN les utilise dans les analyses et productions.</p>
  </div>

  <!-- Modele IA multi-provider avec switch actif -->
  <div class="panel glass" style="margin-bottom:20px">
    <div class="integ-section-label">Modele IA</div>
    <div id="integ-active-bar" style="margin-bottom:12px;font-size:13px;color:var(--mut)">
      Actif : <span id="integ-active-label" style="color:var(--txt);font-weight:600">aucun</span>
    </div>
    <div class="prov-tabs" id="prov-tabs">
      <span class="prov-tab active" data-prov="anthropic">Anthropic</span>
      <span class="prov-tab" data-prov="openai">OpenAI / GPT</span>
      <span class="prov-tab" data-prov="gemini">Gemini</span>
      <span class="prov-tab" data-prov="deepseek">DeepSeek</span>
      <span class="prov-tab" data-prov="mistral">Mistral</span>
      <span class="prov-tab" data-prov="local">Local</span>
    </div>
    <div class="integ-model-row">
      <select id="integ-model-select"></select>
      <div class="integ-key-wrap">
        <input type="password" id="integ-api-key">
        <span class="integ-model-dot" id="integ-model-dot"></span>
      </div>
      <button id="integ-save-btn">Verifier &amp; activer</button>
    </div>
    <div id="integ-status"></div>
  </div>

  <!-- Grille des categories (rendue par JS) -->
  <div id="integ-grid-dynamic" class="integ-grid"></div>

  <!-- Agent local RPA — statut + apprentissage par imitation -->
  <div class="panel glass rpa-panel" style="margin-top:20px">
    <div class="integ-section-label">Agent local RPA</div>
    <div class="rpa-status-bar" id="rpa-status-bar">
      <span class="rpa-status-dot disconnected" id="rpa-dot"></span>
      <span>
        <span class="rpa-status-label" id="rpa-label">Agent deconnecte</span><br>
        <span class="rpa-status-sub" id="rpa-sub">Lancer <code>python rpa_agent.py</code> sur la machine hote</span>
      </span>
      <span class="rpa-queue-badge" id="rpa-queue-badge" style="display:none">file: 0</span>
    </div>

    <div class="integ-section-label" style="margin-top:14px">Apprentissage continu</div>
    <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0 4px">
      <div style="font-size:13px;color:var(--txt)">NEOGEN observe et apprend tes routines tout seul
        <span style="display:block;font-size:11px;color:var(--mut);margin-top:2px">Quand une même séquence revient, elle est enregistrée automatiquement (pas besoin de cliquer « Enregistrer »).</span>
      </div>
      <label class="dark-toggle"><input type="checkbox" id="cont-learn-cb"></label>
    </div>
    <div id="cont-learn-status" style="font-size:12px;color:var(--mut);min-height:16px"></div>

    <div class="integ-section-label" style="margin-top:14px">Enregistrement manuel</div>
    <div class="imit-controls">
      <button id="btn-imit-start" class="ghost">Enregistrer</button>
      <button id="btn-imit-stop" class="ghost" style="display:none"><span class="imit-rec-dot"></span>Stopper</button>
      <button id="btn-rpa-clear" class="ghost" title="Arrêt d'urgence : vider la file RPA" style="margin-left:auto;color:var(--ko);border-color:rgba(220,38,38,.35)">Arrêt d'urgence</button>
    </div>
    <div class="imit-list" id="imit-list">
      <div style="color:var(--mut);font-size:13px;padding:10px 0">Aucun enregistrement. Clique sur « Enregistrer » pour démarrer.</div>
    </div>
  </div>
</div>

<!-- Modal Deploiement Hostinger -->
<div id="modal-deploy" style="display:none">
  <div class="deploy-modal-backdrop" onclick="if(event.target===this)fermerModalDeploy()">
    <div class="deploy-modal">
      <button class="dm-close" onclick="fermerModalDeploy()">✕</button>
      <h3>Deployer sur Hostinger</h3>
      <div class="dm-desc">Genere un pack statique (index.html) et prepare le deploiement vers ton domaine.</div>
      <div style="font-size:12px;color:var(--mut);margin-bottom:6px" id="deploy-produit-info"></div>
      <input type="text" id="deploy-domain" placeholder="ex: mon-outil.netroia.tech">
      <button id="btn-deploy-confirm" style="width:100%">Deployer</button>
      <div class="dm-log" id="deploy-log"></div>
      <div class="dm-status" id="deploy-status"></div>
    </div>
  </div>
</div>

<!-- DON -->
<div id="section-don" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-don)"></span>Soutenir NEOGEN</h2>
    <p>Chaque contribution finance le calcul, le developpement et la protection IP.</p>
  </div>
  <div style="max-width:560px;margin:0 auto">
    <div class="panel glass" style="text-align:center;padding:36px 32px;margin-bottom:16px">
      <div class="ph-icon" style="font-size:52px;margin-bottom:18px">♡</div>
      <h3 style="font-size:19px;font-weight:700;margin-bottom:10px;color:var(--txt)">NEOGEN est un projet ouvert</h3>
      <p style="color:var(--mut);font-size:14px;line-height:1.75;margin-bottom:28px">
        Un organisme logiciel autonome, aligne et auto-ameliorant.<br>
        Ton soutien fait pousser le noyau.
      </p>
      <button id="btn-don-stripe" onclick="ouvrirModalDon()"
         style="display:flex;align-items:center;justify-content:center;gap:10px;
         padding:13px 24px;border-radius:12px;cursor:pointer;width:100%;
         background:rgba(219,39,119,.12);
         border:1px solid rgba(219,39,119,.35);
         color:var(--c-don);font-size:14px;font-weight:600;
         transition:background .15s"
         onmouseover="this.style.background='rgba(219,39,119,.2)'"
         onmouseout="this.style.background='rgba(219,39,119,.12)'">
        ♡ &nbsp;Soutenir
      </button>
    </div>
    <div class="panel glass" style="padding:20px 24px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Ou va ton soutien</div>
      <div class="hist-item"><span style="font-size:16px">⚡</span><span class="hist-intention">Calcul GPU pour la generation et l'evolution</span></div>
      <div class="hist-item"><span style="font-size:16px">⊕</span><span class="hist-intention">Developpement des phases D a G (integrations, GTM, applis)</span></div>
      <div class="hist-item"><span style="font-size:16px">◈</span><span class="hist-intention">Hebergement serveur dedie et infrastructure</span></div>
    </div>
  </div>
</div>

<!-- Modal don libre -->
<div id="modal-don" style="display:none;position:fixed;inset:0;z-index:9999;
  background:rgba(15,23,42,.55);backdrop-filter:blur(6px);
  align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:18px;padding:32px 28px;max-width:380px;width:92%;
    box-shadow:0 24px 64px rgba(0,0,0,.22);position:relative">
    <button onclick="fermerModalDon()" style="position:absolute;top:14px;right:16px;
      background:none;border:none;font-size:20px;cursor:pointer;color:var(--mut);
      line-height:1;padding:2px 6px">✕</button>
    <div style="text-align:center;margin-bottom:22px">
      <div style="font-size:40px;margin-bottom:8px">♡</div>
      <h3 style="font-size:17px;font-weight:700;color:var(--txt)">Choisir un montant</h3>
      <p style="font-size:13px;color:var(--mut);margin-top:5px;line-height:1.5">Don libre. Ce que tu veux, quand tu veux.</p>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px">
      <button class="don-preset" onclick="selectMontant(1,this)">1 €</button>
      <button class="don-preset" onclick="selectMontant(10,this)">10 €</button>
      <button class="don-preset" onclick="selectMontant(20,this)">20 €</button>
      <button class="don-preset" onclick="selectMontant(50,this)">50 €</button>
      <button class="don-preset" onclick="selectMontant(100,this)">100 €</button>
      <button class="don-preset" onclick="selectMontant('custom',this)">Autre +</button>
    </div>
    <div id="don-custom-wrap" style="display:none;margin-bottom:12px">
      <input id="don-custom-input" type="number" min="1" max="9999" placeholder="Montant en EUR"
        style="width:100%;padding:9px 12px;border-radius:9px;font-size:15px;text-align:center;
        border:1px solid rgba(219,39,119,.35);outline:none;color:var(--txt)"
        oninput="donCustomVal=parseInt(this.value)||0;updateDonDisplay()">
    </div>
    <div id="don-display" style="font-size:13px;color:var(--c-don);text-align:center;
      margin-bottom:16px;min-height:20px;font-weight:600"></div>
    <button id="btn-don-confirmer" onclick="confirmerDon()"
      style="width:100%;padding:12px;border-radius:11px;font-size:14px;font-weight:600;
      background:rgba(219,39,119,.12);border:1px solid rgba(219,39,119,.4);
      color:var(--c-don);cursor:pointer;transition:background .15s"
      onmouseover="this.style.background='rgba(219,39,119,.22)'"
      onmouseout="this.style.background='rgba(219,39,119,.12)'">
      Continuer vers le paiement
    </button>
    <div id="don-modal-st" style="font-size:12px;color:var(--mut);text-align:center;margin-top:10px;min-height:16px"></div>
  </div>
</div>

<script>
/* ===== SHADER GLSL (domain-warped fBm, pastels fluides) ===== */
(function(){
  const canvas = document.getElementById('bg-canvas');
  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  if (!gl) { canvas.style.background='linear-gradient(135deg,#f0f4ff,#fef9ff,#f0fff4)'; return; }

  const vert = `attribute vec2 a;void main(){gl_Position=vec4(a,0,1);}`;

  const frag = `
precision mediump float;
uniform vec2 res;
uniform float t;
uniform float dark;

float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}

float n(vec2 p){
  vec2 i=floor(p),f=fract(p);
  f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);
}

float fbm(vec2 p){
  return .5*n(p)+.25*n(p*2.1+vec2(1.7,9.2))+.125*n(p*4.3+vec2(8.3,2.8));
}

void main(){
  vec2 uv=gl_FragCoord.xy/res;
  float tt=t*.08;

  /* Domain warping a 2 niveaux */
  vec2 q=vec2(fbm(uv+tt*.5),fbm(uv+vec2(5.2,1.3)+tt*.4));
  vec2 r=vec2(fbm(uv+1.6*q+vec2(1.7+tt*.25,9.2)),
              fbm(uv+1.6*q+vec2(8.3+tt*.18,2.8)));
  float f=fbm(uv+1.9*r);

  /* Palette vivante : violet / bleu vif / rose / corail */
  vec3 c1=vec3(.62,.42,.97); /* violet profond */
  vec3 c2=vec3(.42,.68,.98); /* bleu vif */
  vec3 c3=vec3(.97,.55,.88); /* rose */
  vec3 c4=vec3(.99,.72,.56); /* corail */

  f=clamp(f,0.,1.);
  vec3 col;
  if(f<.33)col=mix(c1,c2,f/.33);
  else if(f<.66)col=mix(c2,c3,(f-.33)/.33);
  else col=mix(c3,c4,(f-.66)/.34);

  /* Mode clair : couleurs pastel sur fond blanc.
     Mode sombre : couleurs profondes assombries sur fond nuit (glassmorphism nocturne). */
  vec3 clair=mix(vec3(1.),col,.52);
  vec3 sombre=mix(vec3(.05,.04,.12),col*.55,.40);
  col=mix(clair,sombre,dark);

  gl_FragColor=vec4(col,1.);
}`;

  function sh(type,src){
    const s=gl.createShader(type);
    gl.shaderSource(s,src);gl.compileShader(s);return s;
  }
  const prog=gl.createProgram();
  gl.attachShader(prog,sh(gl.VERTEX_SHADER,vert));
  gl.attachShader(prog,sh(gl.FRAGMENT_SHADER,frag));
  gl.linkProgram(prog);gl.useProgram(prog);

  const buf=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,buf);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
  const al=gl.getAttribLocation(prog,'a');
  gl.enableVertexAttribArray(al);
  gl.vertexAttribPointer(al,2,gl.FLOAT,false,0,0);

  const uRes=gl.getUniformLocation(prog,'res');
  const uTime=gl.getUniformLocation(prog,'t');
  const uDark=gl.getUniformLocation(prog,'dark');

  function resize(){
    canvas.width=innerWidth;canvas.height=innerHeight;
    gl.viewport(0,0,canvas.width,canvas.height);
  }
  resize();
  window.addEventListener('resize',resize);

  const start=Date.now();
  let _darkTarget=document.body.classList.contains('dark')?1:0;
  let _darkCur=_darkTarget;
  window._setShaderDark=function(v){_darkTarget=v?1:0;};
  function draw(){
    _darkCur+=(_darkTarget-_darkCur)*.08; /* transition douce */
    gl.uniform2f(uRes,canvas.width,canvas.height);
    gl.uniform1f(uTime,(Date.now()-start)/1000);
    gl.uniform1f(uDark,_darkCur);
    gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
    requestAnimationFrame(draw);
  }
  draw();
})();

/* ===== BENTO 3D : parallaxe souris + float idle ===== */
(function(){
  const plane=document.querySelector('.bento-3d');
  const stage=document.querySelector('.bento');
  if(!plane||!stage) return;
  const baseY=-16, baseX=14;        // inclinaison de repos
  let tx=baseY, ty=baseX;           // cibles
  let cx=baseY, cy=baseX;           // courantes (lerp)
  let mx=30, my=0;                  // position du reflet (%)
  let active=false, idle=0;

  stage.addEventListener('pointermove', e=>{
    const r=stage.getBoundingClientRect();
    const nx=((e.clientX-r.left)/r.width)*2-1;   // -1..1
    const ny=((e.clientY-r.top)/r.height)*2-1;
    tx=baseY + nx*15;                            // rotateY
    ty=baseX - ny*12;                            // rotateX
    mx=((e.clientX-r.left)/r.width)*100;
    my=((e.clientY-r.top)/r.height)*100;
    active=true;
  });
  stage.addEventListener('pointerleave', ()=>{ active=false; });

  function frame(){
    if(!active){                                 // derive douce au repos
      idle+=0.012;
      tx=baseY + Math.sin(idle)*5;
      ty=baseX + Math.cos(idle*0.8)*3;
    }
    cx+=(tx-cx)*0.08;
    cy+=(ty-cy)*0.08;
    plane.style.transform='rotateX('+cy.toFixed(2)+'deg) rotateY('+cx.toFixed(2)+'deg)';
    plane.style.setProperty('--mx', mx.toFixed(1)+'%');
    plane.style.setProperty('--my', my.toFixed(1)+'%');
    requestAnimationFrame(frame);
  }
  frame();
})();

/* ===== SIDEBAR : float apesanteur par item ===== */
(function(){
  const items=Array.from(document.querySelectorAll('.side-item'));
  if(!items.length)return;
  const n=items.length;
  const phase=items.map((_,i)=>i*(Math.PI*2/n));
  const hov=new Array(n).fill(false);
  const cY=new Array(n).fill(0),cX=new Array(n).fill(0);
  items.forEach((el,i)=>{
    el.addEventListener('pointerenter',()=>{hov[i]=true;});
    el.addEventListener('pointerleave',()=>{hov[i]=false;});
  });
  let t=0;
  function frame(){
    t+=0.009;
    items.forEach((el,i)=>{
      const act=hov[i]||el.classList.contains('active');
      /* actif/survol : monte sur baseline +(-3px) mais continue a respirer */
      const tY=act?-3+Math.sin(t+phase[i])*.8:Math.sin(t+phase[i])*3.5;
      /* legere derive X pour l'effet apesanteur 2D */
      const tX=act?4:Math.cos(t*.65+phase[i])*1.2;
      cY[i]+=(tY-cY[i])*.1;
      cX[i]+=(tX-cX[i])*.1;
      el.style.transform='translateY('+cY[i].toFixed(2)+'px) translateX('+cX[i].toFixed(2)+'px)';
    });
    requestAnimationFrame(frame);
  }
  frame();
})();

/* ===== SECTION BREATH : vie dans les panels et cartes ===== */
const _breath=(function(){
  const seen=new WeakSet();
  let items=[];
  let t=0;

  function add(el,ampY,ampX){
    if(seen.has(el))return;
    seen.add(el);
    el.style.willChange='transform';
    /* phase de Fibonacci (1.37 rad) : aucune synchronisation visible entre items */
    items.push({el,phase:items.length*1.37,ampY,ampX,cY:0,cX:0});
  }

  function scan(){
    /* panel formulaire : tres lent, amplitude minimale pour ne pas gener la saisie */
    document.querySelectorAll('.glass.panel').forEach(el=>add(el,1.2,.2));
    /* placeholders (pages bientot) */
    document.querySelectorAll('.placeholder.glass').forEach(el=>add(el,4,.6));
    /* icones ph-icon : lévitation plus prononcee */
    document.querySelectorAll('.ph-icon').forEach(el=>add(el,7,0));
    /* cartes produits (generees dynamiquement) */
    document.querySelectorAll('.produit-card.glass').forEach(el=>add(el,3.5,.8));
  }

  function frame(){
    t+=.008;
    /* purge les elements detaches du DOM (ex: grid.innerHTML='') */
    if(items.length)items=items.filter(o=>document.contains(o.el));
    items.forEach(o=>{
      const tY=Math.sin(t+o.phase)*o.ampY;
      const tX=Math.cos(t*.62+o.phase)*o.ampX;
      o.cY+=(tY-o.cY)*.07;
      o.cX+=(tX-o.cX)*.07;
      o.el.style.transform='translateY('+o.cY.toFixed(2)+'px) translateX('+o.cX.toFixed(2)+'px)';
    });
    requestAnimationFrame(frame);
  }

  scan();
  frame();
  return{scan};
})();

/* ===== NAVIGATION ===== */
const $=s=>document.querySelector(s);
const errMsg=x=>{if(x==null)return'';if(typeof x==='string')return x;if(x.message)return x.message;try{return JSON.stringify(x);}catch(e){return String(x);}};
const esc=s=>(s||'').replace(/[<>]/g,'');
const LABELS={creation:'Creation',production:'Production',compte:'Compte',analyse:'Analyse',integrations:'Integrations',don:'Soutenir'};

function showSection(name){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  $('#landing').style.display='none';
  const s=$('#section-'+name);if(s)s.classList.add('active');
  $('#breadcrumb').classList.add('visible');
  $('#bc-label').textContent=LABELS[name]||name;
  document.body.classList.add('in-section');
  document.querySelectorAll('.side-item').forEach(el=>el.classList.remove('active'));
  const si=$('#side-'+name);if(si)si.classList.add('active');
  history.replaceState(null,'','#'+name);
  if(name==='production')loadProduits();
  if(name==='compte')loadCompte();
  if(name==='analyse')loadAnalyse();
}
function showLanding(){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  $('#landing').style.display='';
  $('#breadcrumb').classList.remove('visible');
  document.body.classList.remove('in-section');
  document.querySelectorAll('.side-item').forEach(el=>el.classList.remove('active'));
  history.replaceState(null,'','#');
  if($('#code-view'))$('#code-view').classList.add('hidden');
}

async function health(){
  try{
    const h=await(await fetch('/health')).json();
    $('#docker-status').innerHTML='<span class="dot '+(h.docker?'on':'off')+'"></span>'+(h.docker?'Docker actif ('+h.docker_info+')':'Docker indisponible');
  }catch(e){}
}

function liste(titre,arr){
  if(!arr||!arr.length)return'';
  return'<div class="ligne"><b>'+titre+'</b><ul style="margin:4px 0 0;padding-left:18px">'+arr.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>';
}

/* ===== STUDIO A->Z — machine a etats ===== */
const MURS_LABELS={
  no_plaintext_secrets:'Aucun secret en clair',
  no_external_network:'Pas de reseau non autorise',
  no_delete_without_confirmation:'Pas de suppression sans confirmation',
  requires_auth:'Authentification requise',
  no_data_exfiltration:'Aucune exfiltration de donnees',
};
const studio={intention:'',proposition:null,murs:[],persistance:false,reseau:false,bureau:false,domaines:'',juger:false,
  deleguer:false,intentionAnalysee:'',intentionConseil:''};

function studioGoto(n){
  document.querySelectorAll('#section-creation .studio-step').forEach(s=>s.classList.toggle('active',+s.dataset.step===n));
  document.querySelectorAll('#studio-rail .srail-step').forEach(s=>{
    const k=+s.dataset.step;
    s.classList.toggle('active',k===n);
    s.classList.toggle('done',k<n);
  });
}
document.querySelectorAll('#section-creation [data-goto]').forEach(b=>b.onclick=()=>studioGoto(+b.dataset.goto));

/* --- Etape 1 : scan de l'intention --- */
$('#btn-scan').onclick=async()=>{
  const intention=$('#intention').value.trim();
  if(intention.length<3){$('#scan-status').innerHTML='<span class="tag ko">vide</span> ecris une intention.';return;}
  studio.intention=intention;
  $('#btn-scan').disabled=true;
  $('#scan-status').innerHTML="L'organisme scanne l'intention et propose un ADN...";
  // Ne pas masquer l'ancien discernement — il reste visible jusqu'aux nouveaux resultats
  try{
    const p=await(await fetch('/proposer',{method:'POST',headers:_llmHdrs(),body:JSON.stringify({intention})})).json();
    if(p.detail){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(p.detail);return;}
    studio.proposition=p;
    studio.persistance=!!p.persistance;studio.reseau=!!p.reseau;studio.bureau=!!p.bureau;
    studio.domaines=(p.domaines_proposes||[]).join(', ');
    // murs retenus initiaux = murs classes (ou murs_proposes en fallback)
    studio.murs=(p.murs_classes&&p.murs_classes.length
      ? p.murs_classes.map(m=>({cle:m.cle,label:m.label||MURS_LABELS[m.cle]||m.cle,criticite:(m.criticite||'important').toLowerCase()}))
      : (p.murs_proposes||[]).map(c=>({cle:c,label:MURS_LABELS[c]||c,criticite:'important'})));
    const d=p.discernement||{};
    let html='<div class="step-title" style="margin-top:18px">Discernement</div>';
    html+='<div class="compo-item"><span class="ci-key">Verdict</span><span>'+(d.merite_attaque?'<span class="tag ok">merite d\'y aller</span>':'<span class="tag ko">a recadrer</span>')+'</span></div>';
    html+='<div class="compo-item"><span class="ci-key">Notes</span><span>valeur '+d.valeur+' &middot; faisabilite '+d.faisabilite+' &middot; clarte '+d.clarte+'</span></div>';
    html+='<div class="compo-item"><span class="ci-key">Raison</span><span>'+esc(d.raison||'')+'</span></div>';
    if(d.reformulation)html+='<div class="compo-premiere">Reformulation suggeree : '+esc(d.reformulation)+'</div>';
    $('#discernement').innerHTML=html;$('#discernement').classList.remove('hidden');
    $('#scan-status').innerHTML='';
    $('#to-step2').classList.remove('hidden');
    studio.intentionAnalysee=intention;
    $('#stale-notice').classList.add('hidden');
    updateOutilsActifs();
    // Si OpenLegi est actif : lance automatiquement la recherche juridique
    if(_iActive('openlegi')&&$('#btn-openlegi')){
      setTimeout(()=>$('#btn-openlegi').click(),600);
    }
    renderBulles();
  }catch(e){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
  finally{$('#btn-scan').disabled=false;}
};

$('#btn-conseils').onclick=async()=>{
  const intention=$('#intention').value.trim();
  if(intention.length<3){$('#scan-status').innerHTML='<span class="tag ko">vide</span> ecris une intention.';return;}
  // Cache : meme intention + contenu existant -> juste afficher sans rappel API
  if(studio.intentionConseil===intention&&$('#conseil-box').innerHTML!==''){
    $('#conseil-box').classList.remove('hidden');return;
  }
  $('#btn-conseils').disabled=true;$('#conseil-box').classList.add('hidden');
  $('#scan-status').innerHTML='Le conseiller analyse (conformite + cadrage)...';
  try{
    const c=await(await fetch('/conseil',{method:'POST',headers:_llmHdrs(),body:JSON.stringify({intention})})).json();
    if(c.detail){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(c.detail);return;}
    const cf=c.conformite||{},cd=c.cadrage||{};
    let html='<div class="compo-premiere">';
    html+='<b>Conseil (indicatif IA)</b> &middot; risque '+esc(cf.niveau_risque||'?');
    html+='<ul style="margin:6px 0;padding-left:18px">'+(cf.points||[]).map(p=>'<li>'+esc(p)+'</li>').join('')+'</ul>';
    html+=liste('Questions cles',cd.questions_cles);
    html+=liste('Donnees a collecter',cd.donnees_a_collecter);
    html+=liste('Pieges',cd.pieges);
    html+='<div class="reform" style="margin-top:6px">'+esc(cf.avertissement||'Indicatif, confirmer par un juriste.')+'</div></div>';
    $('#conseil-box').innerHTML=html;$('#conseil-box').classList.remove('hidden');$('#scan-status').innerHTML='';
    studio.intentionConseil=intention;
  }catch(e){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
  finally{$('#btn-conseils').disabled=false;}
};

// Listener textarea : affiche le badge stale si intention modifiee apres analyse
$('#intention').addEventListener('input',()=>{
  if(!studio.intentionAnalysee)return;
  const changed=$('#intention').value.trim()!==studio.intentionAnalysee;
  $('#stale-notice').classList.toggle('hidden',!changed);
});
// Refaire l'analyse : force re-run scan (+ conseil si deja visible)
$('#btn-reanalyse').onclick=()=>{
  const hadConseil=!$('#conseil-box').classList.contains('hidden');
  studio.intentionAnalysee='';studio.intentionConseil='';
  $('#stale-notice').classList.add('hidden');
  $('#btn-scan').click();
  if(hadConseil)setTimeout(()=>$('#btn-conseils').click(),200);
};

$('#to-step2').onclick=()=>{renderBulles();studioGoto(2);};

/* --- Etape 2 : bulles de murs --- */
// mur personnalise : saisie libre
$('#btn-add-custom-mur').onclick=()=>{
  const inp=$('#mur-custom-input');const label=inp.value.trim();if(!label)return;
  studio.murs.push({cle:'custom_'+Date.now(),label,criticite:'custom'});
  inp.value='';renderBulles();
};
$('#mur-custom-input').addEventListener('keydown',e=>{if(e.key==='Enter')$('#btn-add-custom-mur').click();});
function renderBulles(){
  const zone=$('#bulles-murs');
  zone.innerHTML=studio.murs.length?'':'<span class="step-help">Aucun mur retenu. Ajoute-en ci-dessous ou continue (produit sans garde-fou explicite).</span>';
  studio.murs.forEach((m,i)=>{
    const b=document.createElement('span');
    const crit=m.criticite==='indispensable'?'indispensable':(m.criticite==='custom'?'custom':'important');
    b.className='bulle '+crit;
    b.innerHTML='<span class="bulle-crit">'+esc(m.criticite)+'</span>'+esc(m.label)+'<span class="bulle-x" title="retirer">&times;</span>';
    b.querySelector('.bulle-x').onclick=()=>{studio.murs.splice(i,1);renderBulles();};
    zone.appendChild(b);
  });
  // murs disponibles a l'ajout
  const dispo=$('#bulles-dispo');dispo.innerHTML='';
  const presents=new Set(studio.murs.map(m=>m.cle));
  Object.keys(MURS_LABELS).filter(k=>!presents.has(k)).forEach(k=>{
    const d=document.createElement('span');d.className='bulle-dispo';d.textContent=MURS_LABELS[k];
    d.onclick=()=>{studio.murs.push({cle:k,label:MURS_LABELS[k],criticite:'important'});renderBulles();};
    dispo.appendChild(d);
  });
  // capacites proposees en bulles (interactives : clic pour activer/desactiver)
  const caps=$('#bulles-caps');caps.innerHTML='';
  caps.innerHTML='<div class="compo-section-lbl" style="width:100%">Capacites accordees</div>';
  const capLabels={persistance:'Persistance (disque)',reseau:'Reseau (liste blanche)',bureau:'Bureau (RPA)'};
  ['persistance','reseau','bureau'].forEach(name=>{
    const b=document.createElement('span');
    b.className='cap-bulle'+(studio[name]?' active':'');
    b.textContent=capLabels[name];
    b.title=(studio[name]?'Cliquer pour desactiver':'Cliquer pour activer');
    b.onclick=()=>{studio[name]=!studio[name];renderBulles();};
    caps.appendChild(b);
  });
}

$('#to-step3').onclick=async()=>{
  studioGoto(3);
  const box=$('#composition-box');box.innerHTML='<div class="step-help">Composition en cours...</div>';
  try{
    const body={intention:studio.intention,murs:studio.murs.map(m=>m.cle),
      persistance:studio.persistance,reseau:studio.reseau,
      domaines_autorises:studio.domaines.split(',').map(s=>s.trim()).filter(Boolean),juger:studio.juger};
    const c=await(await fetch('/composer',{method:'POST',headers:_llmHdrs(),body:JSON.stringify(body)})).json();
    if(c.detail){box.innerHTML='<span class="tag ko">erreur</span> '+errMsg(c.detail);return;}
    let html='<div class="compo-objectif"><b>Objectif :</b> '+esc(c.objectif)+'</div>';
    html+='<div class="compo-section-lbl">Murs dans l\'ADN</div>';
    html+=(c.murs&&c.murs.length)?c.murs.map(m=>'<div class="compo-item"><span class="ci-key">'+esc(m.cle)+'</span><span>'+esc(m.explication)+'</span></div>').join(''):'<div class="step-help">Aucun mur.</div>';
    html+='<div class="compo-section-lbl">Capacites accordees</div>';
    html+=(c.capacites&&c.capacites.length)?c.capacites.map(m=>'<div class="compo-item"><span class="ci-key">'+esc(m.cle)+'</span><span>'+esc(m.explication)+'</span></div>').join(''):'<div class="step-help">Aucune (produit pur, calcul en memoire).</div>';
    html+='<div class="compo-premiere"><b>Premiere generation :</b> '+esc(c.description_premiere_generation||'')+'</div>';
    box.innerHTML=html;
  }catch(e){box.innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
};

/* --- Etape 4 : capacites + puissance --- */
$('#to-step4').onclick=()=>{
  // pre-cocher selon proposition + afficher badges utilite
  $('#persistance').checked=studio.persistance;
  $('#reseau').checked=studio.reseau;
  $('#juger').checked=studio.juger;
  $('#deleguer').checked=studio.deleguer;
  $('#domaines').value=studio.domaines;
  $('#domaines').classList.toggle('hidden',!studio.reseau);
  const p=studio.proposition||{};
  setUseful('useful-persistance',p.persistance,p.justification_persistance);
  setUseful('useful-reseau',p.reseau,p.justification_reseau);
  setUseful('useful-juger',null,'');
  setUseful('useful-deleguer',null,'');
  updatePower();
  studioGoto(4);
};
function setUseful(id,flag,just){
  const el=$('#'+id);if(!el)return;
  if(flag===null){el.className='cap-useful';el.textContent='';el.title='';return;}
  el.className='cap-useful '+(flag?'yes':'no');
  el.textContent=flag?'utile':'optionnel';
  el.title=just||'';
}
function updatePower(){
  const lvl=Math.min(3,(studio.juger?1:0)+(studio.deleguer?1:0)+($('#persistance').checked?1:0)+($('#reseau').checked?1:0));
  const dots=[0,1,2].map(i=>'<span class="power-dot'+(i<lvl?' on':'')+'"></span>').join('');
  const lbl=['minimal','modere','eleve','maximal'][lvl];
  $('#power-gauge').innerHTML='puissance / cout : '+dots+' <b style="color:var(--txt)">'+lbl+'</b>';
}
['persistance','reseau','juger','deleguer'].forEach(id=>{
  const el=$('#'+id);if(el)el.addEventListener('change',()=>{
    studio[id]=el.checked;
    if(id==='reseau')$('#domaines').classList.toggle('hidden',!el.checked);
    // Mode juge et mode delegation sont exclusifs (l'orchestrateur ne juge pas).
    if(id==='deleguer'&&el.checked&&$('#juger').checked){$('#juger').checked=false;studio.juger=false;}
    if(id==='juger'&&el.checked&&$('#deleguer').checked){$('#deleguer').checked=false;studio.deleguer=false;}
    updatePower();
  });
});

/* --- Etape 5 : forge en direct (SSE) --- */
const FORGE_LABELS={
  moteur:'Moteur LLM',decomposition:'Decomposition en organes',assemblage:'Assemblage',
  registre:'Enregistrement',
  forge_adn:'Forge de l\'ADN',adn_pret:'ADN forge',generation:'Generation du code',
  code_genere:'Code genere',jugement:'Selection de strategie',membrane:'Membrane (murs)',
  scan:'Scan statique',conteneur:'Conteneur durci',execution:'Execution',
};
let forgeSource=null;
function forgeAdd(key,label,sub,state){
  const flow=$('#forge-flow');
  let el=document.getElementById('fe-'+key);
  if(!el){
    el=document.createElement('div');el.id='fe-'+key;el.className='forge-evt';
    el.innerHTML='<span class="fe-icon"></span><span class="fe-body"><span class="fe-main"></span><span class="fe-sub"></span></span>';
    flow.appendChild(el);
  }
  el.className='forge-evt '+(state||'run');
  el.querySelector('.fe-icon').textContent=state==='ok'?'✓':(state==='ko'?'✗':'·');
  el.querySelector('.fe-main').textContent=label;
  el.querySelector('.fe-sub').textContent=sub||'';
}

$('#btn-forger').onclick=()=>{
  studio.persistance=$('#persistance').checked;studio.reseau=$('#reseau').checked;
  studio.juger=$('#juger').checked;studio.deleguer=$('#deleguer').checked;studio.domaines=$('#domaines').value;
  const max=parseInt($('#max').value)||2;
  const body={intention:studio.intention,max_tentatives:max,juger:studio.juger,
    persistance:studio.persistance,reseau:studio.reseau,
    domaines_autorises:studio.domaines.split(',').map(s=>s.trim()).filter(Boolean)};
  $('#forge-flow').innerHTML='';$('#forge-result').innerHTML='';
  $('#code-creation').classList.add('hidden');$('#btn-voir-catalogue').classList.add('hidden');
  const _sd=$('#strategies-dual');if(_sd){_sd.classList.add('hidden');_sd.innerHTML='';}
  const _df=$('#deleg-flow');if(_df){_df.classList.add('hidden');_df.innerHTML='';}
  $('#btn-forger').disabled=true;
  studioGoto(5);
  const endpoint=studio.deleguer?'/orchestrer/stream':'/fabriquer/stream';
  forgeAdd('start',studio.deleguer?'Lancement de la delegation':'Lancement de la forge','intention envoyee','run');
  fetch(endpoint,{method:'POST',headers:_llmHdrs(),body:JSON.stringify(body)})
    .then(resp=>{
      const reader=resp.body.getReader();const dec=new TextDecoder();let buf='';
      function pump(){
        return reader.read().then(({done,value})=>{
          if(done){return;}
          buf+=dec.decode(value,{stream:true});
          let idx;
          while((idx=buf.indexOf('\n\n'))>=0){
            const chunk=buf.slice(0,idx);buf=buf.slice(idx+2);
            const line=chunk.split('\n').find(l=>l.startsWith('data:'));
            if(!line)continue;
            let evt;try{evt=JSON.parse(line.slice(5).trim());}catch(e){continue;}
            handleForgeEvt(evt);
          }
          return pump();
        });
      }
      forgeAdd('start','Forge en cours','','ok');
      return pump();
    })
    .catch(e=>{forgeAdd('err','Erreur',errMsg(e),'ko');$('#btn-forger').disabled=false;});
};

function renderCandidates(candidates){
  const el=$('#strategies-dual');
  if(!el||!candidates||!candidates.length)return;
  el.classList.remove('hidden');
  el.innerHTML=candidates.map(c=>{
    const won=c.gagnant;
    const badge=won
      ?'<span class="tag ok" style="font-size:11px">retenue</span>'
      :'<span class="tag" style="font-size:11px;background:rgba(220,38,38,.1);color:var(--ko)">ecartee</span>';
    return '<div class="strat-card '+(won?'gagnant':'perdant')+'">'
      +'<div class="strat-card-head">'+badge+'<b>'+esc(c.nom)+'</b>'
      +'<span class="strat-score">score '+esc(String(c.score))+'</span></div>'
      +'<pre class="strat-code">'+esc(c.code||'')+'</pre>'
      +'</div>';
  }).join('');
}

function _slugId(s){return (s||'').replace(/[^a-zA-Z0-9_]/g,'_');}
function _delegCardHtml(o){
  return '<div class="deleg-head"><span class="deleg-icon">·</span>'
    +'<span class="deleg-name">'+esc(o.organe)+'</span></div>'
    +'<div class="deleg-role">'+esc(o.role||'')+'</div>'
    +'<div class="deleg-meta"><span class="deleg-tier '+esc(o.tier||'moyen')+'">'+esc(o.tier||'')+'</span>'
    +'<span class="deleg-model">'+esc(o.modele||'')+'</span></div>';
}
function renderDelegPlan(organes){
  const el=$('#deleg-flow');if(!el)return;
  el.classList.remove('hidden');el.innerHTML='';
  (organes||[]).forEach(o=>{
    const card=document.createElement('div');
    card.className='deleg-card attente';card.id='deleg-'+_slugId(o.organe);
    card.innerHTML=_delegCardHtml(o);
    el.appendChild(card);
  });
}
function updateDelegCard(evt){
  const el=$('#deleg-flow');if(!el)return;el.classList.remove('hidden');
  let card=document.getElementById('deleg-'+_slugId(evt.organe));
  if(!card){card=document.createElement('div');card.id='deleg-'+_slugId(evt.organe);card.innerHTML=_delegCardHtml(evt);el.appendChild(card);}
  const st=evt.statut||'en_cours';
  card.className='deleg-card '+st;
  const icon=card.querySelector('.deleg-icon');
  if(icon)icon.textContent=st==='fait'?'✓':(st==='echec'?'✗':'·');
}

function handleForgeEvt(evt){
  const s=evt.stade;
  if(s==='candidates_ready'){renderCandidates(evt.candidates);return;}
  if(s==='moteur'){forgeAdd('moteur','Moteur LLM',evt.msg||'','ok');return;}
  if(s==='plan'){renderDelegPlan(evt.organes);forgeAdd('plan','Plan de delegation',(evt.total||0)+' organes a deleguer','ok');return;}
  if(s==='sous_agent'){updateDelegCard(evt);return;}
  if(s==='fini'){
    document.querySelectorAll('#forge-flow .forge-evt.run').forEach(el=>{el.className='forge-evt ok';el.querySelector('.fe-icon').textContent='✓';});
    const tag=evt.succes?'<span class="tag ok">execute</span>':'<span class="tag ko">echec</span>';
    let html=tag+' '+esc(evt.verdict||'');
    html+='<div class="meta">'+evt.tentatives+' tentative(s) &middot; '+evt.lignes+' lignes'+(evt.produit_id?' &middot; enregistre':'')+'</div>';
    if(evt.capacites)html+='<div class="meta">capacites : '+esc(evt.capacites)+'</div>';
    if(evt.classement&&evt.classement.length)html+='<div class="meta">strategies : '+evt.classement.map(c=>esc(c[0]+' '+c[1])).join(' | ')+'</div>';
    if(evt.lecons&&evt.lecons.length)html+='<div class="lecons">'+evt.lecons.map(esc).join('\n')+'</div>';
    $('#forge-result').innerHTML=html;
    $('#btn-forger').disabled=false;
    if(evt.produit_id){
      studio.dernierProduit=evt.produit_id;
      $('#btn-voir-catalogue').classList.remove('hidden');
      fetch('/produits/'+encodeURIComponent(evt.produit_id)).then(r=>r.json()).then(prod=>{
        $('#code-creation').textContent=prod.code||'';$('#code-creation').classList.remove('hidden');
      }).catch(()=>{});
    }
    return;
  }
  if(s==='erreur'){forgeAdd('err','Erreur de forge',evt.message,'ko');$('#btn-forger').disabled=false;return;}
  const label=FORGE_LABELS[s]||s;
  const ok=evt.ok===true,ko=evt.ok===false;
  const sub=evt.msg||evt.raison||evt.dangers||(evt.lignes?evt.lignes+' lignes':'')||'';
  forgeAdd(s,label+(evt.tentative?' (tentative '+evt.tentative+')':''),sub,ok?'ok':(ko?'ko':'run'));
}

$('#btn-recommencer').onclick=()=>{
  studio.intention='';studio.proposition=null;studio.murs=[];
  studio.persistance=studio.reseau=studio.juger=studio.deleguer=false;studio.domaines='';
  studio.intentionAnalysee='';studio.intentionConseil='';
  $('#intention').value='';$('#discernement').classList.add('hidden');$('#conseil-box').classList.add('hidden');
  $('#stale-notice').classList.add('hidden');
  const _df=$('#deleg-flow');if(_df){_df.classList.add('hidden');_df.innerHTML='';}
  $('#scan-status').innerHTML='';$('#to-step2').classList.add('hidden');
  studioGoto(1);
};
$('#btn-voir-catalogue').onclick=()=>showSection('production');

async function loadProduits(){
  const d=await(await fetch('/produits')).json();
  const list=(d.produits||[]).slice().reverse();
  const grid=$('#produit-grid');grid.innerHTML='';
  if(!list.length){
    grid.innerHTML='<div class="placeholder glass"><div class="ph-icon">◻</div><h3>Aucun produit</h3><p>Va dans Creation pour fabriquer ton premier produit.</p></div>';
    return;
  }
  list.forEach(p=>{
    const card=document.createElement('div');card.className='produit-card glass';
    card.dataset.id=p.id;
    const genBadge=(p.generation&&p.generation>1)?' <span class="gen-badge">gen '+p.generation+'</span>':'';
    // Badge 3 etats : deploye (promu) > appli (promouvable) > code (basique)
    const statusBadge=p.promu
      ?'<span class="tag ok" style="margin-left:6px">deploye</span>'
      :p.promouvable
        ?'<span class="tag" style="margin-left:6px;background:rgba(8,145,178,.12);color:var(--acc)">appli</span>'
        :'<span class="tag" style="margin-left:6px;background:rgba(100,116,139,.12);color:var(--mut)">code</span>';
    // Titre en gras + description tronquee
    const titre=esc(p.intention);
    card.innerHTML='<div class="ct" style="font-size:15px;font-weight:700;color:var(--txt);margin-bottom:4px">'+titre+statusBadge+genBadge+'</div>'+
                   '<div class="cs">'+p.lignes+' lignes &middot; '+esc(p.verdict)+'</div>';
    const actions=document.createElement('div');actions.className='cactions';
    const btnCode=document.createElement('button');btnCode.className='ghost';btnCode.textContent='Code';
    btnCode.onclick=async()=>{
      const prod=await(await fetch('/produits/'+encodeURIComponent(p.id))).json();
      const cv=$('#code-view');cv.textContent=prod.code||'';cv.classList.remove('hidden');
      cv.scrollIntoView({behavior:'smooth',block:'nearest'});
    };
    actions.appendChild(btnCode);
    const btnLin=document.createElement('button');btnLin.className='ghost';btnLin.textContent='Lignee';
    btnLin.onclick=()=>openLineage(p.id,card);
    actions.appendChild(btnLin);
    if(p.promouvable){
      const btnApp=document.createElement('button');btnApp.textContent="Ouvrir l'appli";
      btnApp.onclick=async(e)=>{
        e.stopPropagation();btnApp.disabled=true;btnApp.textContent='...';
        try{const r=await(await fetch('/produits/'+encodeURIComponent(p.id)+'/promouvoir',{method:'POST'})).json();
          if(r.app)window.open(r.app,'_blank');}
        catch(err){alert(errMsg(err));}
        finally{btnApp.disabled=false;btnApp.textContent="Ouvrir l'appli";}
      };
      actions.appendChild(btnApp);
    }
    // Bouton telechargement ZIP pour tout produit execute (code fonctionnel)
    const btnDl=document.createElement('button');btnDl.className='ghost';
    btnDl.title='Telecharger le pack (main.py + README.md)';
    btnDl.textContent='Telecharger';
    btnDl.onclick=(e)=>{
      e.stopPropagation();
      const a=document.createElement('a');
      a.href='/produits/'+encodeURIComponent(p.id)+'/telecharger';
      a.download='neogen-'+p.id.slice(0,8)+'.zip';
      a.click();
    };
    actions.appendChild(btnDl);
    // Bouton deploiement Hostinger pour les produits promus
    if(p.promu){
      const btnDeploy=document.createElement('button');
      btnDeploy.textContent='Deployer';
      btnDeploy.title='Deployer sur Hostinger';
      btnDeploy.style.cssText='background:rgba(234,88,12,.12);color:var(--c-integration);border:1px solid rgba(234,88,12,.35)';
      btnDeploy.onclick=(e)=>{
        e.stopPropagation();
        ouvrirModalDeploy(p.id,p.intention);
      };
      actions.appendChild(btnDeploy);
    }
    card.appendChild(actions);grid.appendChild(card);
  });
  _breath.scan(); /* active le float sur les cartes venant d'etre injectees */
}

/* --- Genealogie (Phase 4) : arbre des generations, diff, revert, upgrade --- */
async function openLineage(produitId, cardEl){
  // Toggle : cliquer la meme carte referme la lignee
  const existing=document.querySelector('.lineage-inline');
  const sameCard=cardEl&&cardEl.classList.contains('selected');
  document.querySelectorAll('.produit-card.selected').forEach(c=>c.classList.remove('selected'));
  if(existing){existing.remove();}
  if(sameCard)return; // etait deja ouvert -> on a juste ferme
  if(cardEl)cardEl.classList.add('selected');
  const panel=document.createElement('div');
  panel.className='lineage-inline glass';
  panel.innerHTML='<div class="step-help">Chargement de la lignee...</div>';
  // Inserer apres la carte cliquee (ou a la fin de la grille si pas de carte)
  const anchor=cardEl||document.querySelector('#produit-grid');
  if(anchor)anchor.insertAdjacentElement('afterend',panel);
  if(panel)panel.scrollIntoView({behavior:'smooth',block:'nearest'});
  try{
    const d=await(await fetch('/produits/'+encodeURIComponent(produitId)+'/generations')).json();
    if(d.detail){panel.innerHTML='<span class="tag ko">erreur</span> '+errMsg(d.detail);return;}
    renderLineage(d,panel,cardEl);
  }catch(e){panel.innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
}

function _closeLineage(cardEl){
  const panel=document.querySelector('.lineage-inline');if(panel)panel.remove();
  if(cardEl)cardEl.classList.remove('selected');
  else document.querySelectorAll('.produit-card.selected').forEach(c=>c.classList.remove('selected'));
}

function renderLineage(d, el, cardEl){
  let html='<div class="lineage-head"><h3>Lignee : '+esc(d.intention||'')+'</h3>'
    +'<span class="tag">'+d.total+' generation(s)</span>'
    +'<button class="ghost" style="margin-left:auto;font-size:12px;padding:5px 11px" onclick="_closeLineage(_lineageCard)">Fermer</button></div>';
  window._lineageCard=cardEl||null;
  html+='<div class="lineage-tree">';
  (d.generations||[]).forEach(n=>{
    let delta='';
    if(n.delta){
      delta='<span class="gen-delta"><span class="add">+'+n.delta.ajouts+'</span> / <span class="del">-'+n.delta.retraits+'</span></span>';
    }
    // Diff gouvernance : murs/capacites ajoutes ou retires
    let govHtml='';
    if(n.gouvernance){
      const g=n.gouvernance;
      const parts=[];
      (g.murs_ajoutes||[]).forEach(m=>parts.push('<span class="dadd">+mur:'+esc(m)+'</span>'));
      (g.murs_retires||[]).forEach(m=>parts.push('<span class="ddel">-mur:'+esc(m)+'</span>'));
      (g.capacites_ajoutees||[]).forEach(c=>parts.push('<span class="dadd">+cap:'+esc(c)+'</span>'));
      (g.capacites_retirees||[]).forEach(c=>parts.push('<span class="ddel">-cap:'+esc(c)+'</span>'));
      if(parts.length)govHtml='<div class="gen-gov">'+parts.join(' ')+'</div>';
    }
    html+='<div class="gen-node'+(n.actif?' actif':'')+'" id="gennode-'+esc(n.id)+'">'
      +'<div class="gen-node-head"><span class="gen-num">'+n.generation+'</span>'
      +'<b>Generation '+n.generation+'</b>'
      +(n.actif?' <span class="tag ok">active</span>':'')
      +(n.promu?' <span class="tag">appli</span>':'')
      +delta+'</div>'
      +govHtml
      +'<div class="gen-meta">'+esc(n.timestamp||'')+' &middot; '+n.lignes+' lignes &middot; '+esc(n.verdict||'')+'</div>'
      +'<div class="gen-actions">'
      +'<button class="ghost" onclick="toggleDiff(\''+esc(n.id)+'\')">Voir diff</button>'
      +(n.actif?'':'<button class="ghost" onclick="revertGen(\''+esc(n.id)+'\')">Revenir ici</button>')
      +'<button onclick="upgradeGen(\''+esc(n.id)+'\',this)">Faire evoluer &rsaquo;</button>'
      +'</div>'
      +'<div class="gen-diff" id="gendiff-'+esc(n.id)+'"></div>'
      +'</div>';
  });
  html+='</div>';
  el.innerHTML=html;
}

function _colorDiff(txt){
  return txt.split('\n').map(l=>{
    const e=esc(l);
    if(l.startsWith('+')&&!l.startsWith('+++'))return '<span class="dadd">'+e+'</span>';
    if(l.startsWith('-')&&!l.startsWith('---'))return '<span class="ddel">'+e+'</span>';
    if(l.startsWith('@@')||l.startsWith('+++')||l.startsWith('---'))return '<span class="dhdr">'+e+'</span>';
    return e;
  }).join('\n');
}

async function toggleDiff(id){
  const box=document.getElementById('gendiff-'+id);if(!box)return;
  if(box.style.display==='block'){box.style.display='none';return;}
  box.style.display='block';box.textContent='diff en cours...';
  try{
    const d=await(await fetch('/produits/'+encodeURIComponent(id)+'/diff')).json();
    if(d.diff&&d.diff.trim()){box.innerHTML=_colorDiff(d.diff);}
    else{box.textContent='(aucune difference / generation d origine)';}
  }catch(e){box.textContent=errMsg(e);}
}

async function revertGen(id){
  try{
    const r=await(await fetch('/produits/'+encodeURIComponent(id)+'/revert',{method:'POST'})).json();
    if(r.ok){
      const origCard=window._lineageCard;
      const origId=origCard&&origCard.dataset&&origCard.dataset.id;
      await loadProduits();
      const freshCard=origId?document.querySelector('.produit-card[data-id="'+origId+'"]'):null;
      openLineage(origId||id,freshCard||null);
    }
  }catch(e){alert(errMsg(e));}
}

function upgradeGen(id,btn){
  if(btn){btn.disabled=true;btn.textContent='evolution en cours...';}
  const resp=fetch('/produits/'+encodeURIComponent(id)+'/upgrade',{method:'POST',headers:_llmHdrs(),body:JSON.stringify({})});
  resp.then(r=>{
    const reader=r.body.getReader();const dec=new TextDecoder();let buf='';
    function pump(){
      return reader.read().then(({done,value})=>{
        if(done){
          if(btn){btn.disabled=false;btn.textContent='Faire evoluer ›';}
          return;
        }
        buf+=dec.decode(value,{stream:true});
        let idx;
        while((idx=buf.indexOf('\n\n'))>=0){
          const chunk=buf.slice(0,idx);buf=buf.slice(idx+2);
          const line=chunk.split('\n').find(l=>l.startsWith('data:'));
          if(!line)continue;
          let evt;try{evt=JSON.parse(line.slice(5).trim());}catch(e){continue;}
          if(evt.stade==='fini'){
            if(evt.succes&&evt.produit_id){loadProduits().then(()=>{const c=document.querySelector('.produit-card[data-id="'+evt.produit_id+'"]');openLineage(evt.produit_id,c||null);});}
            else{alert('Evolution echouee : '+(evt.verdict||'echec'));}
          } else if(evt.stade==='erreur'){
            alert('Erreur : '+(evt.message||'echec'));
            if(btn){btn.disabled=false;btn.textContent='Faire evoluer ›';}
          }
        }
        return pump();
      });
    }
    return pump();
  }).catch(e=>{
    alert(errMsg(e));
    if(btn){btn.disabled=false;btn.textContent='Faire evoluer ›';}
  });
}

/* ===== DON ===== */
let donMontant=0;let donCustomVal=0;
function ouvrirModalDon(){
  donMontant=0;donCustomVal=0;
  document.querySelectorAll('.don-preset').forEach(b=>b.classList.remove('sel'));
  const cw=document.getElementById('don-custom-wrap');if(cw)cw.style.display='none';
  const ci=document.getElementById('don-custom-input');if(ci)ci.value='';
  const dd=document.getElementById('don-display');if(dd)dd.textContent='';
  const st=document.getElementById('don-modal-st');if(st)st.textContent='';
  const m=document.getElementById('modal-don');if(m)m.style.display='flex';
}
function fermerModalDon(){
  const m=document.getElementById('modal-don');if(m)m.style.display='none';
}
document.getElementById('modal-don').addEventListener('click',function(e){
  if(e.target===this)fermerModalDon();
});
function selectMontant(v,el){
  document.querySelectorAll('.don-preset').forEach(b=>b.classList.remove('sel'));
  if(el)el.classList.add('sel');
  const cw=document.getElementById('don-custom-wrap');
  const dd=document.getElementById('don-display');
  if(v==='custom'){
    donMontant=0;
    if(cw)cw.style.display='block';
    document.getElementById('don-custom-input')&&document.getElementById('don-custom-input').focus();
    if(dd)dd.textContent='';
  } else {
    donMontant=v;donCustomVal=0;
    if(cw)cw.style.display='none';
    if(dd)dd.textContent=v+' EUR selectionne';
  }
}
function updateDonDisplay(){
  const dd=document.getElementById('don-display');
  if(dd)dd.textContent=donCustomVal>0?donCustomVal+' EUR':'';
}
async function confirmerDon(){
  const montant=donMontant||donCustomVal;
  const st=document.getElementById('don-modal-st');
  if(!montant||montant<1){if(st)st.textContent='Selectionner un montant.';return;}
  const btn=document.getElementById('btn-don-confirmer');
  if(btn)btn.disabled=true;
  if(st)st.textContent='Preparation...';
  try{
    const r=await fetch('/don/checkout',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({montant})});
    const d=await r.json();
    if(d.url){window.location.href=d.url;}
    else{if(st)st.textContent='Erreur : '+(d.detail||'erreur inconnue');}
  }catch(e){if(st)st.textContent='Erreur reseau.';}
  if(btn)btn.disabled=false;
}

/* ===== NOTEBOOKLM ===== */
function ouvrirNotebookLM(){
  const intention=($('#intention')&&$('#intention').value||'').trim();
  const url='https://notebooklm.google.com'+(intention?'?hl=fr':'');
  window.open(url,'_blank');
  if(intention){
    const box=$('#openlegi-box');
    box.innerHTML='<div class="compo-premiere"><b>NotebookLM</b> : colle cette intention dans NotebookLM pour enrichir ta recherche :<br><code style="user-select:all;font-size:12px">'+esc(intention)+'</code></div>';
    box.classList.remove('hidden');
  }
}

/* ===== OPENLEGI ===== */
$('#btn-openlegi').onclick=async()=>{
  const intention=($('#intention')&&$('#intention').value||'').trim();
  if(intention.length<3){$('#scan-status').innerHTML='<span class="tag ko">vide</span> ecris une intention.';return;}
  const btn=$('#btn-openlegi'),box=$('#openlegi-box');
  btn.disabled=true;box.classList.add('hidden');
  $('#scan-status').innerHTML='Recherche sur Legifrance via OpenLegi...';
  try{
    const r=await fetch('/openlegi/conformite',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query:intention})});
    const d=await r.json();
    if(d.detail){$('#scan-status').innerHTML='<span class="tag ko">OpenLegi</span> '+errMsg(d.detail);return;}
    const res=d.resultats;
    let html='<div class="compo-premiere"><b>OpenLegi (Legifrance)</b> &middot; <span style="color:var(--mut);font-size:12px">resultats pour : '+esc(d.query||intention)+'</span><br>';
    if(typeof res==='string'){html+=esc(res);}
    else if(Array.isArray(res)){
      html+=(res.length?res.map(r2=>'<div style="margin-top:6px;padding:6px 0;border-top:1px solid rgba(15,23,42,.08)">'+esc(typeof r2==='object'?JSON.stringify(r2):r2)+'</div>').join(''):'Aucun resultat trouve.');}
    else{html+='<pre style="font-size:11px;white-space:pre-wrap;margin:6px 0">'+esc(JSON.stringify(res,null,2))+'</pre>';}
    html+='</div>';
    box.innerHTML=html;box.classList.remove('hidden');$('#scan-status').innerHTML='';
  }catch(e){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
  finally{btn.disabled=false;}
};

/* Auth helpers */
function _authToken(){return localStorage.getItem('neogen_auth_token');}
function _authHdrs(){const t=_authToken();return t?{'Authorization':'Bearer '+t}:{};}

/* Gateway helper : ajoute provider/modele/cle ACTIFS aux en-tetes de production.
   La cle vit cote client (localStorage) ; le backend la consomme par requete, jamais persistee. */
function _llmHdrs(extra){
  const h=Object.assign({'Content-Type':'application/json'},extra||{});
  const p=localStorage.getItem('neogen_active_provider');
  const m=localStorage.getItem('neogen_active_model');
  if(p&&m){
    h['X-LLM-Provider']=p;h['X-LLM-Model']=m;
    const k=localStorage.getItem('neogen_key_'+p)||'';
    if(p==='local'){ if(k)h['X-LLM-Base']=k; }   /* pour local, le champ porte l'URL de base */
    else if(k){ h['X-LLM-Key']=k; }
  }
  if(localStorage.getItem('neogen_eco')!=='0')h['X-LLM-Eco']='1';   /* mode economie ACTIF par defaut (intelligent) */
  var _t=(typeof _authToken==='function')?_authToken():null;
  if(_t)h['Authorization']='Bearer '+_t;   /* identifie l'utilisateur pour les quotas */
  return h;
}
async function _fetchMe(){
  const t=_authToken();if(!t)return null;
  try{
    const r=await fetch('/auth/me',{headers:{'Authorization':'Bearer '+t}});
    if(r.ok)return await r.json();
    localStorage.removeItem('neogen_auth_token');return null;
  }catch(e){return null;}
}

function renderCompteAuth(root){
  let mode='login';
  root.innerHTML=
    '<div class="panel glass" style="max-width:440px">'
    +'<div class="auth-tabs"><div class="auth-tab active" id="tab-login">Se connecter</div>'
    +'<div class="auth-tab" id="tab-register">Creer un compte</div></div>'
    +'<div class="auth-form">'
    +'<div class="auth-field" id="auth-name-wrap" style="display:none"><label>Nom</label>'
    +'<input type="text" id="auth-name" placeholder="Ton prenom..."></div>'
    +'<div class="auth-field"><label>Email</label>'
    +'<input type="email" id="auth-email" placeholder="ton@email.com" autocomplete="email"></div>'
    +'<div class="auth-field"><label>Mot de passe</label>'
    +'<input type="password" id="auth-pw" placeholder="..." autocomplete="current-password"></div>'
    +'<div class="auth-field" id="auth-pw2-wrap" style="display:none"><label>Confirmer</label>'
    +'<input type="password" id="auth-pw2" placeholder="..." autocomplete="new-password"></div>'
    +'<div id="auth-error" style="display:none" class="auth-error"></div>'
    +'<button id="auth-submit" style="width:100%;margin-top:4px">Se connecter</button>'
    +'</div></div>';

  const tabLogin=$('#tab-login'),tabReg=$('#tab-register');
  const nameWrap=$('#auth-name-wrap'),pw2Wrap=$('#auth-pw2-wrap');
  const submit=$('#auth-submit'),errEl=$('#auth-error');

  function switchMode(m){
    mode=m;
    tabLogin.classList.toggle('active',m==='login');
    tabReg.classList.toggle('active',m==='register');
    nameWrap.style.display=m==='register'?'flex':'none';
    pw2Wrap.style.display=m==='register'?'flex':'none';
    submit.textContent=m==='register'?'Creer mon compte':'Se connecter';
    errEl.style.display='none';
  }
  tabLogin.onclick=()=>switchMode('login');
  tabReg.onclick=()=>switchMode('register');

  async function doAuth(){
    const email=($('#auth-email').value||'').trim();
    const pw=$('#auth-pw').value||'';
    const name=($('#auth-name').value||'').trim();
    const pw2=$('#auth-pw2').value||'';
    errEl.style.display='none';
    if(!email||!pw){errEl.textContent='Email et mot de passe requis.';errEl.style.display='';return;}
    if(mode==='register'&&pw.length<6){errEl.textContent='Mot de passe trop court (6 caracteres min.).';errEl.style.display='';return;}
    if(mode==='register'&&pw!==pw2){errEl.textContent='Les mots de passe ne correspondent pas.';errEl.style.display='';return;}
    submit.disabled=true;submit.textContent='...';
    try{
      const url=mode==='login'?'/auth/login':'/auth/register';
      const body=mode==='login'?{email,password:pw}:{email,password:pw,name};
      const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const d=await r.json();
      if(!r.ok){
        errEl.textContent=d.detail||'Erreur';errEl.style.display='';
        submit.disabled=false;submit.textContent=mode==='register'?'Creer mon compte':'Se connecter';
        return;
      }
      localStorage.setItem('neogen_auth_token',d.token);
      loadCompte();
    }catch(e){
      errEl.textContent='Erreur reseau.';errEl.style.display='';
      submit.disabled=false;submit.textContent=mode==='register'?'Creer mon compte':'Se connecter';
    }
  }
  submit.onclick=doAuth;
  ['auth-email','auth-pw','auth-pw2'].forEach(id=>{
    const el=$('#'+id);if(el)el.addEventListener('keydown',e=>{if(e.key==='Enter')doAuth();});
  });
}

async function renderCompteConnecte(root,user){
  const isAdmin=!!user.is_admin;
  root.innerHTML=
    '<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="display:flex;justify-content:space-between;align-items:flex-start"><div>'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Profil</div>'
    +'<div style="font-size:17px;font-weight:700;margin-bottom:3px">'+esc(user.name)+'</div>'
    +'<div style="font-size:13px;color:var(--mut)">'+esc(user.email)+'</div>'
    +(isAdmin?'<span class="tag ok" style="margin-top:6px;display:inline-block">admin</span>':'')
    +'</div><button class="ghost" id="deconnexion-btn" style="font-size:12px;padding:6px 12px">Deconnexion</button></div></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Modele actif</div>'
    +'<div id="compte-model-info" style="font-size:14px;color:var(--txt)"></div></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Envoyer un retour a Jordan</div>'
    +'<div class="star-row" id="fb-stars">'+[1,2,3,4,5].map(i=>'<span class="star" data-v="'+i+'">&#9733;</span>').join('')+'</div>'
    +'<div style="margin-top:10px"><textarea id="fb-msg" placeholder="Dis-moi ce qui va ou ne va pas, une idee, un bug..."></textarea></div>'
    +'<div style="display:flex;align-items:center;gap:10px;margin-top:10px">'
    +'<button id="fb-submit-btn">Envoyer</button><span id="fb-status"></span></div></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Preferences</div>'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">'
    +'<span style="font-size:13px;color:var(--txt)">Mode sombre</span>'
    +'<label class="dark-toggle"><input type="checkbox" id="dark-toggle-cb"><span style="font-size:12px;color:var(--mut)"></span></label></div>'
    +'<div style="margin-bottom:6px"><div style="font-size:13px;color:var(--txt);margin-bottom:8px">Autorisation agent ecran</div>'
    +'<div class="consent-btns">'
    +'<button class="consent-btn safe" data-level="always" data-dur="0" title="Popup avant chaque action">Toujours demander</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="120" title="Autorise pour 2 minutes">2 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="600" title="Autorise pour 10 minutes">10 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="1800" title="Autorise pour 30 minutes">30 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="3600" title="Autorise pour 1 heure">1 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="7200" title="Autorise pour 2 heures">2 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="18000" title="Autorise pour 5 heures">5 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="43200" title="Autorise pour 12 heures">12 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="86400" title="Autorise pour 24 heures">24 h</button>'
    +'<button class="consent-btn danger" data-level="auto" data-dur="0" title="Aucune popup, toutes les actions passent automatiquement">Auto</button>'
    +'</div></div>'
    +'<div style="margin-top:14px;display:flex;align-items:center;gap:10px">'
    +'<span id="agent-local-status" style="font-size:13px;color:var(--mut)">Agent local...</span>'
    +'<button class="ghost" id="clear-chats-btn" style="font-size:12px;padding:5px 12px;margin-left:auto">Effacer tous les chats</button>'
    +'</div></div>'

    +'<div class="panel glass">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Historique de production</div>'
    +'<div id="compte-historique"><div style="color:var(--mut);font-size:13px">Chargement...</div></div></div>';

  const mInfo=$('#compte-model-info');
  if(mInfo){
    const ap=localStorage.getItem('neogen_active_provider'),am=localStorage.getItem('neogen_active_model');
    mInfo.innerHTML=ap&&am
      ?'<span class="tag ok">'+esc(ap)+'</span> <b>'+esc(am)+'</b>'
      :'<span class="tag ko">aucun</span>, configure dans Integrations';
  }

  // --- Dark mode ---
  const darkCb=$('#dark-toggle-cb');
  if(darkCb){
    darkCb.checked=document.body.classList.contains('dark');
    darkCb.onchange=function(){
      document.body.classList.toggle('dark',this.checked);
      localStorage.setItem('neogen_dark_mode',this.checked?'1':'0');
    };
  }

  // --- Consentement ---
  function _activateConsentBtn(lvl,dur){
    document.querySelectorAll('.consent-btn').forEach(function(b){
      var match=(b.dataset.level===lvl)&&(lvl!=='sequence'||String(b.dataset.dur)===String(dur));
      b.classList.toggle('active',match);
    });
  }
  async function loadConsentLevel(){
    var lvl='sequence',dur=120;
    try{var r=await fetch('/rpa/settings');if(r.ok){var d=await r.json();lvl=d.consent_level||'sequence';dur=d.sequence_duration||120;}}catch(e){}
    _activateConsentBtn(lvl,dur);
  }
  document.querySelectorAll('.consent-btn').forEach(function(b){
    b.onclick=async function(){
      var lvl=this.dataset.level,dur=parseInt(this.dataset.dur||'0',10);
      try{await fetch('/rpa/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent_level:lvl,sequence_duration:dur})});}catch(e){}
      _activateConsentBtn(lvl,dur);
    };
  });
  loadConsentLevel();

  // --- Agent local status ---
  const agSt=$('#agent-local-status');
  if(agSt){
    fetch('/rpa/status').then(r=>r.json()).then(function(d){
      agSt.innerHTML=d.connected
        ?'<span class="tag ok">Agent local connecte</span>'
        :'<span class="tag ko">Agent local non lance</span> <span style="font-size:11px;color:var(--mut)">Lancer rpa_agent.py sur votre machine</span>';
    }).catch(function(){agSt.innerHTML='<span class="tag ko">Agent local injoignable</span>';});
  }

  // --- Effacer tous les chats ---
  const clrAll=$('#clear-chats-btn');
  if(clrAll)clrAll.onclick=function(){
    ['cerveau','createur','genealogiste','secretaire'].forEach(function(r){localStorage.removeItem('neogen_chat_'+r);});
    document.querySelectorAll('.agent-chat-log').forEach(function(el){el.innerHTML='';});
    clrAll.textContent='Efface !';setTimeout(function(){clrAll.textContent='Effacer tous les chats';},1500);
  };

  const dBtn=$('#deconnexion-btn');
  if(dBtn)dBtn.onclick=async()=>{
    const t=_authToken();
    if(t)await fetch('/auth/logout',{method:'POST',headers:{'Authorization':'Bearer '+t}}).catch(()=>{});
    localStorage.removeItem('neogen_auth_token');
    loadCompte();
  };

  let rating=0;
  const stars=Array.from(document.querySelectorAll('#fb-stars .star'));
  function paintStars(n){stars.forEach((x,i)=>x.classList.toggle('on',i<n));}
  stars.forEach(s=>{
    s.onclick=()=>{rating=+s.dataset.v;paintStars(rating);};
    s.onmouseenter=()=>paintStars(+s.dataset.v);
    s.onmouseleave=()=>paintStars(rating);
  });

  const fbBtn=$('#fb-submit-btn'),fbSt=$('#fb-status'),fbMsg=$('#fb-msg');
  if(fbBtn)fbBtn.onclick=async()=>{
    const msg=(fbMsg.value||'').trim();
    if(!msg){fbSt.innerHTML='<span class="tag ko">message vide</span>';return;}
    fbBtn.disabled=true;fbBtn.textContent='...';
    try{
      const r=await fetch('/feedback',{method:'POST',
        headers:{'Content-Type':'application/json',..._authHdrs()},
        body:JSON.stringify({message:msg,rating:rating||null})});
      if(r.ok){
        fbSt.innerHTML='<span class="tag ok">envoye</span>';
        fbMsg.value='';rating=0;paintStars(0);
      }else fbSt.innerHTML='<span class="tag ko">erreur</span>';
    }catch(e){fbSt.innerHTML='<span class="tag ko">erreur reseau</span>';}
    fbBtn.disabled=false;fbBtn.textContent='Envoyer';
    setTimeout(()=>fbSt.innerHTML='',3000);
  };

  const hist=$('#compte-historique');
  if(hist){
    try{
      const d=await(await fetch('/produits')).json();
      const list=(d.produits||[]).slice().reverse();
      if(!list.length)hist.innerHTML='<div style="color:var(--mut);font-size:13px;padding:8px 0">Aucun produit fabrique.</div>';
      else hist.innerHTML=list.slice(0,12).map(p=>
        '<div class="hist-item">'
        +'<span class="tag '+(p.succes!==false?'ok':'ko')+'">'+(p.succes!==false?'ok':'ko')+'</span>'
        +'<span class="hist-intention">'+esc(p.intention)+'</span>'
        +'<span class="hist-meta">'+(p.lignes||'?')+' lignes</span></div>'
      ).join('');
    }catch(e){hist.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
  }
  if(window._breath)_breath.scan();
}

/* Compte */
async function loadCompte(){
  const root=$('#compte-root');if(!root)return;
  const user=await _fetchMe();
  if(user)await renderCompteConnecte(root,user);
  else renderCompteAuth(root);
}

/* Analyse */
async function loadAutoAmelioration(){
  const el=$('#analyse-auto');if(!el)return;
  try{
    const a=await(await fetch('/auto-amelioration')).json();
    if(!a.total){el.innerHTML='<div style="color:var(--mut);font-size:13px">'+esc(a.action_suggeree||'')+'</div>';return;}
    let h='<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">'
      +'<span class="tag '+(a.sain?'ok':'warn')+'">'+(a.sain?'systeme sain':a.signaux.length+' signal(aux)')+'</span>'
      +'<span style="font-size:12px;color:var(--mut)">'+Math.round((a.taux_succes||0)*100)+'% succes, '+(a.tentatives_moyennes||0)+' tentatives/creation</span></div>';
    if(a.signaux&&a.signaux.length){
      h+=a.signaux.map(function(s){
        return '<div class="hist-item" style="align-items:flex-start"><span class="tag warn" style="flex-shrink:0">'+esc(s.type)+'</span>'
          +'<span style="flex:1;font-size:13px">'+esc(s.detail)+'<br><span style="font-size:12px;color:var(--mut)">&#8594; '+esc(s.amelioration)+'</span></span></div>';
      }).join('');
    }else{
      h+='<div style="font-size:13px;color:var(--mut)">'+esc(a.action_suggeree||'')+'</div>';
    }
    el.innerHTML=h;
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
async function loadAnalyse(){
  loadAutoAmelioration();
  const statsEl=$('#analyse-stats'),capsEl=$('#analyse-caps'),tentEl=$('#analyse-tentatives');
  const empty=msg=>{if(statsEl)statsEl.innerHTML='<div style="color:var(--mut);font-size:13px">'+msg+'</div>';};
  try{
    const d=await(await fetch('/produits')).json();
    const list=d.produits||[];
    if(!list.length){empty('Fabrique ton premier produit dans Creation.');return;}
    const total=list.length;
    const succes=list.filter(p=>p.succes!==false).length;
    const lignesTotal=list.reduce((a,p)=>a+(p.lignes||0),0);
    const tentMoy=total?(list.reduce((a,p)=>a+(p.tentatives||1),0)/total).toFixed(1):0;
    if(statsEl){
      statsEl.innerHTML=[
        {val:total,lbl:'Produits'},
        {val:Math.round(succes/total*100)+'%',lbl:'Taux succes'},
        {val:lignesTotal,lbl:'Lignes generees'},
        {val:tentMoy,lbl:'Moy. tentatives'},
      ].map(s=>'<div class="stat-card glass"><div class="stat-val">'+s.val+'</div><div class="stat-lbl">'+s.lbl+'</div></div>').join('');
      if(window._breath)_breath.scan();
    }
    if(capsEl){
      capsEl.innerHTML='';
      const wP=list.filter(p=>p.capacites&&p.capacites.includes('persistance')).length;
      const wN=list.filter(p=>p.capacites&&p.capacites.includes('reseau')).length;
      const wJ=list.filter(p=>p.classement&&p.classement.length).length;
      [{lbl:'Sans capacite',n:total-wP-wN,c:'var(--acc)'},
       {lbl:'Persistance',n:wP,c:'var(--c-compte)'},
       {lbl:'Reseau',n:wN,c:'var(--c-integration)'},
       {lbl:'Mode juge',n:wJ,c:'var(--c-analyse)'}].forEach(o=>{
        const pct=total?Math.round(o.n/total*100):0;
        capsEl.innerHTML+='<div class="cap-bar-wrap"><div class="cap-bar-label"><span>'+o.lbl+'</span><span>'+o.n+'</span></div>'
          +'<div class="cap-bar"><div class="cap-bar-fill" style="width:'+pct+'%;background:'+o.c+'"></div></div></div>';
      });
    }
    if(tentEl){
      const dist={};list.forEach(p=>{const t=p.tentatives||1;dist[t]=(dist[t]||0)+1;});
      const maxN=Math.max(...Object.values(dist));
      tentEl.innerHTML=Object.entries(dist).sort((a,b)=>+a[0]-+b[0]).map(([t,n])=>
        '<div class="cap-bar-wrap"><div class="cap-bar-label"><span>'+t+' tentative'+(+t>1?'s':'')+'</span><span>'+n+'</span></div>'
        +'<div class="cap-bar"><div class="cap-bar-fill" style="width:'+Math.round(n/maxN*100)+'%"></div></div></div>'
      ).join('');
    }
  }catch(e){empty('Erreur de chargement.');}
  /* Feedbacks admin */
  const fbEx=document.getElementById('admin-feedbacks-panel');if(fbEx)fbEx.remove();
  try{
    const t=_authToken();if(!t)return;
    const fr=await fetch('/admin/feedbacks',{headers:{'Authorization':'Bearer '+t}});
    if(!fr.ok)return;
    const fd=await fr.json();
    if(!fd.total)return;
    const sec=document.querySelector('#section-analyse');if(!sec)return;
    const fbDiv=document.createElement('div');
    fbDiv.id='admin-feedbacks-panel';fbDiv.className='panel glass';fbDiv.style.marginTop='18px';
    fbDiv.innerHTML=
      '<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">'
      +'Retours utilisateurs <span class="tag ok">'+fd.total+'</span></div>'
      +fd.feedbacks.slice(0,20).map(f=>
        '<div class="fb-item"><div class="fb-header">'
        +'<span class="fb-name">'+esc(f.user_name||'Anonyme')+'</span>'
        +'<span class="fb-date">'+(f.created_at?f.created_at.slice(0,10):'')+'</span>'
        +(f.rating?'<span style="color:#f59e0b">'+'&#9733;'.repeat(f.rating)+'</span>':'')
        +'</div><div class="fb-msg">'+esc(f.message)+'</div></div>'
      ).join('');
    sec.appendChild(fbDiv);if(window._breath)_breath.scan();
  }catch(e){}
}

/* Integrations — multi-provider + switch actif + custom */
(function(){
  /* check = pre-filtre permissif uniquement (longueur). La VRAIE validation se fait
     par un appel reel via /llm/verifier -> ne jamais bloquer une cle valide a cause
     d'un format (ex: nouveau format Gemini "AQ.", anciens "AIza", "sk-ant-", etc.). */
  const PROV={
    anthropic:{label:'Anthropic',check:k=>k.trim().length>=8,
      models:['claude-fable-5','claude-opus-4-8','claude-sonnet-4-6','claude-haiku-4-5'],
      ph:'sk-ant-api03-...'},
    openai:{label:'OpenAI / GPT',check:k=>k.trim().length>=8,
      models:['gpt-4o','gpt-4o-mini','gpt-4.1','gpt-4.1-mini','o1','o3-mini'],
      ph:'sk-proj-...'},
    gemini:{label:'Gemini',check:k=>k.trim().length>=8,
      models:['gemini-2.5-pro','gemini-2.0-flash','gemini-1.5-pro','gemini-1.5-flash'],
      ph:'AIzaSy... ou AQ....'},
    deepseek:{label:'DeepSeek',check:k=>k.trim().length>=8,
      models:['deepseek-chat','deepseek-reasoner','deepseek-coder'],
      ph:'API key DeepSeek...'},
    mistral:{label:'Mistral',check:k=>k.trim().length>=8,
      models:['mistral-large-latest','mistral-small-latest','codestral-latest','open-mistral-nemo'],
      ph:'API key Mistral...'},
    local:{label:'Local (Ollama)',check:_=>true,
      models:['llama3.2','qwen2.5','mistral','phi4','gemma3','deepseek-r1:8b'],
      ph:'http://host.docker.internal:11434/v1'}
  };

  const ge=id=>document.getElementById(id);
  const tabs=document.querySelectorAll('.prov-tab');
  const modelSel=ge('integ-model-select');
  const keyIn=ge('integ-api-key');
  const dot=ge('integ-model-dot');
  const saveBtn=ge('integ-save-btn');
  const st=ge('integ-status');
  const activeLabel=ge('integ-active-label');
  if(!modelSel||!keyIn)return;

  let curProv=localStorage.getItem('neogen_provider')||'anthropic';

  function setDot(s){dot.className='integ-model-dot'+(s?' '+s:'');}

  function updateActiveLabel(){
    const p=localStorage.getItem('neogen_active_provider');
    const m=localStorage.getItem('neogen_active_model');
    const ver=(localStorage.getItem('neogen_verified_'+p)==='1')||p==='local';
    if(p&&m&&PROV[p]){
      activeLabel.textContent=PROV[p].label+' / '+m+(ver?'':' (non verifie)');
      activeLabel.style.color=ver?'var(--ok)':'#d97706';
    } else {
      activeLabel.textContent='aucun';
      activeLabel.style.color='var(--txt)';
    }
  }

  function updateTabDots(){
    tabs.forEach(t=>{
      const p=t.dataset.prov;
      const hasKey=!!localStorage.getItem('neogen_key_'+p)||p==='local';
      const verified=localStorage.getItem('neogen_verified_'+p)==='1';
      const isActive=localStorage.getItem('neogen_active_provider')===p;
      /* rouge = pas de cle ; ambre = cle non verifiee ; vert = verifiee ; vert fort = actif */
      t.style.borderColor=isActive?'var(--ok)':verified?'rgba(22,163,74,.55)':hasKey?'rgba(234,179,8,.55)':'rgba(220,38,38,.4)';
      t.style.color=isActive?'var(--ok)':t.classList.contains('active')?'#fff':'';
    });
  }

  function updateModels(prov){
    const p=PROV[prov];
    modelSel.innerHTML=p.models.map(m=>`<option value="${m}">${m}</option>`).join('');
    const saved=localStorage.getItem('neogen_model_'+prov);
    if(saved)modelSel.value=saved;
    const hasKey=!!localStorage.getItem('neogen_key_'+prov);
    keyIn.placeholder=hasKey?'cle enregistree (••••'+localStorage.getItem('neogen_key_'+prov).slice(-4)+')':p.ph;
    keyIn.value='';
    setDot(hasKey?'ok':'');
  }

  function switchProv(prov){
    curProv=prov;
    tabs.forEach(t=>{
      t.classList.toggle('active',t.dataset.prov===prov);
      /* reset inline styles sauf pour l'actif (updateTabDots le regere) */
      t.style.color='';
    });
    updateModels(prov);
    updateTabDots();
  }

  tabs.forEach(t=>t.addEventListener('click',()=>switchProv(t.dataset.prov)));

  /* Validation live */
  keyIn.addEventListener('input',()=>{
    const k=keyIn.value.trim();
    if(!k){setDot('');return;}
    setDot(PROV[curProv].check(k)?'ok':'ko');
  });

  /* Verifie qu'une cle/provider repond REELLEMENT (appel backend /llm/verifier). */
  async function _verifierCle(prov,model,key){
    const h={'Content-Type':'application/json','X-LLM-Provider':prov,'X-LLM-Model':model};
    if(prov==='local'){if(key)h['X-LLM-Base']=key;}else if(key){h['X-LLM-Key']=key;}
    try{const r=await fetch('/llm/verifier',{method:'POST',headers:h});return await r.json();}
    catch(e){return{ok:false,erreur:errMsg(e)};}
  }

  /* Verifier & activer : on n'active QUE si la cle fonctionne reellement. Sinon rouge. */
  saveBtn.onclick=async()=>{
    const m=modelSel.value;
    const p=PROV[curProv];
    let k=keyIn.value.trim();
    if(!k)k=localStorage.getItem('neogen_key_'+curProv)||'';   /* cle deja enregistree */
    // Garde freemium : 1 seul modele paye enregistre en gratuit (Ollama local toujours gratuit).
    if(curProv!=='local' && localStorage.getItem('neogen_premium')!=='1'){
      var dejaPayes=['anthropic','openai','gemini','deepseek','mistral'].filter(function(pr){return pr!==curProv && localStorage.getItem('neogen_key_'+pr);});
      if(dejaPayes.length>=1){
        st.innerHTML='<span class="tag warn">premium requis</span> Gratuit : 1 modele paye ('+esc(dejaPayes[0])+' deja enregistre) + Ollama local. Passe premium pour plusieurs modeles.';
        setDot('ko');return;
      }
    }
    if(curProv!=='local'){
      if(!k){st.innerHTML='<span class="tag ko">API absente</span> Entre ta cle API pour '+p.label+'.';setDot('ko');localStorage.removeItem('neogen_verified_'+curProv);updateTabDots();return;}
      if(!p.check(k)){st.innerHTML='<span class="tag ko">format invalide</span> Verifie la cle pour '+p.label+'.';setDot('ko');return;}
    }
    saveBtn.disabled=true;st.innerHTML='<span class="tag">verification...</span> Test de '+p.label+' / '+m;setDot('');
    const res=await _verifierCle(curProv,m,k);
    saveBtn.disabled=false;
    if(!res||!res.ok){
      localStorage.removeItem('neogen_verified_'+curProv);setDot('ko');updateTabDots();
      st.innerHTML='<span class="tag ko">activation impossible</span> '+esc((res&&res.erreur)||'la cle ne repond pas');
      return;
    }
    localStorage.setItem('neogen_provider',curProv);
    localStorage.setItem('neogen_model_'+curProv,m);
    if(keyIn.value.trim()){localStorage.setItem('neogen_key_'+curProv,k);localStorage.setItem('neogen_api_key',k);}
    localStorage.setItem('neogen_verified_'+curProv,'1');
    localStorage.setItem('neogen_active_provider',curProv);
    localStorage.setItem('neogen_active_model',m);
    localStorage.setItem('neogen_model',m);
    keyIn.value='';if(k)keyIn.placeholder='cle validee (••••'+k.slice(-4)+')';
    setDot('ok');
    updateActiveLabel();updateTabDots();
    st.innerHTML='<span class="tag ok">actif — cle validee</span> '+p.label+' / '+m;
  };

  /* Custom integrations — delegue au systeme global _loadCustom */
  function loadCustom(){if(window._loadCustom)_loadCustom();}

  window.toggleAddIntegForm=function(){
    const f=ge('integ-add-form');if(f)f.classList.toggle('hidden');
  };
  window.saveCustomInteg=function(){
    const n=ge('integ-custom-name').value.trim();
    const ep=ge('integ-custom-endpoint').value.trim();
    const k=ge('integ-custom-key').value.trim();
    if(!n)return;
    const list=JSON.parse(localStorage.getItem('neogen_integrations')||'[]');
    list.push({name:n,endpoint:ep,key:k});
    localStorage.setItem('neogen_integrations',JSON.stringify(list));
    ge('integ-custom-name').value='';
    ge('integ-custom-endpoint').value='';
    ge('integ-custom-key').value='';
    const f=ge('integ-add-form');if(f)f.classList.add('hidden');
    if(window._loadCustom)_loadCustom();
    if(window._breath)_breath.scan();
  };
  window.deleteInteg=function(i){
    const list=JSON.parse(localStorage.getItem('neogen_integrations')||'[]');
    list.splice(i,1);
    localStorage.setItem('neogen_integrations',JSON.stringify(list));
    if(window._loadCustom)_loadCustom();
  };

  /* Init */
  switchProv(curProv);
  updateActiveLabel();
})();

health();

/* ===== INTEGRATIONS — activation par integration ===== */
const INTEG_DEFS={
  openlegi:{name:'OpenLegi',icon:'⊜',cat:'Juridique & Admin',type:'key',
    keyPh:'Token openlegi.fr...',desc:'Legifrance : codes, jurisprudence, JORF — enrichit le scan et le conseil'},
  notebooklm:{name:'NotebookLM',icon:'◫',cat:'Recherche & Docs',type:'oauth',
    oauthUrl:'https://notebooklm.google.com',
    desc:'Synthese documentaire Google — sources disponibles dans Composition'},
  deerflow:{name:'DeerFlow',icon:'⊞',cat:'Recherche & Docs',type:'url',
    urlPh:'https://deerflow.netroia.tech',
    desc:'Recherche web multi-step — injecte des sources dans la forge'},
  stripe:{name:'Stripe',icon:'◆',cat:'E-commerce & Paiement',type:'server',
    desc:'Paiement — cle detectee automatiquement via credentials serveur'},
  tiktok:{name:'TikTok',icon:'◈',cat:'Reseaux sociaux',bientot:true},
  instagram:{name:'Instagram',icon:'◉',cat:'Reseaux sociaux',bientot:true},
  linkedin:{name:'LinkedIn',icon:'◎',cat:'Reseaux sociaux',bientot:true},
  magnific:{name:'Magnific',icon:'⊕',cat:'Video & Creation',bientot:true},
  youtube:{name:'YouTube',icon:'▶',cat:'Video & Creation',bientot:true},
  inpi:{name:'INPI',icon:'⊟',cat:'Juridique & Admin',bientot:true},
  shopify:{name:'Shopify',icon:'⊠',cat:'E-commerce & Paiement',bientot:true},
  n8n:{name:'n8n',icon:'⊗',cat:'Infra & Dev',bientot:true},
  github:{name:'GitHub',icon:'⊙',cat:'Infra & Dev',bientot:true},
};
const INTEG_CAT_ORDER=['Recherche & Docs','Juridique & Admin','E-commerce & Paiement','Reseaux sociaux','Video & Creation','Infra & Dev'];

function _iKey(n){return'neogen_integ_'+n;}
function _iActive(n){try{return JSON.parse(localStorage.getItem(_iKey(n))||'{}').active===true;}catch(e){return false;}}
function _iGet(n){try{return JSON.parse(localStorage.getItem(_iKey(n))||'null');}catch(e){return null;}}
function _iSet(n,d){localStorage.setItem(_iKey(n),JSON.stringify(d));}
function _iClear(n){localStorage.removeItem(_iKey(n));}
function integActives(){return Object.keys(INTEG_DEFS).filter(k=>_iActive(k));}

function _renderActivatable(k,def){
  const active=_iActive(k);
  const d=_iGet(k)||{};
  const verifie=active&&d.verifie!==false; /* server-detected ou verifie = true */
  let dot,badge;
  if(active&&verifie){dot='<span class="integ-status-dot ok"></span>';badge='<span class="badge live">actif</span>';}
  else if(active){dot='<span class="integ-status-dot warn"></span>';badge='<span class="badge warn">non verifie</span>';}
  else{dot='<span class="integ-status-dot"></span>';badge='<span class="badge soon">inactif</span>';}
  const auto=def.type==='server'?'<span style="font-size:10px;color:var(--mut);margin-left:3px">auto</span>':'';
  return '<div class="integ-activatable'+(active?' active':'')+'" id="ia-'+k+'">'
    +'<div class="integ-act-head" onclick="toggleIntegPanel(\''+k+'\')">'
    +'<span class="integ-icon">'+esc(def.icon)+'</span>'
    +'<span class="integ-act-name">'+esc(def.name)+'</span>'
    +'<span class="integ-act-right">'+dot+badge+auto
    +'<span class="ia-chev" id="chev-'+k+'">▾</span></span>'
    +'</div>'
    +'<div class="integ-act-body" id="iab-'+k+'">'
    +'<div class="iam-inner" id="iam-'+k+'"></div>'
    +'</div></div>';
}

function renderIntegGrid(serverStatus){
  const grid=document.getElementById('integ-grid-dynamic');if(!grid)return;
  if(serverStatus){
    if(serverStatus.openlegi&&!_iGet('openlegi'))_iSet('openlegi',{active:true,key:'(serveur)',source:'server'});
    if(serverStatus.stripe&&!_iGet('stripe'))_iSet('stripe',{active:true,key:'(serveur)',source:'server'});
  }
  const cats={};
  Object.entries(INTEG_DEFS).forEach(([k,def])=>{
    if(!cats[def.cat])cats[def.cat]=[];cats[def.cat].push({k,def});
  });
  grid.innerHTML='';
  const order=[...INTEG_CAT_ORDER,...Object.keys(cats).filter(c=>!INTEG_CAT_ORDER.includes(c)),'Personnalisee'];
  order.forEach(cat=>{
    const card=document.createElement('div');card.className='glass integ-category';
    if(cat==='Personnalisee'){
      card.innerHTML='<div class="integ-cat-title">Personnalisee</div>'
        +'<div id="integ-custom-list"></div>'
        +'<div class="integ-add-btn" onclick="toggleAddIntegForm()">+ Ajouter</div>'
        +'<div id="integ-add-form" class="hidden">'
        +'<input type="text" id="integ-custom-name" placeholder="Nom (ex: Airtable)">'
        +'<input type="text" id="integ-custom-endpoint" placeholder="Endpoint ou URL de l\'API">'
        +'<input type="password" id="integ-custom-key" placeholder="Cle API (optionnel)">'
        +'<button onclick="saveCustomInteg()" style="width:100%;margin-top:2px">Ajouter</button></div>';
      grid.appendChild(card);_loadCustom();return;
    }
    const items=cats[cat]||[];if(!items.length)return;
    let html='<div class="integ-cat-title">'+esc(cat)+'</div>';
    items.forEach(({k,def})=>{
      if(def.bientot){
        html+='<div class="integ-item">'
          +'<span class="integ-icon">'+esc(def.icon)+'</span>'
          +'<span class="integ-name">'+esc(def.name)+'</span>'
          +'<span class="integ-status-dot"></span>'
          +'<span class="badge soon">bientot</span></div>';
      } else {
        html+=_renderActivatable(k,def);
      }
    });
    card.innerHTML=html;grid.appendChild(card);
  });
  updateOutilsActifs();
}

window.toggleIntegPanel=function(name){
  const body=document.getElementById('iab-'+name);
  const chev=document.getElementById('chev-'+name);
  const wrap=document.getElementById('ia-'+name);
  if(!body)return;
  const wasOpen=body.classList.contains('open');
  // Fermer tous les panneaux ouverts
  document.querySelectorAll('.integ-act-body.open').forEach(el=>{
    el.classList.remove('open');
    const id=el.id.replace('iab-','');
    const c=document.getElementById('chev-'+id);if(c)c.style.transform='';
    const w=document.getElementById('ia-'+id);if(w)w.classList.remove('open');
  });
  if(wasOpen)return;
  body.classList.add('open');
  if(wrap)wrap.classList.add('open');
  if(chev)chev.style.transform='rotate(180deg)';
  // Remplir le contenu
  const def=INTEG_DEFS[name];if(!def)return;
  const form=document.getElementById('iam-'+name);if(!form)return;
  const active=_iActive(name);
  const fromServer=(_iGet(name)||{}).source==='server';
  if(active){
    let c='<div class="iam-desc">'+esc(def.desc||'')+'</div>';
    if(fromServer)c+='<p style="font-size:11px;color:var(--mut);margin-bottom:10px">Integration detectee automatiquement via credentials serveur.</p>';
    if(def.type!=='server')c+='<button class="btn-iam-deact" onclick="desactiverInteg(\''+name+'\')">Desactiver</button>';
    form.innerHTML=c;
  } else if(def.type==='key'){
    form.innerHTML='<div class="iam-desc">'+esc(def.desc)+'</div>'
      +'<input type="password" id="iam-inp-'+name+'" placeholder="'+esc(def.keyPh||'Cle API...')+'" autocomplete="off">'
      +'<button onclick="confirmerInteg(\''+name+'\')">Connecter</button>';
  } else if(def.type==='url'){
    form.innerHTML='<div class="iam-desc">'+esc(def.desc)+'</div>'
      +'<input type="text" id="iam-inp-'+name+'" placeholder="'+esc(def.urlPh||'URL...')+'">'
      +'<button onclick="confirmerInteg(\''+name+'\')">Connecter</button>';
  } else if(def.type==='oauth'){
    form.innerHTML='<div class="iam-desc">'+esc(def.desc)+'</div>'
      +'<p style="font-size:12px;color:var(--mut);margin-bottom:8px">Ouvre '+esc(def.name)+' dans un nouvel onglet, connecte-toi, puis confirme.</p>'
      +'<button onclick="window.open(\''+esc(def.oauthUrl||'')+'\',\'_blank\')" class="ghost" style="margin-bottom:5px">Ouvrir '+esc(def.name)+' ↗</button>'
      +'<button onclick="confirmerInteg(\''+name+'\')">Connexion confirmee</button>';
  } else if(def.type==='server'){
    form.innerHTML='<div class="iam-desc">'+esc(def.desc)+'</div>'
      +'<p style="font-size:11px;color:var(--mut)">Active automatiquement via les credentials serveur.</p>';
  }
};

window.confirmerInteg=async function(name){
  const def=INTEG_DEFS[name];if(!def)return;
  // Garde freemium : max 3 integrations tierces actives en gratuit.
  if(localStorage.getItem('neogen_premium')!=='1' && !_iActive(name) && integActives().length>=3){
    var st0=document.getElementById('iam-statut-'+name);
    var msg='<span class="tag warn">premium requis</span> Limite gratuite : 3 integrations. Passe premium (Compte) pour plus.';
    if(st0){st0.innerHTML=msg;}else{alert('Limite gratuite : 3 integrations actives. Passe premium pour en activer plus.');}
    return;
  }
  const inp=document.getElementById('iam-inp-'+name);
  const val=inp?inp.value.trim():'';
  const form=document.getElementById('iam-'+name);
  // Zone de statut
  let statut=document.getElementById('iam-statut-'+name);
  if(!statut&&form){statut=document.createElement('div');statut.id='iam-statut-'+name;statut.style.cssText='font-size:12px;margin-top:8px';form.appendChild(statut);}
  if(statut)statut.innerHTML='<span style="color:var(--mut)">Verification en cours...</span>';
  // Verification reelle cote serveur
  let res={ok:false,erreur:'erreur'};
  try{
    res=await(await fetch('/integrations/verifier',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({type:def.type,name:name,value:val})})).json();
  }catch(e){res={ok:false,erreur:'serveur injoignable'};}
  if(res.ok){
    _iSet(name,{active:true,key:val,source:'user',verifie:true});
    if(statut)statut.innerHTML='<span class="tag ok">verifie et actif</span>';
    renderIntegGrid();updateOutilsActifs();
  } else if(res.manuel){
    // Non verifiable automatiquement (ex oauth) : actif mais marque "non verifie"
    _iSet(name,{active:true,key:val,source:'user',verifie:false});
    if(statut)statut.innerHTML='<span class="tag warn">actif (non verifie)</span> <span style="color:var(--mut);font-size:11px">'+esc(res.erreur||'')+'</span>';
    renderIntegGrid();updateOutilsActifs();
  } else {
    // Echec : NE PAS activer, rouge + raison
    if(statut)statut.innerHTML='<span class="tag ko">activation impossible</span> <span style="color:var(--ko);font-size:11px">'+esc(res.erreur||'')+'</span>';
  }
};

window.desactiverInteg=function(name){
  _iClear(name);renderIntegGrid();updateOutilsActifs();
};

function updateOutilsActifs(){
  const banner=document.getElementById('outils-actifs-banner');if(!banner)return;
  const actives=integActives();
  if(!actives.length){banner.classList.add('hidden');return;}
  banner.classList.remove('hidden');
  banner.innerHTML='<b style="margin-right:6px">Outils actifs :</b>'
    +actives.map(k=>'<span class="outil-chip">'+esc((INTEG_DEFS[k]&&INTEG_DEFS[k].icon||'')+' '+(INTEG_DEFS[k]&&INTEG_DEFS[k].name||k))+'</span>').join('');
}

function _loadCustom(){
  const list=JSON.parse(localStorage.getItem('neogen_integrations')||'[]');
  const el=document.getElementById('integ-custom-list');if(!el)return;
  el.innerHTML=list.map((c,i)=>
    '<div class="integ-item"><span class="integ-icon">⊕</span><span class="integ-name">'+esc(c.name)+'</span>'
    +'<span class="integ-status-dot'+(c.key?' ok':'')+'"></span>'
    +'<span style="font-size:12px;color:var(--ko);cursor:pointer;font-weight:700" onclick="deleteInteg('+i+')">×</span></div>'
  ).join('');
}

// Init : detecte credentials serveur + render
(async function(){
  let srv={openlegi:false,stripe:false};
  try{srv=await(await fetch('/integrations/status')).json();}catch(e){}
  renderIntegGrid(srv);
})();

/* Hash routing : on load + bouton back navigateur */
const SECTIONS=['cerveau','creation','production','compte','analyse','integrations','don'];
function routeHash(){
  const h=location.hash.slice(1);
  if(h&&SECTIONS.includes(h))showSection(h);
}
window.addEventListener('popstate',routeHash);
routeHash();

/* ===== RPA STATUS POLLING ===== */
let _rpaInterval=null;
async function pollRpaStatus(){
  try{
    const r=await(await fetch('/rpa/status')).json();
    const dot=$('#rpa-dot'), lbl=$('#rpa-label'), sub=$('#rpa-sub'), qb=$('#rpa-queue-badge');
    if(r.connected){
      dot.className='rpa-status-dot connected';
      lbl.textContent='Agent connecte';
      sub.textContent=r.recording?'Enregistrement en cours...':'Pret a recevoir des actions';
    }else{
      dot.className='rpa-status-dot disconnected';
      lbl.textContent='Agent deconnecte';
      sub.innerHTML='Lancer <code>python rpa_agent.py</code> sur la machine hote';
    }
    if(r.queue_len>0){qb.style.display='';qb.textContent='file: '+r.queue_len;}
    else{qb.style.display='none';}
    // Sync recording button state
    const btnStart=$('#btn-imit-start'),btnStop=$('#btn-imit-stop');
    if(r.recording){btnStart.style.display='none';btnStop.style.display='';}
    else{btnStart.style.display='';btnStop.style.display='none';}
  }catch(e){}
}
_rpaInterval=setInterval(pollRpaStatus,3000);
pollRpaStatus();

/* ===== APPRENTISSAGE CONTINU ===== */
async function refreshContinuous(){
  const cb=$('#cont-learn-cb'),st=$('#cont-learn-status');
  if(!cb)return;
  try{
    const d=await(await fetch('/rpa/continuous')).json();
    cb.checked=!!d.enabled;
    if(d.enabled){
      let txt='Observation active.';
      if(d.learned&&d.learned.length)txt+=' '+d.learned.length+' routine(s) apprise(s) automatiquement.';
      else txt+=' En attente d\'une séquence répétée...';
      st.textContent=txt;
    }else st.textContent='';
  }catch(e){}
}
(function(){
  const cb=$('#cont-learn-cb');
  if(cb)cb.onchange=async function(){
    var self=this;
    try{
      var r=await fetch('/rpa/continuous',{method:'POST',headers:{'Content-Type':'application/json',..._authHdrs()},body:JSON.stringify({enabled:self.checked})});
      if(!r.ok){
        var d={};try{d=await r.json();}catch(e){}
        self.checked=false;   // refus -> on remet le toggle a off
        var st=$('#cont-learn-status');if(st)st.innerHTML='<span class="tag warn">premium requis</span> '+esc(d.detail||'Reserve a la version premium.');
        return;
      }
    }catch(e){self.checked=false;}
    refreshContinuous();if(window.loadImitationList)loadImitationList();
  };
  refreshContinuous();
  setInterval(refreshContinuous,5000);
})();

/* ===== IMITATION RECORDING UI ===== */
$('#btn-imit-start').onclick=async()=>{
  try{
    await fetch('/rpa/record/start',{method:'POST'});
    $('#btn-imit-start').style.display='none';
    $('#btn-imit-stop').style.display='';
  }catch(e){alert('Erreur : '+errMsg(e));}
};

$('#btn-imit-stop').onclick=async()=>{
  const name=prompt('Nom de l\'enregistrement :','sequence_'+Date.now());
  if(!name)return;
  try{
    const r=await(await fetch('/rpa/record/stop',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name})})).json();
    if(r.detail){alert(errMsg(r.detail));return;}
    $('#btn-imit-start').style.display='';
    $('#btn-imit-stop').style.display='none';
    loadImitationList();
  }catch(e){alert('Erreur : '+errMsg(e));}
};

$('#btn-rpa-clear').onclick=async()=>{
  if(!confirm('Arrêt d\'urgence : vider toute la file RPA ?'))return;
  try{
    const r=await(await fetch('/rpa/clear',{method:'POST'})).json();
    alert('File videe : '+r.cleared+' action(s) annulee(s).');
    pollRpaStatus();
  }catch(e){alert('Erreur : '+errMsg(e));}
};

async function loadImitationList(){
  const el=$('#imit-list');if(!el)return;
  try{
    const r=await(await fetch('/rpa/recordings')).json();
    const recs=r.recordings||[];
    if(!recs.length){
      el.innerHTML='<div style="color:var(--mut);font-size:13px;padding:10px 0">Aucun enregistrement. Clique sur « Enregistrer » pour demarrer.</div>';
      return;
    }
    el.innerHTML=recs.map(rec=>
      '<div class="imit-item">'
      +'<span class="imit-item-name">'+esc(rec.name)+'</span>'
      +'<span class="imit-item-meta">'+rec.steps+' etapes &middot; '+esc(rec.created_at||'')+'</span>'
      +'<span class="imit-item-actions">'
      +'<button class="ghost" onclick="replayImitation(\''+esc(rec.id)+'\')">Rejouer</button>'
      +'<button class="ghost" style="color:var(--ko);border-color:rgba(220,38,38,.3)" onclick="deleteImitation(\''+esc(rec.id)+'\')">×</button>'
      +'</span></div>'
    ).join('');
  }catch(e){el.innerHTML='<div style="color:var(--ko);font-size:13px">Erreur de chargement.</div>';}
}

window.replayImitation=async function(id){
  if(!confirm('Rejouer cette sequence ? L\'agent local executera chaque action avec votre consentement.'))return;
  try{
    const r=await(await fetch('/rpa/recordings/'+encodeURIComponent(id)+'/replay',{method:'POST'})).json();
    if(r.ids)alert(r.ids.length+' action(s) ajoutee(s) a la file RPA.');
    pollRpaStatus();
  }catch(e){alert('Erreur : '+errMsg(e));}
};

window.deleteImitation=async function(id){
  if(!confirm('Supprimer cet enregistrement ?'))return;
  try{
    await fetch('/rpa/recordings/'+encodeURIComponent(id),{method:'DELETE'});
    loadImitationList();
  }catch(e){alert('Erreur : '+errMsg(e));}
};

// Load imitation list on integrations section
const _origShowSection=showSection;
showSection=function(name){
  _origShowSection(name);
  if(name==='integrations'){loadImitationList();pollRpaStatus();}
  if(name==='cerveau'&&window.loadSkills){loadSkills();if(window.loadMemoire)loadMemoire();if(window.loadTaches)loadTaches();}
};

/* ===== DEPLOY MODAL (Hostinger) ===== */
let _deployProduitId=null;
function ouvrirModalDeploy(produitId,intention){
  _deployProduitId=produitId;
  const info=$('#deploy-produit-info');
  if(info)info.textContent='Produit : '+esc(intention||produitId);
  const inp=$('#deploy-domain');if(inp)inp.value='';
  const log=$('#deploy-log');if(log){log.style.display='none';log.textContent='';}
  const st=$('#deploy-status');if(st)st.textContent='';
  const btn=$('#btn-deploy-confirm');if(btn)btn.disabled=false;
  const m=$('#modal-deploy');if(m)m.style.display='block';
}
function fermerModalDeploy(){
  const m=$('#modal-deploy');if(m)m.style.display='none';
  _deployProduitId=null;
}

$('#btn-deploy-confirm').onclick=async()=>{
  const domain=($('#deploy-domain').value||'').trim();
  const st=$('#deploy-status'),log=$('#deploy-log'),btn=$('#btn-deploy-confirm');
  if(!domain){if(st)st.innerHTML='<span class="tag ko">domaine requis</span>';return;}
  if(!_deployProduitId){if(st)st.innerHTML='<span class="tag ko">aucun produit selectionne</span>';return;}
  btn.disabled=true;
  if(st)st.innerHTML='Preparation du pack...';
  if(log){log.style.display='block';log.textContent='[deploiement] Demarrage...\n';}
  try{
    const r=await fetch('/produits/'+encodeURIComponent(_deployProduitId)+'/deploy',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({domain})
    });
    const d=await r.json();
    if(!r.ok){
      if(st)st.innerHTML='<span class="tag ko">erreur</span> '+errMsg(d.detail||d);
      if(log)log.textContent+='[erreur] '+errMsg(d.detail||d)+'\n';
      btn.disabled=false;return;
    }
    if(log)log.textContent+='[ok] '+esc(d.message||'Pack genere.')+'\n';
    if(d.archive_path){
      if(log)log.textContent+='[archive] '+esc(d.archive_path)+'\n';
    }
    if(d.instructions){
      if(log)log.textContent+='[info] '+esc(d.instructions)+'\n';
    }
    if(st)st.innerHTML='<span class="tag ok">pack pret</span> Archive generee. Deploiement a finaliser via Hostinger.';
    btn.disabled=false;
    btn.textContent='Fermer';
    btn.onclick=()=>{fermerModalDeploy();btn.textContent='Deployer';btn.onclick=arguments.callee;};
  }catch(e){
    if(st)st.innerHTML='<span class="tag ko">erreur reseau</span>';
    if(log)log.textContent+='[erreur] '+errMsg(e)+'\n';
    btn.disabled=false;
  }
};

/* ===== AGENTS CONVERSATIONNELS (chat -> outils -> reponse, multi-provider) ===== */
/* Convertit un bloc de tableau markdown (lignes |...|) en <table> HTML. */
function _mdTable(lines){
  const row=l=>l.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
  const head=row(lines[0]);
  const body=lines.slice(2).map(row);
  let h='<table class="ac-tbl"><thead><tr>'+head.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';
  body.forEach(r=>{h+='<tr>'+r.map(c=>'<td>'+c+'</td>').join('')+'</tr>';});
  return h+'</tbody></table>';
}
function _mdLite(t){
  let s=esc(t);
  // Tableaux : detecter les blocs |..| avec ligne de separation |---|---| (avant le traitement \n)
  const ls=s.split('\n');const out=[];let i=0;
  while(i<ls.length){
    if(/^\s*\|.*\|\s*$/.test(ls[i])&&i+1<ls.length&&/^\s*\|[\s:|-]+\|\s*$/.test(ls[i+1])){
      let j=i+2;while(j<ls.length&&/^\s*\|.*\|\s*$/.test(ls[j]))j++;
      out.push(_mdTable(ls.slice(i,j)));i=j;
    } else {out.push(ls[i]);i++;}
  }
  s=out.join('\n');
  s=s.replace(/^#{1,4}\s+(.*)$/gm,'<h3>$1</h3>');
  s=s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/^\s*[-*]\s+(.*)$/gm,'<li>$1</li>');
  s=s.replace(/(?:<li>[\s\S]*?<\/li>)+/g,m=>'<ul>'+m+'</ul>');
  s=s.replace(/\n/g,'<br>');
  s=s.replace(/<\/ul><br>/g,'</ul>').replace(/<br>(<h3>)/g,'$1').replace(/(<\/h3>)<br>/g,'$1');
  // Nettoyer les <br> parasites autour des tableaux
  s=s.replace(/<\/table><br>/g,'</table>').replace(/<br>(<table)/g,'$1');
  return s;
}
function buildChat(mount){
  const role=mount.dataset.agent;
  const titre=mount.dataset.titre||role;
  const sub=mount.dataset.sub||'';
  mount.classList.add('agent-chat','panel','glass');
  mount.innerHTML=
    '<div class="agent-chat-head"><span class="agent-chat-dot"></span><b>'+esc(titre)+'</b>'
    +'<span class="agent-chat-sub">'+esc(sub)+'</span>'
    +'<label class="eco-toggle" id="aceco-'+role+'" title="Mode economie : choisit le modele le plus econome selon ta demande (moins de tokens)">'
    +'<input type="checkbox" id="ececb-'+role+'"><span>&#127793; Eco</span></label>'
    +'<button class="agent-chat-clear" id="acclr-'+role+'" title="Effacer la conversation">&#128465;</button></div>'
    +'<div class="agent-chat-log" id="aclog-'+role+'"></div>'
    +'<div class="agent-chat-input"><textarea id="acin-'+role+'" rows="1" placeholder="Parler a '+esc(titre)+'..."></textarea>'
    +'<button class="agent-chat-send" id="acsend-'+role+'">Envoyer</button></div>';
  const log=mount.querySelector('#aclog-'+role);
  const inp=mount.querySelector('#acin-'+role);
  const btn=mount.querySelector('#acsend-'+role);
  const clr=mount.querySelector('#acclr-'+role);
  const ecocb=mount.querySelector('#ececb-'+role);
  if(ecocb){
    ecocb.checked=localStorage.getItem('neogen_eco')!=='0';   /* actif par defaut */
    ecocb.onchange=function(){localStorage.setItem('neogen_eco',this.checked?'1':'0');
      document.querySelectorAll('[id^="ececb-"]').forEach(function(c){c.checked=ecocb.checked;});};
  }
  const KEY='neogen_chat_'+role;
  let hist=[];try{hist=JSON.parse(localStorage.getItem(KEY)||'[]');}catch(e){hist=[];}
  function add(cls,html){const d=document.createElement('div');d.className=cls;d.innerHTML=html;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
  function _save(){try{localStorage.setItem(KEY,JSON.stringify(hist.slice(-40)));}catch(e){}}
  hist.forEach(function(m){if(m.role==='user')add('ac-msg user',esc(m.content));else add('ac-msg agent','<div class="ac-md">'+_mdLite(m.content)+'</div>');});
  if(clr)clr.onclick=function(){hist=[];_save();log.innerHTML='';};
  async function envoyer(){
    const msg=(inp.value||'').trim();if(!msg)return;
    inp.value='';inp.style.height='auto';btn.disabled=true;
    add('ac-msg user',esc(msg));
    let derniereReponse='';let forgeLine=null;
    try{
      const resp=await fetch('/agent/'+role+'/chat/stream',{method:'POST',headers:_llmHdrs(),body:JSON.stringify({message:msg,historique:hist})});
      if(!resp.ok||!resp.body){var dd='';try{dd=(await resp.json()).detail||'';}catch(e){}add('ac-trace action','&#9888; '+esc(dd||('erreur '+resp.status)));btn.disabled=false;return;}
      const reader=resp.body.getReader();const dec=new TextDecoder();let buf='';
      while(true){
        const {done,value}=await reader.read();if(done)break;
        buf+=dec.decode(value,{stream:true});
        let idx;
        while((idx=buf.indexOf('\n\n'))>=0){
          const chunk=buf.slice(0,idx);buf=buf.slice(idx+2);
          if(!chunk.startsWith('data: '))continue;
          let evt;try{evt=JSON.parse(chunk.slice(6));}catch(e){continue;}
          if(evt.type==='eco'){add('ac-trace','&#127793; eco : modele '+esc(evt.tier||'')+' ('+esc(evt.raison||'')+')');}
          else if(evt.type==='pensee'){add('ac-trace','&#128173; '+esc(evt.texte||''));}
          else if(evt.type==='action'){add('ac-trace action','&#128295; '+esc(evt.outil||'')+' '+esc(JSON.stringify(evt.parametres||{})));}
          else if(evt.type==='observation'){add('ac-trace','&#8594; '+esc((evt.texte||'').slice(0,240)));}
          else if(evt.type==='delegation'){add('ac-trace deleg','&#129504; &#8594; '+esc(evt.vers||'')+' : '+esc(evt.mission||''));}
          else if(evt.type==='forge'){var ft='&#9881; forge : '+esc(((evt.stade||'')+' '+(evt.msg||evt.message||'')).trim()).slice(0,180);if(!forgeLine){forgeLine=add('ac-trace action',ft);}else{forgeLine.innerHTML=ft;log.scrollTop=log.scrollHeight;}}
          else if(evt.type==='reponse'){var _rt=evt.texte||'';var _isStep=_rt.trimStart().startsWith('{')&&['"outil"','"pensee"','"arguments"'].filter(function(k){return _rt.includes(k);}).length>=2;if(_isStep){add('ac-trace action','&#9888; Reponse illisible (petit modele). Reformule ta demande.');}else{derniereReponse=_rt;if(_rt)add('ac-msg agent','<div class="ac-md">'+_mdLite(_rt)+'</div>');}}

          else if(evt.type==='erreur'){add('ac-trace action','&#9888; '+esc(evt.message||''));}
        }
      }
      if(derniereReponse){hist.push({role:'user',content:msg});hist.push({role:'assistant',content:derniereReponse});_save();}
    }catch(e){add('ac-trace action','&#9888; '+errMsg(e));}
    finally{btn.disabled=false;inp.focus();}
  }
  btn.onclick=envoyer;
  inp.addEventListener('input',()=>{inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,130)+'px';});
  inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();envoyer();}});
}
document.querySelectorAll('.agent-chat-mount').forEach(buildChat);

// ===== PREFERENCES (dark mode + consentement + agent local) =====
// Dark mode persistant au chargement
if(localStorage.getItem('neogen_dark_mode')==='1'){
  document.body.classList.add('dark');
  if(window._setShaderDark)window._setShaderDark(true);
}

async function _confirmerPremiumRetour(){
  // Au retour de Stripe : success_url = #compte?premium_session=cs_xxx
  var h=location.hash||'';
  var m=h.match(/premium_session=([^&]+)/);
  if(!m)return;
  var t=(typeof _authToken==='function')?_authToken():null;
  if(!t)return;
  try{
    var r=await fetch('/premium/confirmer',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({session_id:m[1]})});
    var d=await r.json();
    if(d.premium){alert(d.essai?'Essai premium 7 jours active ! Acces illimite. Tu seras debite apres l\'essai (annulable avant).':'Bienvenue en premium ! Acces illimite debloque.');}
  }catch(e){}
  // Nettoie le hash pour eviter de reconfirmer
  location.hash='#compte';
}
async function loadQuotas(){
  await _confirmerPremiumRetour();
  var list=document.getElementById('quotas-list'),badge=document.getElementById('quotas-badge'),cta=document.getElementById('quotas-cta');
  if(!list)return;
  try{
    var d=await(await fetch('/quotas/me',{headers:_authHdrs?_authHdrs():{}})).json();
    localStorage.setItem('neogen_premium',d.premium?'1':'0');   /* cache pour les gardes UI */
    if(badge)badge.innerHTML=d.premium?'<span class="tag ok">Premium</span>':'<span class="tag">Gratuit</span>';
    if(d.premium){
      list.innerHTML='<div style="font-size:13px;color:var(--ok)">&#10003; Acces illimite a toutes les fonctions.</div>';
      if(cta)cta.innerHTML='';
      return;
    }
    if(!d.connecte){
      list.innerHTML='<div style="font-size:13px;color:var(--mut)">Connecte-toi (plus bas) pour suivre tes quotas et debloquer le plan gratuit : 5 creations, 2 mode juge, 3 integrations.</div>';
      if(cta)cta.innerHTML='';
      return;
    }
    list.innerHTML=(d.quotas||[]).map(function(q){
      var pct=q.limite?Math.min(100,Math.round(q.utilise/q.limite*100)):0;
      var coul=q.reste===0?'var(--ko)':(q.reste<=1?'var(--warn)':'var(--ok)');
      return '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px">'
        +'<span>'+esc(q.libelle)+'</span><span style="color:'+coul+';font-weight:600">'+q.utilise+' / '+q.limite+'</span></div>'
        +'<div style="height:6px;border-radius:99px;background:rgba(100,116,139,.2);overflow:hidden"><div style="height:100%;width:'+pct+'%;background:'+coul+';transition:width .3s"></div></div></div>';
    }).join('')
      +'<div style="font-size:11px;color:var(--mut);margin-top:8px">Reserve premium : deploiement, apprentissage continu, delegation complete.</div>';
    if(cta)cta.innerHTML='<div style="font-size:12px;color:var(--mut);margin-bottom:6px">Passer premium (illimite) &#8212; <b style="color:var(--ok)">7 jours d\'essai gratuit</b> :</div>'
      +'<div style="display:flex;gap:8px">'
      +'<button id="premium-mensuel" style="flex:1">Mensuel<br><span style="font-size:11px;opacity:.85">14,99&#8364;/mois</span></button>'
      +'<button id="premium-annuel" style="flex:1">Annuel <span style="font-size:11px;opacity:.85">-30%</span><br><span style="font-size:11px;opacity:.85">125,90&#8364;/an</span></button></div>'
      +'<div style="font-size:11px;color:var(--mut);margin-top:6px">Essai 7j, sans engagement. CB demandee, debitee seulement apres l\'essai. Annulable a tout moment.</div>';
    async function _passerPremium(plan,btn){
      var t=(typeof _authToken==='function')?_authToken():null;
      if(!t){alert('Connecte-toi d\'abord (plus bas) pour passer premium.');return;}
      var old=btn.textContent;btn.disabled=true;btn.textContent='Redirection...';
      try{
        var r=await fetch('/premium/checkout',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({plan:plan})});
        var d=await r.json();
        if(r.ok&&d.url){window.location.href=d.url;}
        else{alert(d.detail||'Paiement indisponible.');btn.disabled=false;btn.textContent=old;}
      }catch(e){alert('Erreur reseau.');btn.disabled=false;btn.textContent=old;}
    }
    var pm=document.getElementById('premium-mensuel'),pa=document.getElementById('premium-annuel');
    if(pm)pm.onclick=function(){_passerPremium('mensuel',pm);};
    if(pa)pa.onclick=function(){_passerPremium('annuel',pa);};
  }catch(e){list.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
function _initPreferences(){
  loadQuotas();
  // Dark mode toggle
  var cb=document.getElementById('dark-toggle-cb');
  if(cb){
    cb.checked=document.body.classList.contains('dark');
    cb.onchange=function(){
      document.body.classList.toggle('dark',this.checked);
      localStorage.setItem('neogen_dark_mode',this.checked?'1':'0');
      if(window._setShaderDark)window._setShaderDark(this.checked);
    };
  }
  // Consentement
  function _activateConsentBtn(lvl,dur){
    document.querySelectorAll('.consent-btn').forEach(function(b){
      var match=(b.dataset.level===lvl)&&(lvl!=='sequence'||String(b.dataset.dur)===String(dur));
      b.classList.toggle('active',match);
    });
  }
  fetch('/rpa/settings').then(function(r){return r.json();}).then(function(d){
    _activateConsentBtn(d.consent_level||'sequence',d.sequence_duration||120);
  }).catch(function(){});
  document.querySelectorAll('.consent-btn').forEach(function(b){
    b.onclick=function(){
      var lvl=this.dataset.level,dur=parseInt(this.dataset.dur||'0',10);
      fetch('/rpa/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent_level:lvl,sequence_duration:dur})}).catch(function(){});
      _activateConsentBtn(lvl,dur);
    };
  });
  // Agent local status
  var st=document.getElementById('agent-local-status');
  if(st){
    fetch('/rpa/status').then(function(r){return r.json();}).then(function(d){
      st.innerHTML=d.connected?'<span class="tag ok">Agent local connecte</span>':'<span class="tag ko">Agent local non lance</span> <span style="font-size:11px;color:var(--mut)">Lancer rpa_agent.py sur votre machine</span>';
    }).catch(function(){st.innerHTML='<span class="tag ko">Agent local injoignable</span>';});
  }
  // Effacer tous les chats
  var clr=document.getElementById('clear-chats-btn');
  if(clr)clr.onclick=function(){
    ['cerveau','createur','genealogiste','secretaire'].forEach(function(r){localStorage.removeItem('neogen_chat_'+r);});
    document.querySelectorAll('.agent-chat-log').forEach(function(el){el.innerHTML='';});
    clr.textContent='Efface !';setTimeout(function(){clr.textContent='Effacer tous les chats';},1500);
  };
}
// Lancer au chargement + quand on arrive sur Compte
document.addEventListener('DOMContentLoaded',_initPreferences);
_initPreferences();

// ===== COMPETENCES (skills) auto-creees =====
async function loadSkills(){
  const el=document.getElementById('skills-list');if(!el)return;
  try{
    const d=await(await fetch('/skills')).json();
    const list=d.skills||[];
    if(!list.length){el.innerHTML='<div style="color:var(--mut);font-size:13px">Aucune competence apprise pour le moment. Demande au Cerveau d\'accomplir une tache reproductible, il la cristallisera.</div>';return;}
    el.innerHTML=list.map(function(s){
      return '<div class="hist-item" style="align-items:flex-start">'
        +'<span class="tag ok" style="flex-shrink:0">'+esc(s.nom)+'</span>'
        +'<span style="flex:1"><b style="font-size:13px">'+esc(s.titre||s.nom)+'</b>'
        +(s.auto?' <span class="badge live" style="font-size:9px">auto</span>':'')
        +'<br><span style="font-size:12px;color:var(--mut)">'+esc(s.description||'')+'</span>'
        +(s.outils&&s.outils.length?'<br><span style="font-size:11px;color:var(--mut)">outils: '+esc(s.outils.join(', '))+'</span>':'')
        +'</span>'
        +'<span style="color:var(--ko);cursor:pointer;font-weight:700;flex-shrink:0" title="Supprimer" onclick="deleteSkill(\''+esc(s.nom)+'\')">&times;</span>'
        +'</div>';
    }).join('');
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
window.deleteSkill=async function(nom){
  try{await fetch('/skills/'+encodeURIComponent(nom),{method:'DELETE'});}catch(e){}
  loadSkills();
};
(function(){
  const btn=document.getElementById('skills-refresh');
  if(btn)btn.onclick=loadSkills;
  loadSkills();
})();

// ===== MEMOIRE cross-session =====
async function loadMemoire(){
  const el=document.getElementById('mem-list');if(!el)return;
  try{
    const d=await(await fetch('/memoire')).json();
    const list=d.memoires||[];
    if(!list.length){el.innerHTML='<div style="color:var(--mut);font-size:13px">L\'agent ne se souvient de rien pour le moment. Dis-lui qui tu es, tes preferences, tes projets : il les retiendra.</div>';return;}
    const couleur={user:'#7c3aed',preference:'#0891b2',projet:'#16a34a',fait:'#64748b'};
    el.innerHTML=list.map(function(m){
      return '<div class="hist-item" style="align-items:flex-start">'
        +'<span class="tag" style="flex-shrink:0;background:'+(couleur[m.type]||'#64748b')+'22;color:'+(couleur[m.type]||'#64748b')+'">'+esc(m.type||'fait')+'</span>'
        +'<span style="flex:1;font-size:13px">'+esc(m.contenu||'')+'<br><span style="font-size:11px;color:var(--mut)">'+esc(m.cree_le||'')+'</span></span>'
        +'<span style="color:var(--ko);cursor:pointer;font-weight:700;flex-shrink:0" title="Oublier" onclick="deleteMemoire(\''+esc(m.id)+'\')">&times;</span>'
        +'</div>';
    }).join('');
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
window.deleteMemoire=async function(id){
  try{await fetch('/memoire/'+encodeURIComponent(id),{method:'DELETE'});}catch(e){}
  loadMemoire();
};
(function(){
  const btn=document.getElementById('mem-refresh');
  if(btn)btn.onclick=loadMemoire;
  loadMemoire();
})();

// ===== TACHES AUTONOMES (cron) =====
async function loadTaches(){
  const el=document.getElementById('tache-list');if(!el)return;
  try{
    const d=await(await fetch('/taches')).json();
    const list=d.taches||[];
    if(!list.length){el.innerHTML='<div style="color:var(--mut);font-size:13px">Aucune tache. L\'agent peut agir tout seul : cree une veille, un rapport...</div>';return;}
    el.innerHTML=list.map(function(t){
      var last=(t.logs&&t.logs.length)?t.logs[t.logs.length-1]:null;
      return '<div class="hist-item" style="align-items:flex-start">'
        +'<span class="tag '+(t.actif?'ok':'')+'" style="flex-shrink:0">'+(t.actif?'actif':'pause')+'</span>'
        +'<span style="flex:1;font-size:13px"><b>'+esc(t.nom)+'</b> <span style="color:var(--mut);font-size:11px">('+esc(t.agent)+', toutes les '+t.intervalle_minutes+'min)</span>'
        +'<br><span style="font-size:12px;color:var(--mut)">'+esc(t.message)+'</span>'
        +(last?'<br><span style="font-size:11px;color:var(--mut)">dernier: '+esc(last.t)+' &#8594; '+esc((last.resultat||'').slice(0,90))+'</span>':'')
        +'</span>'
        +'<span style="display:flex;flex-direction:column;gap:4px;flex-shrink:0">'
        +'<span style="cursor:pointer;font-size:11px;color:var(--acc)" onclick="toggleTache(\''+esc(t.id)+'\','+(!t.actif)+')">'+(t.actif?'pause':'activer')+'</span>'
        +'<span style="cursor:pointer;font-size:11px;color:var(--ko)" onclick="deleteTache(\''+esc(t.id)+'\')">supprimer</span>'
        +'</span></div>';
    }).join('');
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
window.toggleTache=async function(id,actif){
  try{await fetch('/taches/'+encodeURIComponent(id)+'/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actif:actif})});}catch(e){}
  loadTaches();
};
window.deleteTache=async function(id){
  try{await fetch('/taches/'+encodeURIComponent(id),{method:'DELETE'});}catch(e){}
  loadTaches();
};
(function(){
  const add=document.getElementById('tache-add-btn'),form=document.getElementById('tache-form'),save=document.getElementById('tache-save');
  if(add)add.onclick=function(){form.classList.toggle('hidden');};
  if(save)save.onclick=async function(){
    var nom=(document.getElementById('tache-nom').value||'').trim();
    var agent=document.getElementById('tache-agent').value;
    var msg=(document.getElementById('tache-msg').value||'').trim();
    var interval=parseInt(document.getElementById('tache-interval').value||'60',10);
    if(!nom||!msg){return;}
    try{await fetch('/taches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nom:nom,agent:agent,message:msg,intervalle_minutes:interval})});}catch(e){}
    document.getElementById('tache-nom').value='';document.getElementById('tache-msg').value='';
    form.classList.add('hidden');loadTaches();
  };
  loadTaches();
})();
</script>
</body>
</html>
"""

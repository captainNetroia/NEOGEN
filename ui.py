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

.hidden{display:none !important;}

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
    <span class="side-badge soon">bientot</span>
  </div>
  <div class="side-item" style="--lc:var(--c-don)" onclick="showSection('don')" id="side-don">
    <span class="side-dot"></span>Soutenir
    <span class="side-badge soon">bientot</span>
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
      <div class="layer-label"><h3>Soutenir</h3><p>Contribuer au projet NEOGEN</p></div>
      <span class="badge soon">bientot</span>
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
    <div id="stale-notice" class="hidden" style="margin-top:8px;padding:5px 12px;border-radius:8px;
      background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.25);
      font-size:12px;color:var(--warn);display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      Intention modifiee &mdash; resultats anterieurs ci-dessous
      <button id="btn-reanalyse" style="padding:3px 10px;font-size:12px">&#8635; Refaire l'analyse</button>
    </div>
    <div id="discernement" class="hidden"></div>
    <div id="conseil-box" class="hidden"></div>
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

<!-- PRODUCTION -->
<div id="section-production" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-production)"></span>Production</h2>
    <p>Produits generes, valides, prets a l'emploi.</p>
  </div>
  <div id="produit-grid" class="produit-grid"></div>
  <div id="lineage-view" class="lineage-view hidden"></div>
  <pre id="code-view" class="hidden"></pre>
</div>

<!-- COMPTE -->
<div id="section-compte" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-compte)"></span>Compte</h2>
    <p>Ton profil, modele actif et historique de production.</p>
  </div>
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
      <button id="integ-save-btn">Enregistrer</button>
      <button id="integ-activate-btn" class="ghost" style="display:none">Activer</button>
    </div>
    <div id="integ-status"></div>
  </div>

  <!-- Grille des categories -->
  <div class="integ-grid">

    <div class="glass integ-category">
      <div class="integ-cat-title">Reseaux sociaux</div>
      <div class="integ-item"><span class="integ-icon">◈</span><span class="integ-name">TikTok</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">◉</span><span class="integ-name">Instagram</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">◎</span><span class="integ-name">LinkedIn</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <div class="glass integ-category">
      <div class="integ-cat-title">Video &amp; Creation</div>
      <div class="integ-item"><span class="integ-icon">⊕</span><span class="integ-name">Magnific</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">▶</span><span class="integ-name">YouTube</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <div class="glass integ-category">
      <div class="integ-cat-title">Recherche &amp; Docs</div>
      <div class="integ-item"><span class="integ-icon">◫</span><span class="integ-name">NotebookLM</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">⊞</span><span class="integ-name">DeerFlow</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <div class="glass integ-category">
      <div class="integ-cat-title">Juridique &amp; Admin</div>
      <div class="integ-item"><span class="integ-icon">⊜</span><span class="integ-name">OpenLegi</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">⊟</span><span class="integ-name">INPI</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <div class="glass integ-category">
      <div class="integ-cat-title">E-commerce &amp; Paiement</div>
      <div class="integ-item"><span class="integ-icon">⊠</span><span class="integ-name">Shopify</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">◆</span><span class="integ-name">Stripe</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <div class="glass integ-category">
      <div class="integ-cat-title">Infra &amp; Dev</div>
      <div class="integ-item"><span class="integ-icon">⊗</span><span class="integ-name">n8n</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
      <div class="integ-item"><span class="integ-icon">⊙</span><span class="integ-name">GitHub</span><span class="integ-status-dot"></span><span class="badge soon">bientot</span></div>
    </div>

    <!-- Integrations personnalisees -->
    <div class="glass integ-category">
      <div class="integ-cat-title">Personnalisee</div>
      <div id="integ-custom-list"></div>
      <div class="integ-add-btn" onclick="toggleAddIntegForm()">+ Ajouter</div>
      <div id="integ-add-form" class="hidden">
        <input type="text" id="integ-custom-name" placeholder="Nom (ex: Airtable)">
        <input type="text" id="integ-custom-endpoint" placeholder="Endpoint ou URL de l'API">
        <input type="password" id="integ-custom-key" placeholder="Cle API (optionnel)">
        <button onclick="saveCustomInteg()" style="width:100%;margin-top:2px">Ajouter</button>
      </div>
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
      <div style="display:flex;flex-direction:column;gap:12px;align-items:stretch">
        <a href="https://github.com/captainNetroia/VIVARIUM" target="_blank"
           style="display:flex;align-items:center;justify-content:center;gap:10px;
           padding:13px 24px;border-radius:12px;
           background:rgba(255,255,255,.3);backdrop-filter:blur(10px);
           color:var(--txt);text-decoration:none;font-weight:600;font-size:14px;
           border:1px solid rgba(255,255,255,.55);transition:background .15s"
           onmouseover="this.style.background='rgba(255,255,255,.5)'"
           onmouseout="this.style.background='rgba(255,255,255,.3)'">
          ⊙ &nbsp;Voir le projet sur GitHub
        </a>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;
           padding:13px 24px;border-radius:12px;cursor:default;
           background:rgba(219,39,119,.07);
           border:1px solid rgba(219,39,119,.18);
           color:var(--c-don);font-size:14px;font-weight:600">
          ◆ &nbsp;Paiement Stripe — bientot disponible
        </div>
      </div>
    </div>
    <div class="panel glass" style="padding:20px 24px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Ou va ton soutien</div>
      <div class="hist-item"><span style="font-size:16px">⚡</span><span class="hist-intention">Calcul GPU pour la generation et l'evolution</span></div>
      <div class="hist-item"><span style="font-size:16px">⊕</span><span class="hist-intention">Developpement des phases D a G (integrations, GTM, applis)</span></div>
      <div class="hist-item"><span style="font-size:16px">⊟</span><span class="hist-intention">Protection IP (INPI, eSoleau, RGPD)</span></div>
      <div class="hist-item"><span style="font-size:16px">◈</span><span class="hist-intention">Hebergement serveur dedie et infrastructure</span></div>
    </div>
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

  /* Fond clair avec couleur bien presente (glassmorphism) */
  col=mix(vec3(1.),col,.52);

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

  function resize(){
    canvas.width=innerWidth;canvas.height=innerHeight;
    gl.viewport(0,0,canvas.width,canvas.height);
  }
  resize();
  window.addEventListener('resize',resize);

  const start=Date.now();
  function draw(){
    gl.uniform2f(uRes,canvas.width,canvas.height);
    gl.uniform1f(uTime,(Date.now()-start)/1000);
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
const studio={intention:'',proposition:null,murs:[],persistance:false,reseau:false,domaines:'',juger:false,
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
    studio.persistance=!!p.persistance;studio.reseau=!!p.reseau;
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
  const capLabels={persistance:'Persistance (disque)',reseau:'Reseau (liste blanche)'};
  ['persistance','reseau'].forEach(name=>{
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
    const genBadge=(p.generation&&p.generation>1)?' <span class="gen-badge">gen '+p.generation+'</span>':'';
    card.innerHTML='<div class="ct">'+esc(p.intention)+(p.promouvable?' <span class="tag ok">appli</span>':'')+genBadge+'</div>'+
                   '<div class="cs">'+p.lignes+' lignes | '+esc(p.verdict)+'</div>';
    const actions=document.createElement('div');actions.className='cactions';
    const btnCode=document.createElement('button');btnCode.className='ghost';btnCode.textContent='Code';
    btnCode.onclick=async()=>{
      const prod=await(await fetch('/produits/'+encodeURIComponent(p.id))).json();
      const cv=$('#code-view');cv.textContent=prod.code||'';cv.classList.remove('hidden');
      cv.scrollIntoView({behavior:'smooth',block:'nearest'});
    };
    actions.appendChild(btnCode);
    const btnLin=document.createElement('button');btnLin.className='ghost';btnLin.textContent='Lignee';
    btnLin.onclick=()=>openLineage(p.id);
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
    card.appendChild(actions);grid.appendChild(card);
  });
  _breath.scan(); /* active le float sur les cartes venant d'etre injectees */
}

/* --- Genealogie (Phase 4) : arbre des generations, diff, revert, upgrade --- */
async function openLineage(produitId){
  const el=$('#lineage-view');if(!el)return;
  el.classList.remove('hidden');
  el.innerHTML='<div class="step-help">Chargement de la lignee...</div>';
  el.scrollIntoView({behavior:'smooth',block:'nearest'});
  try{
    const d=await(await fetch('/produits/'+encodeURIComponent(produitId)+'/generations')).json();
    if(d.detail){el.innerHTML='<span class="tag ko">erreur</span> '+errMsg(d.detail);return;}
    renderLineage(d);
  }catch(e){el.innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
}

function renderLineage(d){
  const el=$('#lineage-view');
  let html='<div class="lineage-head"><h3>Lignee : '+esc(d.intention||'')+'</h3>'
    +'<span class="tag">'+d.total+' generation(s)</span>'
    +'<button class="ghost" style="margin-left:auto;font-size:12px;padding:5px 11px" onclick="document.getElementById(\'lineage-view\').classList.add(\'hidden\')">Fermer</button></div>';
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
    if(r.ok)openLineage(id);
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
            if(evt.succes&&evt.produit_id){loadProduits().then(()=>openLineage(evt.produit_id));}
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
async function loadAnalyse(){
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
  const PROV={
    anthropic:{label:'Anthropic',check:k=>k.startsWith('sk-ant-'),
      models:['claude-fable-5','claude-opus-4-8','claude-sonnet-4-6','claude-haiku-4-5'],
      ph:'sk-ant-api03-...'},
    openai:{label:'OpenAI / GPT',check:k=>k.startsWith('sk-')&&!k.startsWith('sk-ant-'),
      models:['gpt-4o','gpt-4o-mini','gpt-4.1','gpt-4.1-mini','o1','o3-mini'],
      ph:'sk-proj-...'},
    gemini:{label:'Gemini',check:k=>k.startsWith('AIza'),
      models:['gemini-2.5-pro','gemini-2.0-flash','gemini-1.5-pro','gemini-1.5-flash'],
      ph:'AIzaSy...'},
    deepseek:{label:'DeepSeek',check:k=>k.length>10,
      models:['deepseek-chat','deepseek-reasoner','deepseek-coder'],
      ph:'API key DeepSeek...'},
    mistral:{label:'Mistral',check:k=>k.length>10,
      models:['mistral-large-latest','mistral-small-latest','codestral-latest','open-mistral-nemo'],
      ph:'API key Mistral...'},
    local:{label:'Local (Ollama)',check:_=>true,
      models:['llama3.2','qwen2.5','mistral','phi4','gemma3','deepseek-r1:8b'],
      ph:'http://localhost:11434 (optionnel)'}
  };

  const ge=id=>document.getElementById(id);
  const tabs=document.querySelectorAll('.prov-tab');
  const modelSel=ge('integ-model-select');
  const keyIn=ge('integ-api-key');
  const dot=ge('integ-model-dot');
  const saveBtn=ge('integ-save-btn');
  const actBtn=ge('integ-activate-btn');
  const st=ge('integ-status');
  const activeLabel=ge('integ-active-label');
  if(!modelSel||!keyIn)return;

  let curProv=localStorage.getItem('neogen_provider')||'anthropic';

  function setDot(s){dot.className='integ-model-dot'+(s?' '+s:'');}

  function updateActiveLabel(){
    const p=localStorage.getItem('neogen_active_provider');
    const m=localStorage.getItem('neogen_active_model');
    if(p&&m&&PROV[p]){
      activeLabel.textContent=PROV[p].label+' / '+m;
      activeLabel.style.color='var(--ok)';
    } else {
      activeLabel.textContent='aucun';
      activeLabel.style.color='var(--txt)';
    }
  }

  function updateTabDots(){
    tabs.forEach(t=>{
      const p=t.dataset.prov;
      const hasKey=!!localStorage.getItem('neogen_key_'+p);
      const isActive=localStorage.getItem('neogen_active_provider')===p;
      /* dot vert dans le tab si cle presente */
      t.style.borderColor=isActive?'var(--ok)':hasKey?'rgba(22,163,74,.4)':'rgba(15,23,42,.12)';
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
    /* bouton Activer : visible si cle dispo et pas deja actif */
    const isActive=localStorage.getItem('neogen_active_provider')===prov;
    actBtn.style.display=(hasKey&&!isActive)?'':'none';
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

  /* Enregistrer */
  saveBtn.onclick=()=>{
    const m=modelSel.value,k=keyIn.value.trim();
    const p=PROV[curProv];
    if(k&&!p.check(k)){
      st.innerHTML='<span class="tag ko">format invalide</span> Verifier la cle pour '+p.label;
      setDot('ko');return;
    }
    localStorage.setItem('neogen_provider',curProv);
    localStorage.setItem('neogen_model_'+curProv,m);
    if(k){
      localStorage.setItem('neogen_key_'+curProv,k);
      localStorage.setItem('neogen_api_key',k); /* compat generateur */
      keyIn.value='';
      keyIn.placeholder='cle enregistree (••••'+k.slice(-4)+')';
      setDot('ok');
    }
    actBtn.style.display=(localStorage.getItem('neogen_active_provider')!==curProv)?'':'none';
    updateTabDots();
    st.innerHTML='<span class="tag ok">enregistre</span> '+p.label+' / '+m+(k?' — cle mise a jour':'');
    setTimeout(()=>st.innerHTML='',3000);
  };

  /* Activer */
  actBtn.onclick=()=>{
    const m=modelSel.value;
    localStorage.setItem('neogen_active_provider',curProv);
    localStorage.setItem('neogen_active_model',m);
    localStorage.setItem('neogen_model',m); /* compat */
    actBtn.style.display='none';
    updateActiveLabel();
    updateTabDots();
    st.innerHTML='<span class="tag ok">actif</span> '+PROV[curProv].label+' / '+m;
    setTimeout(()=>st.innerHTML='',3000);
  };

  /* Custom integrations */
  function loadCustom(){
    const list=JSON.parse(localStorage.getItem('neogen_integrations')||'[]');
    const el=ge('integ-custom-list');if(!el)return;
    el.innerHTML=list.map((c,i)=>
      `<div class="integ-item">
        <span class="integ-icon">⊕</span>
        <span class="integ-name">${esc(c.name)}</span>
        <span class="integ-status-dot ${c.key?'ok':''}"></span>
        <span style="font-size:12px;color:var(--ko);cursor:pointer;font-weight:700" onclick="deleteInteg(${i})">×</span>
      </div>`
    ).join('');
  }

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
    ge('integ-add-form').classList.add('hidden');
    loadCustom();
    if(window._breath)_breath.scan();
  };
  window.deleteInteg=function(i){
    const list=JSON.parse(localStorage.getItem('neogen_integrations')||'[]');
    list.splice(i,1);
    localStorage.setItem('neogen_integrations',JSON.stringify(list));
    loadCustom();
  };

  /* Init */
  switchProv(curProv);
  updateActiveLabel();
  loadCustom();
})();

health();

/* Hash routing : on load + bouton back navigateur */
const SECTIONS=['creation','production','compte','analyse','integrations','don'];
function routeHash(){
  const h=location.hash.slice(1);
  if(h&&SECTIONS.includes(h))showSection(h);
}
window.addEventListener('popstate',routeHash);
routeHash();
</script>
</body>
</html>
"""

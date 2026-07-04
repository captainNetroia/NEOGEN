/* ===== VIDEO BACKGROUND (Matrix loop) ===== */
(function(){
  ['bg-video','bg-video-light-1','bg-video-light-2','cascade-video'].forEach(id=>{
    const v=document.getElementById(id);
    if(v) v.play().catch(()=>{});
  });
  window._setShaderDark = function(){};
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

  /* Perf : au repos (pas de pointermove), le mouvement est lent (float idle) -> 30fps est
     visuellement indiscernable de 60fps ici, et divise par 2 la charge GPU (recomposition
     de 9 cartes backdrop-filter + parallaxe 3D + video de fond simultanes - mesure : la video
     perdait ~50% de ses frames sur cette page avant cette optimisation). Repasse a pleine
     cadence des qu'une interaction souris reelle a lieu (active=true), ou la reactivite
     est prioritaire sur l'economie GPU. */
  let _lastFrameT=0;
  function frame(t){
    const throttle=!active;
    if(throttle && t-_lastFrameT<33){requestAnimationFrame(frame);return;}
    _lastFrameT=t;
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
  requestAnimationFrame(frame);
})();

/* ===== SIDEBAR : shimmer souris + stagger float CSS ===== */
(function(){
  const items=Array.from(document.querySelectorAll('.side-item'));
  if(!items.length)return;
  items.forEach((el,i)=>{
    /* specular shimmer : suit la souris par item */
    el.addEventListener('pointermove',e=>{
      const r=el.getBoundingClientRect();
      el.style.setProperty('--sx',((e.clientX-r.left)/r.width*100).toFixed(1)+'%');
      el.style.setProperty('--sy',((e.clientY-r.top)/r.height*100).toFixed(1)+'%');
    });
  });
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
    /* panels : apesanteur subtile partout, y compris les panels de chat (demande explicite
       Jordan) - amplitude reduite sur .agent-chat pour ne pas geiner la lecture/saisie. */
    document.querySelectorAll('.glass.panel,.panel.glass').forEach(function(el){
      if(el.classList.contains('agent-chat')){add(el,.9,.06);return;}
      add(el,1.8,.1);
    });
    /* sidebar items : phase Fibonacci -> chaque item a sa propre trajectoire aleatoire */
    document.querySelectorAll('.side-item').forEach(el=>add(el,3,1));
    /* placeholders (pages bientot) */
    document.querySelectorAll('.placeholder.glass').forEach(el=>add(el,2,.3));
    /* icones ph-icon : levitation moderee */
    document.querySelectorAll('.ph-icon').forEach(el=>add(el,4,0));
    /* cartes produits (generees dynamiquement) */
    document.querySelectorAll('.produit-card.glass').forEach(el=>add(el,2,.4));
  }

  /* Perf : mouvement tres lent (sinus basse frequence) -> 30fps indiscernable de 60fps,
     divise par 2 la charge GPU cumulee avec le parallaxe bento + backdrop-filter des
     cartes (cf. commentaire perf sur le parallaxe dans app.js). */
  let _lastFrameT=0;
  function frame(ts){
    if(ts-_lastFrameT<33){requestAnimationFrame(frame);return;}
    _lastFrameT=ts;
    t+=.009;
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
  requestAnimationFrame(frame);
  return{scan};
})();

/* ===== NAVIGATION ===== */
const $=s=>document.querySelector(s);
const errMsg=x=>{if(x==null)return'';if(typeof x==='string')return x;if(x.message)return x.message;try{return JSON.stringify(x);}catch(e){return String(x);}};
const esc=s=>(s||'').replace(/[<>]/g,'');
const LABELS={creation:'Creation',production:'Production',compte:'Compte',analyse:'Dev & Analyse',evolution:'Evolution',marketing:'Marketing',integrations:'Integrations',don:'Soutenir'};

/* ===== ICONES SVG (remplace les emojis texte des boutons/toggles par des glyphes stroke
   coherents avec le reste du design system, cf. reference PNG fournie par Jordan). currentColor
   pour heriter la teinte du bouton parent (vert Matrix par defaut, pas de bleu/cyan importe). */
const ICONS={
  eco:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 4 13V6a1 1 0 0 1 1-1h6a7 7 0 0 1 7 7 7 7 0 0 1-7 7Z"/><path d="M11 20v-9"/><path d="M11 11 6 6"/></svg>',
  eclair:'<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/></svg>',
  conversations:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2Z"/><path d="M7 9h10"/><path d="M7 13h6"/></svg>',
  close:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  camera:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8a2 2 0 0 1 2-2h1.2a1 1 0 0 0 .87-.5l.66-1.15A1 1 0 0 1 9.6 4h4.8a1 1 0 0 1 .87.5l.66 1.15a1 1 0 0 0 .87.5H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"/><circle cx="12" cy="13" r="3.2"/></svg>',
};
function svgIcon(name,size){size=size||15;return '<span class="ntr-icon ntr-icon-'+name+'" style="display:inline-flex;width:'+size+'px;height:'+size+'px;vertical-align:-3px">'+ICONS[name]+'</span>';}

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
  if(name==='analyse'){loadAnalyse();if(typeof loadIngenieur==='function')loadIngenieur();}
  if(name==='marketing')loadMarketing();
  if(name==='cerveau'){loadMemoire();loadSkills();}
  if(name==='evolution'){loadHubEtat();loadHubPropositions();loadPenseesConfig();loadPensees();loadEvolutionSysteme();}
  /* scan post-section : enregistre les panels rendus dynamiquement (fragments, chats) */
  setTimeout(()=>_breath.scan(),150);
  /* re-verifie la distorsion glass des panels de la section qui vient de s'activer - un
     panel injecte pendant que sa section etait encore inactive peut rester bloque sur le
     blur() simple sans ceci (cf. skill bento-3d-glass v3.8). */
  setTimeout(()=>{ if(typeof window.refreshLiquidGlass==='function') window.refreshLiquidGlass(); },200);
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
  const el=$('#docker-status');
  if(!el)return; /* absent en instance publique (cf. ui.py::_head) - rien a faire */
  try{
    const h=await(await fetch('/health')).json();
    el.innerHTML='<span class="dot '+(h.docker?'on':'off')+'"></span>'+(h.docker?'Docker actif ('+h.docker_info+')':'Docker indisponible');
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
    .then(async resp=>{
      if(await _maybeUpgrade(resp,$('#forge-result'))){
        forgeAdd('err','Limite atteinte','Passe a un pack superieur pour continuer.','ko');
        $('#btn-forger').disabled=false;return;
      }
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
  const grid=$('#produit-grid');if(!grid)return;
  let d;
  try{
    const r=await fetch('/produits');
    if(!r.ok)throw new Error('HTTP '+r.status);
    d=await r.json();
  }catch(e){
    // Transitoire (rebuild/redemarrage) : message clair + retry, pas de « Failed to fetch » brut.
    grid.innerHTML='<div class="placeholder glass"><div class="ph-icon">⟳</div><h3>Chargement indisponible</h3>'
      +'<p>Le serveur redemarre peut-etre. <a href="#" onclick="loadProduits();return false;" style="color:var(--acc)">Reessayer</a></p></div>';
    return;
  }
  const list=(d.produits||[]).slice().reverse();
  grid.innerHTML='';
  if(!list.length){
    grid.innerHTML='<div class="placeholder glass"><div class="ph-icon">◻</div><h3>Aucun produit</h3><p>Va dans Creation pour fabriquer ton premier produit.</p></div>';
    return;
  }
  // Cacher les archivees par defaut (filtre courant 'actifs')
  const filtreProd=window._filtreProduitsCourant||'actifs';
  list.forEach(p=>{
    const card=document.createElement('div');card.className='produit-card glass';
    card.dataset.id=p.id;
    card.dataset.archive=p.archive?'1':'0';
    if(filtreProd==='actifs'&&p.archive)return;
    if(filtreProd==='archivees'&&!p.archive)return;
    const genBadge=(p.generation&&p.generation>1)?' <span class="gen-badge">gen '+p.generation+'</span>':'';
    // Badge 3 etats : deploye (promu) > appli (promouvable) > code (basique)
    const statusBadge=p.promu
      ?'<span class="tag ok" style="margin-left:6px">deploye</span>'
      :p.promouvable
        ?'<span class="tag" style="margin-left:6px;background:rgba(8,145,178,.12);color:var(--acc)">appli</span>'
        :'<span class="tag" style="margin-left:6px;background:rgba(100,116,139,.12);color:var(--mut)">code</span>';
    // Titre en gras + description tronquee
    const titre=esc(p.intention);
    const penseeOrigin=p.pensee_id
      ?'<div style="font-size:11px;color:var(--mut);margin-top:3px">Née de : <a href="#evolution" style="color:var(--acc);text-decoration:none" onclick="window._penseeScroll=\''+esc(p.pensee_id)+'\'">'+esc(p.pensee_titre||p.pensee_id)+'</a></div>'
      :'';
    card.innerHTML='<div class="ct" style="font-size:15px;font-weight:700;color:var(--txt);margin-bottom:4px">'+titre+statusBadge+genBadge+'</div>'+
                   '<div class="cs">'+p.lignes+' lignes &middot; '+esc(p.verdict)+'</div>'+penseeOrigin;
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
    btnDl.onclick=async(e)=>{
      e.stopPropagation();
      if(!_authToken()){_showAuthModal('Connecte-toi pour telecharger ce produit.',()=>btnDl.click());return;}
      btnDl.disabled=true;btnDl.textContent='...';
      try{
        const r=await fetch('/produits/'+encodeURIComponent(p.id)+'/telecharger',{headers:_authHdrs()});
        if(!r.ok){
          if(r.status===401)_showAuthModal('Connecte-toi pour telecharger ce produit.',()=>btnDl.click());
          else alert('Erreur telechargement ('+r.status+')');
          return;
        }
        const blob=await r.blob();
        const a=document.createElement('a');
        a.href=URL.createObjectURL(blob);
        a.download='neogen-'+p.id.slice(0,8)+'.zip';
        a.click();
        URL.revokeObjectURL(a.href);
      }catch(err){alert(errMsg(err));}
      finally{btnDl.disabled=false;btnDl.textContent='Telecharger';}
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
    // Bouton cristalliser en skill
    const btnCrist=document.createElement('button');btnCrist.className='ghost';
    btnCrist.title='Cristalliser ce produit en skill reutilisable';
    btnCrist.textContent='Cristalliser';
    btnCrist.onclick=async(e)=>{
      e.stopPropagation();btnCrist.disabled=true;btnCrist.textContent='...';
      try{
        const r=await(await fetch('/produits/'+encodeURIComponent(p.id)+'/cristalliser',
          {method:'POST',headers:_llmHdrs()})).json();
        if(r.ok&&r.skill){
          btnCrist.textContent='Skill cree !';
          btnCrist.style.color='var(--ok)';
          setTimeout(()=>{btnCrist.textContent='Cristalliser';btnCrist.style.color='';btnCrist.disabled=false;},3000);
        } else {
          alert(r.detail||'Erreur cristallisation');
          btnCrist.disabled=false;btnCrist.textContent='Cristalliser';
        }
      }catch(err){alert(errMsg(err));btnCrist.disabled=false;btnCrist.textContent='Cristalliser';}
    };
    actions.appendChild(btnCrist);
    // Bouton archiver (si non deja archive)
    if(!p.archive){
      const btnArc=document.createElement('button');btnArc.className='ghost';
      btnArc.title='Archiver cette creation (masquee du catalogue)';
      btnArc.textContent='Archiver';
      btnArc.style.cssText='color:var(--mut);opacity:.7';
      btnArc.onclick=(e)=>{
        e.stopPropagation();btnArc.disabled=true;
        fetch('/produits/'+encodeURIComponent(p.id)+'/archiver',{method:'POST'})
          .then(r=>r.json())
          .then(d=>{if(d.ok)card.remove();else{btnArc.disabled=false;}})
          .catch(()=>{btnArc.disabled=false;});
      };
      actions.appendChild(btnArc);
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
function _renderOpenLegi(d,intention){
  var res=d.resultats||{};
  var termes=d.termes||d.query||intention;
  var head='<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">'
    +'<b style="color:var(--acc)">⊜ Conformité juridique</b>'
    +'<span style="font-size:11px;color:var(--mut)">Légifrance · termes : '+esc(termes)+'</span></div>';
  /* Repli si structure inattendue (ancien format ou echec LLM) */
  var articles=(res&&Array.isArray(res.articles))?res.articles:null;
  if(!articles){
    var brut=(res&&res.brut)?res.brut:(typeof res==='string'?res:JSON.stringify(res||{},null,2));
    return '<div class="compo-premiere">'+head
      +'<div style="font-size:12px;color:var(--mut);white-space:pre-wrap;max-height:220px;overflow:auto">'+esc((brut||'').slice(0,1200))+'</div></div>';
  }
  var html='<div class="compo-premiere">'+head;
  if(res.synthese){
    html+='<div style="padding:10px 12px;background:rgba(0,232,105,.06);border-left:2px solid var(--acc);border-radius:6px;font-size:13px;line-height:1.5;margin-bottom:10px">'+esc(res.synthese)+'</div>';
  }
  if(!articles.length){
    html+='<div style="font-size:12px;color:var(--mut)">Aucun texte de loi pertinent trouvé pour cet objectif.</div></div>';
    return html;
  }
  html+=articles.map(function(a){
    var haute=(a.pertinence==='haute');
    var badge='<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;'
      +(haute?'background:rgba(0,232,105,.15);color:var(--acc)':'background:rgba(148,163,184,.15);color:var(--mut)')
      +'">'+(haute?'pertinence haute':'pertinence moyenne')+'</span>';
    var lien=(a.lien&&/^https?:\/\//.test(a.lien))
      ?'<a href="'+esc(a.lien)+'" target="_blank" rel="noopener" style="font-size:11px;color:var(--acc);text-decoration:underline">Voir sur Légifrance →</a>':'';
    return '<div style="border:1px solid var(--brd);border-radius:10px;padding:12px 14px;margin-bottom:8px">'
      +'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:5px">'
      +'<b style="font-size:13.5px">'+esc(a.titre||a.reference||'Texte')+'</b>'+badge+'</div>'
      +(a.reference?'<div style="font-size:11px;color:var(--mut);margin-bottom:5px">'+esc(a.reference)+'</div>':'')
      +(a.resume?'<div style="font-size:12.5px;line-height:1.5;margin-bottom:5px">'+esc(a.resume)+'</div>':'')
      +(a.pourquoi?'<div style="font-size:11.5px;color:var(--mut);line-height:1.45;margin-bottom:6px"><b style="color:var(--txt)">Pourquoi :</b> '+esc(a.pourquoi)+'</div>':'')
      +lien
      +'</div>';
  }).join('');
  html+='</div>';
  return html;
}
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
    box.innerHTML=_renderOpenLegi(d,intention);box.classList.remove('hidden');$('#scan-status').innerHTML='';
  }catch(e){$('#scan-status').innerHTML='<span class="tag ko">erreur</span> '+errMsg(e);}
  finally{btn.disabled=false;}
};

/* Auth helpers */
function _authToken(){return localStorage.getItem('neogen_auth_token');}
function _authHdrs(){const t=_authToken();return t?{'Authorization':'Bearer '+t}:{};}

/* Masonry : positionne les cartes absolument pour supprimer les vides entre lignes. */
function _attachDetailsToggle(id,colW,gap){
  var c=document.getElementById(id);
  if(!c)return;
  c.querySelectorAll('details').forEach(function(det){
    if(det.dataset.masonryBound)return;
    det.dataset.masonryBound='1';
    det.addEventListener('toggle',function(){
      requestAnimationFrame(function(){_applyMasonry(id,colW||350,gap||8);});
    });
  });
}

function _applyMasonry(id,colW,gap){
  colW=colW||215;gap=gap||8;
  var c=document.getElementById(id);
  if(!c)return;
  var items=Array.from(c.children).filter(function(el){return el.style.display!=='none';});
  if(!items.length){c.style.height='';return;}
  var totalW=c.clientWidth;
  if(!totalW)return;
  var numCols=Math.max(1,Math.floor((totalW+gap)/(colW+gap)));
  var aColW=Math.floor((totalW-(numCols-1)*gap)/numCols);
  c.style.position='relative';
  c.style.display='block';
  var colH=new Array(numCols).fill(0);
  items.forEach(function(el){
    if(el.classList&&el.classList.contains('pensee-groupe-header')){
      var maxH=Math.max.apply(null,colH);
      el.style.position='absolute';el.style.left='0';el.style.top=maxH+'px';el.style.width=totalW+'px';
      var h=el.offsetHeight+gap;
      for(var i=0;i<numCols;i++)colH[i]=maxH+h;
    }else{
      var min=Math.min.apply(null,colH);var col=colH.indexOf(min);
      el.style.position='absolute';el.style.left=(col*(aColW+gap))+'px';el.style.top=colH[col]+'px';
      el.style.width=aColW+'px';el.style.boxSizing='border-box';
      colH[col]+=el.offsetHeight+gap;
    }
  });
  c.style.height=Math.max.apply(null,colH)+'px';
}

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
  if(localStorage.getItem('neogen_eco')!=='0')h['X-LLM-Eco']='1';
  if(localStorage.getItem('neogen_eclair')!=='0')h['X-ECLAIR']='1';
  var _t=(typeof _authToken==='function')?_authToken():null;
  if(_t)h['Authorization']='Bearer '+_t;   /* identifie l'utilisateur pour les quotas */
  return h;
}
/* Intercepteur global 401 — toute reponse non-auth qui retourne 401 affiche la modal de connexion.
   Exclusions : /auth/* (deja le formulaire lui-meme) et /rpa/* (polls de fond silencieux,
   ex. pollRpaStatus toutes les 3s — un 401 normal pour un visiteur non connecte ne doit
   jamais interrompre une saisie en cours ailleurs sur la page, cf. bug 2026-07-04 ou la
   modal de login se recreait/se vidait pendant la frappe a cause de ce poll). */
(function(){
  var _orig=window.fetch.bind(window);
  window.fetch=async function(){
    var res=await _orig.apply(this,arguments);
    if(res.status===401){
      var url=(typeof arguments[0]==='string'?arguments[0]:(arguments[0]&&arguments[0].url)||'');
      if(!url.includes('/auth/')&&!url.includes('/rpa/')){
        _showAuthModal('Tu dois te connecter à ton compte pour continuer.');
      }
    }
    return res;
  };
})();

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
      if(typeof _injectUserCss==='function')_injectUserCss();
      if(typeof _checkOnboarding==='function')_checkOnboarding();else loadCompte();
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

/* Modal flottante de connexion/inscription — appelee quand une action requiert un compte */
function _showAuthModal(msg,onSuccess){
  const ex=document.getElementById('ntr-auth-overlay');if(ex)ex.remove();
  const overlay=document.createElement('div');
  overlay.id='ntr-auth-overlay';
  overlay.style.cssText='position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.78);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px)';
  const box=document.createElement('div');
  box.style.cssText='position:relative;min-width:320px;max-width:420px;width:90vw';
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.remove();});
  if(msg){
    const msgEl=document.createElement('p');
    msgEl.textContent=msg;
    msgEl.style.cssText='font-size:14px;color:var(--acc,#6366f1);font-weight:600;margin:0 0 12px;text-align:center';
    box.appendChild(msgEl);
  }
  const btnClose=document.createElement('button');
  btnClose.innerHTML='&#x2715;';
  btnClose.style.cssText='position:absolute;top:6px;right:10px;z-index:2;background:none;border:none;color:var(--mut,#6b7280);font-size:18px;cursor:pointer;padding:4px 8px';
  btnClose.onclick=()=>overlay.remove();
  box.appendChild(btnClose);
  const formRoot=document.createElement('div');
  box.appendChild(formRoot);
  let mode='login';
  formRoot.innerHTML='<div class="panel glass">'
    +'<div class="auth-tabs"><div class="auth-tab active" id="ntr-tab-login">Se connecter</div>'
    +'<div class="auth-tab" id="ntr-tab-register">Creer un compte</div></div>'
    +'<div class="auth-form">'
    +'<div id="ntr-name-wrap" class="auth-field" style="display:none"><label>Nom</label>'
    +'<input type="text" id="ntr-auth-name" placeholder="Ton prenom..."></div>'
    +'<div class="auth-field"><label>Email</label>'
    +'<input type="email" id="ntr-auth-email" placeholder="ton@email.com" autocomplete="email"></div>'
    +'<div class="auth-field"><label>Mot de passe</label>'
    +'<input type="password" id="ntr-auth-pw" placeholder="..." autocomplete="current-password"></div>'
    +'<div id="ntr-pw2-wrap" class="auth-field" style="display:none"><label>Confirmer</label>'
    +'<input type="password" id="ntr-auth-pw2" placeholder="..." autocomplete="new-password"></div>'
    +'<div id="ntr-auth-err" style="display:none" class="auth-error"></div>'
    +'<button id="ntr-auth-submit" style="width:100%;margin-top:4px">Se connecter</button>'
    +'</div></div>';
  const qr=s=>formRoot.querySelector(s);
  const errEl=qr('#ntr-auth-err');
  const submit=qr('#ntr-auth-submit');
  function switchMode(m){
    mode=m;
    qr('#ntr-tab-login').classList.toggle('active',m==='login');
    qr('#ntr-tab-register').classList.toggle('active',m==='register');
    qr('#ntr-name-wrap').style.display=m==='register'?'flex':'none';
    qr('#ntr-pw2-wrap').style.display=m==='register'?'flex':'none';
    submit.textContent=m==='register'?'Creer mon compte':'Se connecter';
    errEl.style.display='none';
  }
  qr('#ntr-tab-login').onclick=()=>switchMode('login');
  qr('#ntr-tab-register').onclick=()=>switchMode('register');
  async function doAuth(){
    const email=(qr('#ntr-auth-email').value||'').trim();
    const pw=qr('#ntr-auth-pw').value||'';
    const name=(qr('#ntr-auth-name').value||'').trim();
    const pw2=qr('#ntr-auth-pw2').value||'';
    errEl.style.display='none';
    if(!email||!pw){errEl.textContent='Email et mot de passe requis.';errEl.style.display='';return;}
    if(mode==='register'&&pw.length<6){errEl.textContent='Mot de passe trop court (6 min).';errEl.style.display='';return;}
    if(mode==='register'&&pw!==pw2){errEl.textContent='Mots de passe differents.';errEl.style.display='';return;}
    submit.disabled=true;submit.textContent='...';
    try{
      const url=mode==='login'?'/auth/login':'/auth/register';
      const body=mode==='login'?{email,password:pw}:{email,password:pw,name};
      const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const d=await r.json();
      if(!r.ok){errEl.textContent=d.detail||'Erreur';errEl.style.display='';submit.disabled=false;submit.textContent=mode==='register'?'Creer mon compte':'Se connecter';return;}
      localStorage.setItem('neogen_auth_token',d.token);
      if(typeof _injectUserCss==='function')_injectUserCss();
      overlay.remove();
      if(typeof onSuccess==='function')onSuccess();else loadCompte();
    }catch(e){errEl.textContent='Erreur reseau.';errEl.style.display='';submit.disabled=false;submit.textContent=mode==='register'?'Creer mon compte':'Se connecter';}
  }
  submit.onclick=doAuth;
  ['#ntr-auth-email','#ntr-auth-pw','#ntr-auth-pw2'].forEach(s=>{const el=qr(s);if(el)el.addEventListener('keydown',e=>{if(e.key==='Enter')doAuth();});});
  setTimeout(()=>{const el=qr('#ntr-auth-email');if(el)el.focus();},60);
}

async function renderCompteConnecte(root,user){
  const isAdmin=!!user.is_admin;
  const palierLabel={'gratuit':'Gratuit','essential':'Essential','pro':'Pro','power':'Power','enterprise':'Enterprise'};
  const palCle=user.palier||'gratuit';
  root.innerHTML=
    '<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Mon compte</div>'
    +'<div style="font-size:17px;font-weight:700;margin-bottom:3px">'+esc(user.name)+'</div>'
    +'<div style="font-size:13px;color:var(--mut)">'+esc(user.email)+'</div>'
    +'<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">'
    +'<span class="tag '+(palCle!=='gratuit'?'ok':'')+'" style="display:inline-block">'+esc(palierLabel[palCle]||palCle)+'</span>'
    +(isAdmin?'<span class="tag ok" style="display:inline-block">admin</span>':'')
    +'</div>'
    +'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px">'
    +'<button class="ghost" id="chg-pw-btn" style="font-size:12px;padding:6px 12px">Changer le mot de passe</button>'
    +'<button class="ghost" id="switch-acct-btn" style="font-size:12px;padding:6px 12px">Changer de compte</button>'
    +'<button class="ghost" id="deconnexion-btn" style="font-size:12px;padding:6px 12px">Deconnexion</button>'
    +'</div>'
    +'<form id="chg-pw-form" style="display:none;margin-top:12px;flex-direction:column;gap:8px">'
    +'<input type="password" id="chg-pw-old" placeholder="Mot de passe actuel" autocomplete="current-password" style="width:100%;font-size:13px;padding:8px 10px;background:rgba(0,0,0,.25);border:1px solid rgba(100,116,139,.3);color:var(--txt);border-radius:8px;box-sizing:border-box">'
    +'<input type="password" id="chg-pw-new" placeholder="Nouveau mot de passe (6 caracteres min.)" autocomplete="new-password" style="width:100%;font-size:13px;padding:8px 10px;background:rgba(0,0,0,.25);border:1px solid rgba(100,116,139,.3);color:var(--txt);border-radius:8px;box-sizing:border-box">'
    +'<div style="display:flex;align-items:center;gap:10px"><button type="submit" style="font-size:12px;padding:7px 16px">Valider</button><span id="chg-pw-status" style="font-size:12px"></span></div>'
    +'</form></div>'

    +'<div id="abonnement-mount"></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Modele actif</div>'
    +'<div id="compte-model-info" style="font-size:14px;color:var(--txt)"></div></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Envoyer un retour a NEOGEN</div>'
    +'<div class="star-row" id="fb-stars">'+[1,2,3,4,5].map(i=>'<span class="star" data-v="'+i+'">&#9733;</span>').join('')+'</div>'
    +'<div style="margin-top:10px"><textarea id="fb-msg" placeholder="Dis-moi ce qui va ou ne va pas, une idee, un bug..."></textarea></div>'
    +'<div style="display:flex;align-items:center;gap:10px;margin-top:10px">'
    +'<button id="fb-submit-btn">Envoyer</button><span id="fb-status"></span></div></div>'

    +'<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">'+t('compte.preferences')+'</div>'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">'
    +'<span style="font-size:13px;color:var(--txt)">'+t('compte.langue')+'</span>'
    +'<select id="langue-select" style="padding:6px 10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:var(--txt);font-size:12px">'
    +'<option value="fr">Francais</option><option value="en">English</option>'
    +'</select></div>'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">'
    +'<span style="font-size:13px;color:var(--txt)">'+t('compte.mode_sombre')+'</span>'
    +'<label class="dark-toggle"><input type="checkbox" id="dark-toggle-cb"><span style="font-size:12px;color:var(--mut)"></span></label></div>'
    +'<div style="margin-bottom:6px"><div style="font-size:13px;color:var(--txt);margin-bottom:8px">'+t('compte.autorisation_agent_ecran')+'</div>'
    +'<div class="consent-btns">'
    +'<button class="consent-btn safe" data-level="always" data-dur="0" title="Popup avant chaque action">'+t('compte.toujours_demander')+'</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="120" title="Autorise pour 2 minutes">2 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="600" title="Autorise pour 10 minutes">10 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="1800" title="Autorise pour 30 minutes">30 min</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="3600" title="Autorise pour 1 heure">1 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="7200" title="Autorise pour 2 heures">2 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="18000" title="Autorise pour 5 heures">5 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="43200" title="Autorise pour 12 heures">12 h</button>'
    +'<button class="consent-btn" data-level="sequence" data-dur="86400" title="Autorise pour 24 heures">24 h</button>'
    +'<button class="consent-btn danger" data-level="auto" data-dur="0" title="Aucune popup, toutes les actions passent automatiquement">'+t('compte.auto')+'</button>'
    +'</div></div>'
    +'<div style="margin-top:14px;display:flex;align-items:center;gap:10px">'
    +'<span id="agent-local-status" style="font-size:13px;color:var(--mut)">'+t('compte.agent_local_attente')+'</span>'
    +'<button class="ghost" id="clear-chats-btn" style="font-size:12px;padding:5px 12px;margin-left:auto">'+t('compte.effacer_chats')+'</button>'
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

  // --- Langue ---
  const langueSel=$('#langue-select');
  if(langueSel){
    langueSel.value=(function(){try{return localStorage.getItem('neogen_langue')||'fr';}catch(e){return 'fr';}})();
    langueSel.onchange=async function(){
      var langue=this.value;
      definirLangue(langue);
      try{
        await fetch('/compte/langue',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),body:JSON.stringify({langue:langue})});
      }catch(e){}
      location.reload();
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
    if(typeof _injectUserCss==='function')_injectUserCss();
    loadCompte();
  };

  // --- Changer de compte : deconnecte puis rouvre le formulaire de connexion ---
  const swBtn=$('#switch-acct-btn');
  if(swBtn)swBtn.onclick=async()=>{
    const t=_authToken();
    if(t)await fetch('/auth/logout',{method:'POST',headers:{'Authorization':'Bearer '+t}}).catch(()=>{});
    localStorage.removeItem('neogen_auth_token');
    if(typeof _injectUserCss==='function')_injectUserCss();
    await loadCompte();
  };

  // --- Changer le mot de passe ---
  const pwBtn=$('#chg-pw-btn'),pwForm=$('#chg-pw-form');
  if(pwBtn&&pwForm)pwBtn.onclick=()=>{pwForm.style.display=pwForm.style.display==='none'?'flex':'none';};
  if(pwForm)pwForm.onsubmit=async(e)=>{
    e.preventDefault();
    const st=$('#chg-pw-status'),old=$('#chg-pw-old').value,nw=$('#chg-pw-new').value;
    st.textContent='...';st.style.color='var(--mut)';
    try{
      const r=await fetch('/auth/change-password',{method:'POST',
        headers:{'Content-Type':'application/json',..._authHdrs()},
        body:JSON.stringify({ancien:old,nouveau:nw})});
      const d=await r.json().catch(()=>({}));
      if(r.ok){st.textContent='Mot de passe modifie';st.style.color='var(--ok)';$('#chg-pw-old').value='';$('#chg-pw-new').value='';setTimeout(()=>{pwForm.style.display='none';st.textContent='';},2000);}
      else{st.textContent=d.detail||'Erreur';st.style.color='#ef4444';}
    }catch(err){st.textContent='Erreur reseau';st.style.color='#ef4444';}
  };

  // --- Abonnement Stripe : etat + resiliation ---
  _loadAbonnement();

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

/* Abonnement Stripe : etat + resiliation (section Compte) */
async function _loadAbonnement(){
  const mount=$('#abonnement-mount');if(!mount)return;
  mount.innerHTML='';
  let d;
  try{d=await(await fetch('/premium/abonnement',{headers:_authHdrs()})).json();}catch(e){return;}
  if(!d||!d.actif||!d.abonnement)return; // gratuit ou pas d'abonnement : rien a afficher
  const ab=d.abonnement;
  const fin=ab.fin_periode?new Date(ab.fin_periode*1000).toLocaleDateString('fr-FR'):'';
  const statutLabel={'active':'Actif','trialing':'Essai en cours','past_due':'Paiement en retard'}[ab.statut]||ab.statut;
  let corps='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
    +'<span style="font-size:14px;font-weight:700">'+esc(statutLabel)+'</span>'
    +'<span class="tag ok" style="display:inline-block">'+esc((d.palier||'').toUpperCase())+'</span></div>';
  if(ab.annulation_prevue){
    corps+='<div style="font-size:12px;color:#f59e0b;margin-bottom:10px">Resiliation programmee — acces conserve jusqu\'au '+esc(fin)+'.</div>'
      +'<button class="ghost" id="ab-reactiver-btn" style="font-size:12px;padding:7px 14px">Reprendre mon abonnement</button>';
  }else{
    corps+='<div style="font-size:12px;color:var(--mut);margin-bottom:10px">Prochain renouvellement le '+esc(fin)+'.</div>'
      +'<button class="ghost" id="ab-annuler-btn" style="font-size:12px;padding:7px 14px;border-color:rgba(239,68,68,.4);color:#ef4444">Resilier mon abonnement</button>';
  }
  corps+='<span id="ab-status" style="font-size:12px;margin-left:10px"></span>';
  mount.innerHTML='<div class="panel glass" style="margin-bottom:18px">'
    +'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Mon abonnement</div>'
    +corps+'</div>';
  const annBtn=$('#ab-annuler-btn'),reBtn=$('#ab-reactiver-btn'),abSt=$('#ab-status');
  if(annBtn)annBtn.onclick=async()=>{
    if(!confirm('Programmer la resiliation ? Tu gardes l\'acces jusqu\'a la fin de la periode payee.'))return;
    annBtn.disabled=true;abSt.textContent='...';abSt.style.color='var(--mut)';
    try{
      const r=await fetch('/premium/annuler',{method:'POST',headers:_authHdrs()});
      const j=await r.json().catch(()=>({}));
      if(r.ok){_loadAbonnement();}else{abSt.textContent=j.detail||'Erreur';abSt.style.color='#ef4444';annBtn.disabled=false;}
    }catch(e){abSt.textContent='Erreur reseau';abSt.style.color='#ef4444';annBtn.disabled=false;}
  };
  if(reBtn)reBtn.onclick=async()=>{
    reBtn.disabled=true;abSt.textContent='...';abSt.style.color='var(--mut)';
    try{
      const r=await fetch('/premium/reactiver',{method:'POST',headers:_authHdrs()});
      const j=await r.json().catch(()=>({}));
      if(r.ok){_loadAbonnement();}else{abSt.textContent=j.detail||'Erreur';abSt.style.color='#ef4444';reBtn.disabled=false;}
    }catch(e){abSt.textContent='Erreur reseau';abSt.style.color='#ef4444';reBtn.disabled=false;}
  };
}

/* Compte */
async function loadCompte(){
  const root=$('#compte-root');if(!root)return;
  const user=await _fetchMe();
  const panel=document.getElementById('mes-skills-panel');
  if(user){
    await renderCompteConnecte(root,user);
    if(panel)panel.style.display='';
    loadMesSkills();
  }else{
    renderCompteAuth(root);
    if(panel)panel.style.display='none';
  }
}

/* Mes skills — espace personnel de creation (tout user connecte) */
async function loadMesSkills(){
  const panel=document.getElementById('mes-skills-panel');
  const liste=document.getElementById('mes-skills-liste');
  if(!panel||!liste)return;
  if(!_authToken()){panel.style.display='none';return;}
  panel.style.display='';
  try{
    const r=await fetch('/savoir/evolution/cellules',{headers:_authHdrs()});
    if(!r.ok){liste.innerHTML='<div style="opacity:.4;font-size:12px;padding:10px">Chargement impossible.</div>';return;}
    const d=await r.json();
    const cells=(d.cellules)||[];
    if(!cells.length){liste.innerHTML='<div style="text-align:center;padding:14px;opacity:.4;font-size:12px">Aucun skill forge. Decris un besoin ci-dessus pour commencer.</div>';return;}
    liste.innerHTML='';
    for(const cell of cells){
      const el=document.createElement('div');
      el.style.cssText='padding:10px 12px;background:rgba(16,185,129,.05);border-radius:8px;margin-bottom:6px;font-size:12px;border:1px solid rgba(16,185,129,.18)';
      const dt=cell.ts?new Date(cell.ts*1000).toLocaleDateString():'';
      const det=document.createElement('details');
      det.innerHTML='<summary style="cursor:pointer;list-style:none">'
        +'<span style="font-weight:700;color:#10b981">&#9889; '+esc(cell.nom||'')+'</span> '
        +'<span style="opacity:.7">'+esc(cell.description||'')+'</span>'
        +'<span style="float:right;opacity:.5">score '+(cell.score||'--')+' &middot; '+esc(dt)+'</span>'
        +'</summary>';
      const corps=document.createElement('div');
      corps.style.cssText='margin-top:8px';
      corps.innerHTML='<div style="opacity:.6;margin-bottom:6px">Verdict : '+esc(cell.verdict||'')
        +(cell.test&&cell.test.resume?' &middot; test : '+esc(cell.test.resume):'')+'</div>'
        +'<pre style="background:rgba(0,0,0,.35);border-radius:8px;padding:10px;overflow:auto;font-size:11px;max-height:220px;white-space:pre-wrap" id="mscode-'+esc(cell.nom)+'">Chargement…</pre>';
      det.appendChild(corps);
      det.addEventListener('toggle',async function(){
        if(!det.open)return;
        const pre=document.getElementById('mscode-'+cell.nom);
        if(pre&&pre.dataset.charge)return;
        try{
          const rc=await fetch('/savoir/evolution/cellules/'+encodeURIComponent(cell.nom),{headers:_authHdrs()});
          const dc=await rc.json();
          if(pre){pre.textContent=dc.code||'(code indisponible)';pre.dataset.charge='1';}
        }catch(e){if(pre)pre.textContent='Erreur de chargement';}
      });
      el.appendChild(det);
      liste.appendChild(el);
    }
  }catch(e){}
}

async function forgerMonSkill(btn){
  const besoin=(document.getElementById('ms-besoin')||{}).value||'';
  const titre=(document.getElementById('ms-titre')||{}).value||'';
  const err=document.getElementById('ms-forge-erreur');
  if(!besoin.trim()){if(err){err.textContent='Decris ton besoin.';err.style.display='';}return;}
  if(err)err.style.display='none';
  btn.disabled=true;btn.textContent='En cours...';
  try{
    const r=await fetch('/savoir/evolution/mon-skill',{
      method:'POST',
      headers:_llmHdrs(),
      body:JSON.stringify({besoin:besoin.trim(),titre:titre.trim()})
    });
    if(r.status===402){
      if(err){err.style.display='';_showUpsell(err,(await r.clone().json().catch(function(){return{};})).detail);}
      btn.disabled=false;btn.textContent='Forger';
      return;
    }
    const d=await r.json();
    if(!r.ok){
      if(err){err.textContent=d.detail||'Erreur ('+r.status+')';err.style.display='';}
      btn.disabled=false;btn.textContent='Forger';
      return;
    }
    /* bulle de progression — loadMesSkills est appele automatiquement dans _bulleProgression a la fin */
    _bulleProgression(d.job_id,titre||besoin.slice(0,40),null);
    btn.disabled=false;btn.textContent='Forger';
  }catch(e){
    if(err){err.textContent='Erreur reseau.';err.style.display='';}
    btn.disabled=false;btn.textContent='Forger';
  }
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
    // Points forts (ce qui marche deja bien)
    if(a.points_forts&&a.points_forts.length){
      h+='<div style="margin-top:10px;font-size:11px;font-weight:700;color:var(--ok)">POINTS FORTS</div>'
        +a.points_forts.map(function(p){return '<div style="font-size:12px;color:var(--mut)">&#10003; '+esc(p)+'</div>';}).join('');
    }
    // Sources analysees (transparence : la boucle lit vraiment plusieurs journaux)
    if(a.sources){
      h+='<div style="margin-top:8px;font-size:11px;color:var(--mut)">Sources : '
        +(a.sources.creations||0)+' creations, '+(a.sources.erreurs_journalisees||0)+' erreurs, '
        +(a.sources.decisions_membrane||0)+' decisions membrane</div>';
    }
    el.innerHTML=h;
    // Actions automatiques deja prises par la boucle fermee
    try{
      const j=await(await fetch('/auto-amelioration/journal')).json();
      if(j.actions&&j.actions.length){
        el.innerHTML+='<div style="margin-top:12px;font-size:11px;font-weight:700;color:var(--acc)">ACTIONS AUTO PRISES</div>'
          +j.actions.slice(0,6).map(function(ac){
            var quoi=ac.action==='lecon_cristallisee'?('Leçon cristallisee : '+esc(ac.competence||ac.type_erreur||'')):
                     ac.action==='pattern_memorise'?('Pattern memorise : '+esc(ac.domaine||'')):esc(ac.action||'');
            return '<div style="font-size:12px;color:var(--mut)">'+esc(ac.iso||'')+' &#8594; '+quoi+'</div>';
          }).join('');
      }
    }catch(e){}
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
function anlzTab(tab){
  document.querySelectorAll('[data-anlz-tab]').forEach(function(b){b.classList.toggle('active',b.dataset.anlzTab===tab);});
  document.querySelectorAll('[data-anlz-pane]').forEach(function(p){p.style.display=p.dataset.anlzPane===tab?'':'none';});
  if(tab==='ingenieur'&&typeof loadIngenieur==='function')loadIngenieur();
}
function loadMarketing(){
  /* Marketing section ne charge pas de donnees dynamiques pour l'instant — placeholder pour extensions futures */
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
      models:['claude-opus-4-8','claude-sonnet-5','claude-haiku-4-5-20251001','claude-fable-5'],
      ph:'sk-ant-api03-...'},
    openai:{label:'OpenAI / GPT',check:k=>k.trim().length>=8,
      models:['gpt-5.5','gpt-5.2','gpt-5-mini','o3','gpt-4.1'],
      ph:'sk-proj-...'},
    gemini:{label:'Gemini',check:k=>k.trim().length>=8,
      models:['gemini-3.1-pro-preview','gemini-3.5-flash','gemini-3.1-flash-lite','gemini-2.5-pro'],
      ph:'AIzaSy... ou AQ....'},
    deepseek:{label:'DeepSeek',check:k=>k.trim().length>=8,
      models:['deepseek-v4-flash','deepseek-v4-pro'],
      ph:'API key DeepSeek...'},
    mistral:{label:'Mistral',check:k=>k.trim().length>=8,
      models:['mistral-large-latest','mistral-small-latest','codestral-latest','ministral-3-8b'],
      ph:'API key Mistral...'},
    moonshot:{label:'Kimi (Moonshot)',check:k=>k.trim().length>=8,
      models:['kimi-k2.7-code','kimi-k2.6','kimi-k2.7-code-highspeed','kimi-k2.5','moonshot-v1-128k'],
      ph:'sk-... (cle Moonshot)'},
    glm:{label:'GLM-5.2 (z.ai)',check:k=>k.trim().length>=20,
      models:['glm-4.5-flash','glm-4.5','glm-5.2'],
      ph:'xxxxxxx.NI3rc... (cle z.ai / Zhipu AI)'},
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
      var dejaPayes=['anthropic','openai','gemini','deepseek','mistral','moonshot','glm'].filter(function(pr){return pr!==curProv && localStorage.getItem('neogen_key_'+pr);});
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
  /* ── PRODUCTIVITE & NOTES ── */
  notion:{name:'Notion',icon:'◰',cat:'Productivite & Notes',type:'key',
    keyPh:'ntn_... (Integration Token)',
    desc:'Notes, bases, projets — pages et databases accessibles depuis les agents'},
  googledrive:{name:'Google Drive',icon:'▲',cat:'Productivite & Notes',type:'oauth',
    oauthUrl:'https://drive.google.com',
    desc:'Stockage Google — lecture et recherche de fichiers dans les analyses'},
  gmail:{name:'Gmail',icon:'◁',cat:'Productivite & Notes',type:'oauth',
    oauthUrl:'https://mail.google.com',
    desc:'Emails — lire, envoyer et archiver depuis les agents'},
  gcalendar:{name:'Google Calendar',icon:'◻',cat:'Productivite & Notes',type:'oauth',
    oauthUrl:'https://calendar.google.com',
    desc:'Agenda — consulter et creer des evenements depuis les agents'},
  airtable:{name:'Airtable',icon:'⊡',cat:'Productivite & Notes',type:'key',
    keyPh:'pat... (Personal Access Token)',
    desc:'Bases de donnees visuelles — lecture et mise a jour des tables depuis les agents'},
  todoist:{name:'Todoist',icon:'◑',cat:'Productivite & Notes',type:'key',
    keyPh:'Token API Todoist...',
    desc:'Taches et projets — creer et suivre les actions depuis les agents'},
  trello:{name:'Trello',icon:'◲',cat:'Productivite & Notes',type:'key',
    keyPh:'APIKey:Token (format cle:token)',
    desc:'Tableaux Kanban — cartes, listes et boards depuis les agents'},
  /* ── COMMUNICATION ── */
  slack:{name:'Slack',icon:'⊛',cat:'Communication',type:'key',
    keyPh:'xoxb-... (Bot Token)',
    desc:'Messagerie equipe — envoyer des messages et lire les canaux depuis les agents'},
  discord:{name:'Discord',icon:'⊚',cat:'Communication',type:'key',
    keyPh:'Token Bot Discord...',
    desc:'Communaute — poster dans les canaux et interagir avec les serveurs'},
  telegram:{name:'Telegram',icon:'▷',cat:'Communication',type:'key',
    keyPh:'Token bot Telegram (BotFather)',
    desc:'Bot Telegram — notifications et commandes depuis les agents'},
  /* ── CRM & MARKETING ── */
  hubspot:{name:'HubSpot',icon:'◒',cat:'CRM & Marketing',type:'key',
    keyPh:'Bearer Token HubSpot (Private App)...',
    desc:'CRM — contacts, deals et entreprises dans les analyses commerciales'},
  brevo:{name:'Brevo',icon:'◊',cat:'CRM & Marketing',type:'key',
    keyPh:'xkeysib-... (API Key Brevo)',
    desc:'Email & SMS marketing — campagnes et listes de contacts'},
  mailchimp:{name:'Mailchimp',icon:'◓',cat:'CRM & Marketing',type:'key',
    keyPh:'API Key Mailchimp (key-us0)...',
    desc:'Email marketing — audiences et statistiques de campagnes'},
  calendly:{name:'Calendly',icon:'◔',cat:'CRM & Marketing',type:'key',
    keyPh:'Personal Access Token Calendly...',
    desc:'Prise de RDV — evenements et disponibilites dans le workflow'},
  /* ── RECHERCHE & DOCS ── */
  notebooklm:{name:'NotebookLM',icon:'◫',cat:'Recherche & Docs',type:'oauth',
    oauthUrl:'https://notebooklm.google.com',
    desc:'Synthese documentaire Google — sources disponibles dans Composition'},
  deerflow:{name:'DeerFlow',icon:'⊞',cat:'Recherche & Docs',type:'url',
    urlPh:'https://deerflow.netroia.tech',
    desc:'Recherche web multi-step — injecte des sources dans la forge'},
  perplexity:{name:'Perplexity',icon:'✦',cat:'Recherche & Docs',type:'key',
    keyPh:'pplx-... (API Key)',
    desc:'Recherche web IA — reponses sourcees en temps reel dans les analyses'},
  tavily:{name:'Tavily',icon:'⊝',cat:'Recherche & Docs',type:'key',
    keyPh:'tvly-... (API Key)',
    desc:'API recherche pour agents — resultats structures et filtres web'},
  /* ── VIDEO & CREATION ── */
  elevenlabs:{name:'ElevenLabs',icon:'◌',cat:'Video & Creation',type:'key',
    keyPh:'Cle API ElevenLabs...',
    desc:'Synthese vocale IA — generer des fichiers audio depuis les agents'},
  runway:{name:'Runway',icon:'◕',cat:'Video & Creation',type:'key',
    keyPh:'Cle API Runway...',
    desc:'Generation video IA — clips et effets visuels depuis les agents'},
  magnific:{name:'Magnific',icon:'⊕',cat:'Video & Creation',bientot:true},
  youtube:{name:'YouTube',icon:'▶',cat:'Video & Creation',bientot:true},
  /* ── RESEAUX SOCIAUX ── */
  xtwitter:{name:'X (Twitter)',icon:'✕',cat:'Reseaux sociaux',type:'key',
    keyPh:'Bearer Token X (Twitter API v2)...',
    desc:'Reseau X — publier, lire et analyser les mentions depuis les agents'},
  pinterest:{name:'Pinterest',icon:'◳',cat:'Reseaux sociaux',type:'key',
    keyPh:'Access Token Pinterest...',
    desc:'Pinterest — epingles et tableaux dans les workflows creation'},
  reddit:{name:'Reddit',icon:'⊖',cat:'Reseaux sociaux',type:'key',
    keyPh:'Client ID:Secret Reddit',
    desc:'Reddit — veille, posts et commentaires dans les analyses'},
  tiktok:{name:'TikTok',icon:'◈',cat:'Reseaux sociaux',bientot:true},
  instagram:{name:'Instagram',icon:'◉',cat:'Reseaux sociaux',bientot:true},
  linkedin:{name:'LinkedIn',icon:'◎',cat:'Reseaux sociaux',bientot:true},
  /* ── E-COMMERCE & PAIEMENT ── */
  shopify:{name:'Shopify',icon:'⊠',cat:'E-commerce & Paiement',bientot:true},
  /* ── INFRA & DEV ── */
  github:{name:'GitHub',icon:'⊙',cat:'Infra & Dev',type:'key',
    keyPh:'ghp_... (Personal Access Token)',
    desc:'GitHub — repos, issues et pull requests depuis les agents'},
  linear:{name:'Linear',icon:'⊏',cat:'Infra & Dev',type:'key',
    keyPh:'lin_api_... (API Key)',
    desc:'Issue tracking — tickets, cycles et projets dev depuis les agents'},
  figma:{name:'Figma',icon:'⊐',cat:'Infra & Dev',type:'key',
    keyPh:'Personal Access Token Figma...',
    desc:'Design — lecture des fichiers et composants pour les productions'},
  vercel:{name:'Vercel',icon:'▼',cat:'Infra & Dev',type:'key',
    keyPh:'Token Vercel...',
    desc:'Deploiement — projets, domaines et logs depuis les agents'},
  supabase:{name:'Supabase',icon:'⊓',cat:'Infra & Dev',type:'key',
    keyPh:'Service Role Key Supabase...',
    desc:'Base de donnees Postgres — requetes et mutations via API REST'},
  n8n:{name:'n8n',icon:'⊗',cat:'Infra & Dev',bientot:true},
  /* ── JURIDIQUE & ADMIN ── */
  openlegi:{name:'OpenLegi',icon:'⊜',cat:'Juridique & Admin',type:'key',
    keyPh:'Token openlegi.fr...',
    desc:'Legifrance : codes, jurisprudence, JORF — enrichit le scan et le conseil'},
  inpi:{name:'INPI',icon:'⊟',cat:'Juridique & Admin',bientot:true},
};
const INTEG_CAT_ORDER=['Productivite & Notes','Communication','CRM & Marketing','Recherche & Docs','Video & Creation','Reseaux sociaux','E-commerce & Paiement','Infra & Dev','Juridique & Admin'];

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
    _syncIntegServeur(name,val,def.type);
    if(statut)statut.innerHTML='<span class="tag ok">verifie et actif</span>';
    renderIntegGrid();updateOutilsActifs();
  } else if(res.manuel){
    // Non verifiable automatiquement (ex oauth) : actif mais marque "non verifie"
    _iSet(name,{active:true,key:val,source:'user',verifie:false});
    _syncIntegServeur(name,val,def.type);
    if(statut)statut.innerHTML='<span class="tag warn">actif (non verifie)</span> <span style="color:var(--mut);font-size:11px">'+esc(res.erreur||'')+'</span>';
    renderIntegGrid();updateOutilsActifs();
  } else {
    // Echec : NE PAS activer, rouge + raison
    if(statut)statut.innerHTML='<span class="tag ko">activation impossible</span> <span style="color:var(--ko);font-size:11px">'+esc(res.erreur||'')+'</span>';
  }
};

function _syncIntegServeur(name,key,type){
  fetch('/integrations/activer',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name,key,type})}).catch(function(){});
}

window.desactiverInteg=function(name){
  _iClear(name);
  fetch('/integrations/activer/'+encodeURIComponent(name),{method:'DELETE'}).catch(function(){});
  renderIntegGrid();updateOutilsActifs();
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
const SECTIONS=['cerveau','creation','production','compte','analyse','evolution','marketing','integrations','don'];
function routeHash(){
  const h=location.hash.slice(1);
  if(h&&SECTIONS.includes(h))showSection(h);
}
window.addEventListener('popstate',routeHash);
routeHash();

/* ===== RPA STATUS POLLING ===== */
let _rpaInterval=null;
var _rpaConnected=false;
async function pollRpaStatus(){
  if(!_authToken())return; /* pas connecte : /rpa/status exige un compte, evite le 401 qui rouvrirait le login */
  try{
    const r=await(await fetch('/rpa/status',{headers:_authHdrs()})).json();
    const dot=$('#rpa-dot'), lbl=$('#rpa-label'), sub=$('#rpa-sub'), qb=$('#rpa-queue-badge');
    const wasConnected=_rpaConnected;
    _rpaConnected=!!r.connected;
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
    // Mettre a jour le bloc remote-control selon connexion
    if(wasConnected!==_rpaConnected&&window._renderRemoteConnState)window._renderRemoteConnState();
  }catch(e){}
}
_rpaInterval=setInterval(pollRpaStatus,3000);
pollRpaStatus();

/* ===== APPRENTISSAGE CONTINU ===== */
async function refreshContinuous(){
  const cb=$('#cont-learn-cb'),st=$('#cont-learn-status');
  if(!cb)return;
  if(!_authToken())return; /* pas connecte : /rpa/continuous exige un compte, evite le 401 qui rouvrirait le login */
  try{
    const d=await(await fetch('/rpa/continuous',{headers:_authHdrs()})).json();
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

/* ===== /remote-control ===== */
(function(){
  var _remoteActive=false;
  var btn=$('#btn-remote-control');
  var st=$('#remote-control-status');
  if(!btn)return;
  async function _syncRemote(){
    try{var r=await(await fetch('/rpa/settings')).json();
      _remoteActive=(r.consent_level==='auto');
      _renderRemote();}catch(e){}
  }
  function _renderRemote(){
    // Si agent deconnecte : section passive, pas d'alerte trompeuse
    if(!_rpaConnected){
      btn.textContent='Prendre le contrôle';
      btn.style.background='';btn.style.borderColor='';btn.style.color='';btn.disabled=true;btn.title='Agent déconnecté';
      if(st){st.textContent='Agent non connecté — lance rpa_agent.py pour activer.';st.style.color='var(--mut)';}
      return;
    }
    btn.disabled=false;btn.title='';
    if(_remoteActive){
      btn.textContent='Arrêter le contrôle';
      btn.style.background='rgba(220,38,38,.12)';
      btn.style.borderColor='rgba(220,38,38,.4)';
      btn.style.color='var(--ko)';
      if(st){st.textContent='Mode contrôle actif — l\'agent agit sans popup. Coin haut-gauche = arrêt d\'urgence.';st.style.color='var(--ko)';}
    }else{
      btn.textContent='Prendre le contrôle';
      btn.style.background='';btn.style.borderColor='';btn.style.color='';
      if(st){st.textContent='';st.style.color='';}
    }
  }
  window._renderRemoteConnState=_renderRemote;
  btn.onclick=async function(){
    if(!_rpaConnected)return;
    var lvl=_remoteActive?'sequence':'auto';
    try{await fetch('/rpa/settings',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({consent_level:lvl,sequence_duration:120})});
      _remoteActive=!_remoteActive;_renderRemote();}catch(e){}
  };
  _syncRemote();
})();

/* ===== /goal : mode objectif autonome ===== */
(function(){
  var btn=$('#btn-goal-launch');
  var log=$('#goal-log');
  var inp=$('#goal-input');
  if(!btn||!inp)return;
  var _goalRunning=false;
  btn.onclick=async function(){
    if(_goalRunning)return;
    var objectif=(inp.value||'').trim();
    if(!objectif){if(log)log.textContent='Saisis un objectif avant de lancer.';return;}
    _goalRunning=true;btn.disabled=true;btn.textContent='En cours...';
    if(log)log.textContent='Analyse de l\'objectif...\n';
    try{
      var r=await(await fetch('/rpa/goal',{method:'POST',
        headers:_llmHdrs(),
        body:JSON.stringify({objectif})})).json();
      if(r.detail){if(log)log.textContent+='Erreur : '+errMsg(r.detail)+'\n';return;}
      // Si infos manquantes -> afficher la question et attendre
      if(r.infos_manquantes&&r.infos_manquantes.length){
        if(log)log.textContent+='Information(s) requise(s) :\n'+r.infos_manquantes.map(function(x){return'  • '+x}).join('\n')+'\n\nRéponds dans le champ ci-dessous et relance.';
        inp.value=objectif+'\n\n[INFOS: ]';
        return;
      }
      if(log){log.textContent+=r.rapport||r.detail||JSON.stringify(r);}
    }catch(e){if(log)log.textContent+='Erreur réseau : '+errMsg(e);}
    finally{_goalRunning=false;btn.disabled=false;btn.textContent='Lancer';}
  };
})();

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
  // Redirect ingenieur → onglet ingenieur dans Dev & Analyse
  if(name==='ingenieur'){_origShowSection('analyse');anlzTab('ingenieur');return;}
  _origShowSection(name);
  if(name==='integrations'){loadImitationList();pollRpaStatus();}
  if(name==='cerveau'&&window.loadSkills){loadSkills();if(window.loadMemoire)loadMemoire();if(window.loadTaches)loadTaches();if(window.loadBebeAgents)loadBebeAgents();}
  if(name==='marketing'&&window.loadMarketing){loadMarketing();}
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
  s=s.replace(/\/fichiers\/rapports\/(rapport_[a-f0-9]{8}\.(docx|pdf|xlsx|csv|pptx|html))/g,function(_,fn){var icons={'docx':'📄','pdf':'📕','xlsx':'📊','csv':'📋','pptx':'📽️','html':'🌐'};var ext=fn.split('.').pop();var ic=icons[ext]||'📎';return '<a href="/fichiers/rapports/'+fn+'" download="'+fn+'" style="color:var(--acc);font-weight:600">'+ic+' Télécharger '+fn+'</a>';});
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
    +'<input type="checkbox" id="ececb-'+role+'"><span>'+svgIcon('eco',13)+' Eco</span></label>'
    +'<button class="agent-chat-convs-btn" id="acconvs-'+role+'" title="Conversations">'+svgIcon('conversations',15)+'</button>'
    +'<label class="eco-toggle eclair-toggle" id="aceclair-'+role+'" title="Mode ÉCLAIR : compression intelligente du contexte — économisez 30 à 50% sur vos tokens lors des longues conversations (détection de dérive incluse)"><input type="checkbox" id="eclrcb-'+role+'"><span>'+svgIcon('eclair',13)+' ÉCLAIR</span></label>'
    +'<button class="agent-chat-clear" id="acclr-'+role+'" title="Effacer la conversation">'+svgIcon('close',14)+'</button></div>'
    +'<div class="agent-convs-panel" id="aconvp-'+role+'" style="display:none"></div>'
    +'<div class="agent-chat-log" id="aclog-'+role+'"></div>'
    +'<div class="agent-chat-input" style="flex-direction:column;align-items:stretch">'
    +'<div class="ac-img-prev" id="acimgprev-'+role+'"></div>'
    +'<div id="acadv-'+role+'" class="model-advisor" style="display:none"></div>'
    +'<div style="display:flex;gap:8px;align-items:flex-end">'
    +'<textarea id="acin-'+role+'" rows="1" placeholder="Parler a '+esc(titre)+'... (Ctrl+V = coller images)"></textarea>'
    +'<input type="file" id="acfile-'+role+'" accept="image/*,.pdf,.pptx,.ppt,.docx,.doc,.txt,.md,.csv" multiple style="display:none">'
    +'<button class="ghost" id="acattach-'+role+'" title="Joindre images ou fichier (multi-sélection OK)" style="padding:10px 12px;border-radius:12px;flex-shrink:0">'+svgIcon('camera',16)+'</button>'
    +'<button class="agent-chat-send" id="acsend-'+role+'">Envoyer</button>'
    +'</div></div>';
  const log=mount.querySelector('#aclog-'+role);
  const inp=mount.querySelector('#acin-'+role);
  const btn=mount.querySelector('#acsend-'+role);
  const clr=mount.querySelector('#acclr-'+role);
  const ecocb=mount.querySelector('#ececb-'+role);
  const fileIn=mount.querySelector('#acfile-'+role);
  const attachBtn=mount.querySelector('#acattach-'+role);
  const imgPrev=mount.querySelector('#acimgprev-'+role);
  let _images=[];  // [{b64, mime}] multi-images
  let _fichierB64=null,_fichierNom='';
  function _renderImgPrev(){
    if(!imgPrev)return;
    if(!_images.length&&!_fichierB64){imgPrev.style.display='none';imgPrev.innerHTML='';return;}
    imgPrev.style.display='flex';
    imgPrev.style.flexWrap='wrap';
    imgPrev.style.gap='6px';
    var html='';
    _images.forEach(function(im,idx){
      html+='<span style="position:relative;display:inline-block">'
        +'<img src="data:'+im.mime+';base64,'+im.b64+'" alt="img" style="height:48px;width:48px;object-fit:cover;border-radius:6px;border:1px solid rgba(255,255,255,.15)">'
        +'<span data-idx="'+idx+'" style="position:absolute;top:-4px;right:-4px;background:var(--ko,#ef4444);color:#fff;border-radius:50%;width:16px;height:16px;font-size:10px;line-height:16px;text-align:center;cursor:pointer;font-weight:700">×</span>'
        +'</span>';
    });
    if(_fichierB64){
      var ext=_fichierNom.split('.').pop().toLowerCase();
      var ico=ext==='pdf'?'📄':ext==='pptx'||ext==='ppt'?'📊':ext==='docx'||ext==='doc'?'📝':'📎';
      html+=ico+' <span style="font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:120px">'+esc(_fichierNom)+'</span>'
        +'<span id="clrdoc-'+role+'" style="cursor:pointer;padding:0 4px;font-weight:700;color:var(--ko)">×</span>';
    }
    imgPrev.innerHTML=html;
    imgPrev.querySelectorAll('[data-idx]').forEach(function(x){
      x.onclick=function(){var i=parseInt(this.getAttribute('data-idx'));_images.splice(i,1);_renderImgPrev();};
    });
    var xd=imgPrev.querySelector('#clrdoc-'+role);if(xd)xd.onclick=function(){_fichierB64=null;_fichierNom='';_renderImgPrev();};
  }
  function _clearImg(){_images=[];if(fileIn)fileIn.value='';_renderImgPrev();}
  function _clearDoc(){_fichierB64=null;_fichierNom='';if(fileIn)fileIn.value='';_renderImgPrev();}
  function _setDoc(file){
    if(!file)return;
    _fichierNom=file.name;
    const fr=new FileReader();
    fr.onload=function(e){_fichierB64=e.target.result.split(',')[1];_renderImgPrev();};
    fr.readAsDataURL(file);
  }
  function _addImg(file){
    if(!file||!file.type.startsWith('image/'))return;
    const mime=file.type||'image/png';
    const fr=new FileReader();
    fr.onload=function(e){
      _images.push({b64:e.target.result.split(',')[1],mime:mime});
      _renderImgPrev();
    };
    fr.readAsDataURL(file);
  }
  if(attachBtn)attachBtn.onclick=function(){if(fileIn)fileIn.click();};
  if(fileIn)fileIn.onchange=function(e){
    var files=e.target.files;if(!files||!files.length)return;
    for(var i=0;i<files.length;i++){
      if(files[i].type.startsWith('image/')){_addImg(files[i]);}
      else if(i===0){_setDoc(files[i]);}  // un seul fichier doc à la fois
    }
    fileIn.value='';
  };
  inp.addEventListener('paste',function(e){
    var items=e.clipboardData&&e.clipboardData.items;if(!items)return;
    for(var i=0;i<items.length;i++){if(items[i].type.startsWith('image/')){_addImg(items[i].getAsFile());}}
  });
  if(ecocb){
    ecocb.checked=localStorage.getItem('neogen_eco')!=='0';
    ecocb.onchange=function(){localStorage.setItem('neogen_eco',this.checked?'1':'0');
      document.querySelectorAll('[id^="ececb-"]').forEach(function(c){c.checked=ecocb.checked;});};
  }
  const eclrcb=mount.querySelector('#eclrcb-'+role);
  if(eclrcb){
    eclrcb.checked=localStorage.getItem('neogen_eclair')!=='0';
    eclrcb.onchange=function(){localStorage.setItem('neogen_eclair',this.checked?'1':'0');
      document.querySelectorAll('[id^="eclrcb-"]').forEach(function(c){c.checked=eclrcb.checked;});};
  }
  // ── Conversations multi-tours ────────────────────────────────────────────────
  let hist=[];
  let _convId=null;
  const _AKEY='neogen_active_conv_'+role;
  const _hasAuth=!!_authToken();
  function _genId(){return Math.random().toString(36).slice(2,10);}
  function add(cls,html){const d=document.createElement('div');d.className=cls;d.innerHTML=html;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
  function _renderMsg(m){if((m.role==='user'))add('ac-msg user',esc(m.content||''));else add('ac-msg agent','<div class="ac-md">'+_mdLite(m.content||'')+'</div>');}

  async function _syncConv(extra){
    if(!_hasAuth)return;
    if(!_convId)_convId=_genId();
    const fu=hist.find(function(m){return m.role==='user';});
    const title=(fu?fu.content.slice(0,45):'Conversation');
    const body=Object.assign({id:_convId,role:role,title:title,messages:hist.slice(-60)},extra||{});
    try{const r=await fetch('/agent/convs',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),body:JSON.stringify(body)});
      if(r.ok)localStorage.setItem(_AKEY,_convId);}catch(e){}
  }

  async function _newConv(){
    if(_convId&&hist.length>0){await _syncConv();}
    _convId=_genId();hist=[];log.innerHTML='';
    localStorage.setItem(_AKEY,_convId);
    add('ac-trace','&#128172; Nouvelle conversation');
  }

  async function _compact(){
    if(hist.length<6){add('ac-trace','&#9888; Pas assez de messages (minimum 6).');return;}
    const banner=add('ac-trace action','&#9203; Compression en cours…');
    try{
      await _syncConv({archived:true});
      const r=await fetch('/agent/compact',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),body:JSON.stringify({role:role,messages:hist})});
      if(!r.ok)throw new Error('erreur '+r.status);
      const d=await r.json();const summary=d.summary||'';
      _convId=_genId();hist=[{role:'assistant',content:'[Contexte r\xe9sum\xe9]\n\n'+summary}];
      log.innerHTML='';
      add('ac-msg agent','<div class="ac-md"><div style="opacity:.6;font-size:11px;margin-bottom:6px">&#128203; Contexte de la conversation pr\xe9c\xe9dente</div>'+_mdLite(summary)+'</div>');
      await _syncConv();banner.remove();
      add('ac-trace','&#10003; Conversation compress\xe9e — contexte pr\xe9serv\xe9');
    }catch(e){banner.innerHTML='&#9888; Erreur compression : '+esc(e.message||'');}
  }

  async function _loadConvPanel(){
    const panel=document.getElementById('aconvp-'+role);if(!panel)return;
    panel.innerHTML='<div style="padding:8px 12px;font-size:13px;opacity:.6">Chargement…</div>';
    const _nc='<button style="width:100%;padding:7px 12px;border-radius:8px;font-size:13px;cursor:pointer;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);color:inherit" id="_nc-'+role+'">&#9998; Nouvelle conversation</button>';
    if(!_hasAuth){panel.innerHTML='<div style="padding:8px 12px">'+_nc+'<div style="padding:6px 0 0;font-size:12px;opacity:.5">Connectez-vous pour sauvegarder</div></div>';document.getElementById('_nc-'+role).onclick=function(){panel.style.display='none';_newConv();};return;}
    try{
      const r=await fetch('/agent/convs?role='+encodeURIComponent(role),{headers:_authHdrs()});
      if(!r.ok)throw new Error('');
      const data=await r.json();const convs=data.convs||[];
      let html='<div style="padding:6px 12px 6px">'+_nc+'</div>';
      if(!convs.length){html+='<div style="padding:4px 12px 8px;font-size:12px;opacity:.5">Aucune conversation pr\xe9c\xe9dente</div>';}
      else{convs.forEach(function(c){
        const active=c.id===_convId;
        const dt=c.updated_at?new Date(c.updated_at+'Z').toLocaleDateString('fr',{day:'2-digit',month:'2-digit'}):'';
        html+='<div class="conv-item'+(active?' conv-active':'')+'" data-cid="'+esc(c.id)+'">'
          +'<div class="conv-title">'+esc(c.title||'Sans titre')+'</div>'
          +'<div class="conv-meta">'+esc(dt)+' · '+c.message_count+' msg'+(c.archived?' · archiv\xe9e':'')+'</div>'
          +'</div>';
      });}
      panel.innerHTML=html;
      document.getElementById('_nc-'+role).onclick=function(){panel.style.display='none';_newConv();};
      panel.querySelectorAll('.conv-item').forEach(function(el){
        el.onclick=async function(){
          const id=el.dataset.cid;if(id===_convId){panel.style.display='none';return;}
          panel.style.display='none';
          try{const rr=await fetch('/agent/convs/'+encodeURIComponent(id)+'?role='+encodeURIComponent(role),{headers:_authHdrs()});
            if(!rr.ok)return;const conv=await rr.json();
            _convId=conv.id;hist=conv.messages||[];log.innerHTML='';
            hist.forEach(_renderMsg);localStorage.setItem(_AKEY,_convId);
            add('ac-trace','&#128194; '+esc(conv.title||'Conversation charg\xe9e'));
          }catch(e){add('ac-trace action','&#9888; Erreur chargement');}
        };
      });
    }catch(e){panel.innerHTML='<div style="padding:10px 12px;font-size:13px;opacity:.5">Erreur chargement</div>';}
  }

  // Init : charger la conversation active depuis le backend, ou cr\xe9er une nouvelle
  (async function(){
    if(!_hasAuth){
      try{hist=JSON.parse(localStorage.getItem('neogen_chat_'+role)||'[]');}catch(e){hist=[];}
      hist.forEach(_renderMsg);return;
    }
    const saved=localStorage.getItem(_AKEY);
    if(saved){try{
      const r=await fetch('/agent/convs/'+encodeURIComponent(saved)+'?role='+encodeURIComponent(role),{headers:_authHdrs()});
      if(r.ok){const conv=await r.json();_convId=conv.id;hist=conv.messages||[];hist.forEach(_renderMsg);return;}
    }catch(e){}}
    _convId=_genId();localStorage.setItem(_AKEY,_convId);
  })();

  // Bouton conversations
  const _convBtn=mount.querySelector('#acconvs-'+role);
  const _convPanel=document.getElementById('aconvp-'+role);
  if(_convBtn&&_convPanel){_convBtn.onclick=function(){
    if(_convPanel.style.display==='none'){_convPanel.style.display='block';_loadConvPanel();}
    else{_convPanel.style.display='none';}
  };}

  if(clr)clr.onclick=function(){hist=[];log.innerHTML='';if(_hasAuth){_convId=_genId();localStorage.setItem(_AKEY,_convId);}else{try{localStorage.removeItem('neogen_chat_'+role);}catch(e){}}};
  async function envoyer(){
    const msg=(inp.value||'').trim();if(!msg)return;
    if(msg==='/compat'){inp.value='';await _compact();return;}
    inp.value='';inp.style.height='auto';btn.disabled=true;
    add('ac-msg user',esc(msg));
    let derniereReponse='';let forgeLine=null;
    try{
      const body={message:msg,historique:hist};
      if(_images.length){body.images=_images.map(function(i){return {b64:i.b64,mime:i.mime};});}_clearImg();
      if(_fichierB64){body.fichier_b64=_fichierB64;body.fichier_nom=_fichierNom;}_clearDoc();
      const resp=await fetch('/agent/'+role+'/chat/stream',{method:'POST',headers:_llmHdrs(),body:JSON.stringify(body)});
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
          else if(evt.type==='delegation'){var _tm=evt.tier?(' <span class="tag ok">'+esc(evt.tier)+'</span>'):'';add('ac-trace deleg','&#129504; &#8594; '+esc(evt.vers||'')+_tm+' : '+esc(evt.mission||''));}
          else if(evt.type==='forge'){var ft='&#9881; forge : '+esc(((evt.stade||'')+' '+(evt.msg||evt.message||'')).trim()).slice(0,180);if(!forgeLine){forgeLine=add('ac-trace action',ft);}else{forgeLine.innerHTML=ft;log.scrollTop=log.scrollHeight;}}
          else if(evt.type==='reponse'){var _rt=evt.texte||'';var _isStep=_rt.trimStart().startsWith('{')&&['"outil"','"pensee"','"arguments"'].filter(function(k){return _rt.includes(k);}).length>=2;if(_isStep){add('ac-trace action','&#9888; Reponse illisible (petit modele). Reformule ta demande.');}else{derniereReponse=_rt;if(_rt)add('ac-msg agent','<div class="ac-md">'+_mdLite(_rt)+'</div>');}}

          else if(evt.type==='erreur'){add('ac-trace action','&#9888; '+esc(evt.message||''));}
          else if(evt.type==='derive'){add('ac-trace','&#9889; Mode ÉCLAIR — dérive détectée (score '+esc(String(evt.score||''))+') : recadrage appliqué');}
          else if(evt.type==='audit'){add('ac-trace','&#128203; AUDIT ÉCLAIR\n'+esc(evt.texte||''));}
        }
      }
      if(derniereReponse){hist.push({role:'user',content:msg});hist.push({role:'assistant',content:derniereReponse});_syncConv();if(hist.length===30){setTimeout(function(){add('ac-trace','&#9889; Conversation longue — compression automatique…');_compact();},800);}else if(hist.length>30&&hist.length%10===0){add('ac-trace','&#9889; '+hist.length+' messages — tapez /compat pour compresser');}}
    }catch(e){add('ac-trace action','&#9888; '+errMsg(e));}
    finally{btn.disabled=false;inp.focus();}
  }
  btn.onclick=envoyer;
  inp.addEventListener('input',()=>{inp.style.height='auto';inp.style.height=Math.min(inp.scrollHeight,130)+'px';});
  inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();envoyer();}});
  // Model advisor — recommandation proactive avant envoi (debounce 600ms)
  var _advTimer=null;
  var _adv=$('#acadv-'+role);
  function _conseillerModele(txt){
    if(!_adv)return;
    if(!txt||txt.length<15){_adv.style.display='none';_adv.className='model-advisor';return;}
    fetch('/llm/recommander',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({demande:txt})}).then(function(r){return r.json();}).then(function(d){
      if(!_adv)return;
      var tier=d.tier||'moyen';
      var eco=localStorage.getItem('neogen_eco')!=='0';
      if(tier==='fort'&&eco){
        _adv.textContent='⚡ Tâche complexe — Eco actif. Désactiver Eco pour un meilleur résultat ?';
        _adv.className='model-advisor warn';_adv.style.display='block';
      }else if(tier==='leger'&&!eco){
        _adv.textContent='💡 Tâche simple — activer Eco pour économiser des tokens.';
        _adv.className='model-advisor';_adv.style.display='block';
      }else{_adv.style.display='none';}
    }).catch(function(){if(_adv)_adv.style.display='none';});
  }
  inp.addEventListener('input',function(){
    clearTimeout(_advTimer);
    _advTimer=setTimeout(function(){_conseillerModele((inp.value||'').trim());},600);
  });
}
document.querySelectorAll('.agent-chat-mount').forEach(buildChat);
_breath.scan(); /* agent chats viennent de recevoir .panel.glass -> les enregistrer maintenant */

// ===== PREFERENCES (dark mode + consentement + agent local) =====
// Dark mode = DEFAUT. Clair uniquement si choisi explicitement.
if(localStorage.getItem('neogen_dark_mode')==='0'){
  document.body.classList.remove('dark');
}else{
  document.body.classList.add('dark');
  if(window._setShaderDark)window._setShaderDark(true);
}

// ===== GENYTE WALLET + CREDITS =====
async function loadWallet(){
  var badge=document.getElementById('gen-wallet-badge'),
      detail=document.getElementById('gen-wallet-detail'),
      navBadge=document.getElementById('gen-wallet-nav'),
      hist=document.getElementById('gen-wallet-history');
  var t=(typeof _authToken==='function')?_authToken():null;
  if(!t){
    if(badge)badge.textContent='— GEN';
    if(detail)detail.textContent='Connecte-toi pour voir ton solde.';
    if(navBadge)navBadge.style.display='none';
    return;
  }
  try{
    var d=await(await fetch('/credits/me',{headers:_authHdrs?_authHdrs():{}})).json();
    if(badge)badge.textContent=d.solde+' GEN';
    if(navBadge){navBadge.textContent=d.solde+' GEN';navBadge.style.display='';}
    var palierLabel={'gratuit':'Gratuit','essential':'Essential','pro':'Pro','power':'Power','enterprise':'Enterprise'};
    if(detail){
      var mensuel=d.gen_mensuel||0;
      var pct=mensuel>0?Math.max(0,Math.min(100,Math.round(d.solde/mensuel*100))):0;
      var consomme=mensuel>0?Math.max(0,mensuel-d.solde):0;
      var barCol=pct<=15?'#ef4444':(pct<=40?'#f59e0b':'linear-gradient(90deg,#f59e0b,#fbbf24)');
      detail.innerHTML='<span style="color:var(--ok);font-weight:600">'+esc(palierLabel[d.palier]||d.palier)+'</span>'
        +(mensuel>0?' &middot; <span style="color:#f59e0b">'+mensuel+' GEN/mois</span>':'')
        +(mensuel>0?'<div style="margin-top:10px"><div style="height:9px;border-radius:6px;background:rgba(100,116,139,.2);overflow:hidden"><div style="height:100%;width:'+pct+'%;background:'+barCol+';border-radius:6px;transition:width .4s"></div></div>'
          +'<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--mut);margin-top:5px"><span><b style="color:#f59e0b">'+d.solde+'</b> GEN restants</span><span>'+consomme+' consommes ce mois</span></div></div>':'');
    }
    if(hist&&d.historique&&d.historique.length){
      hist.innerHTML='<div style="font-size:11px;color:var(--mut);margin-bottom:4px">Dernieres transactions</div>'
        +d.historique.slice(0,5).map(function(tx){
          var sign=tx.montant>0?'+':'';
          var col=tx.montant>0?'#10b981':'#f87171';
          var ts=new Date(tx.ts*1000).toLocaleDateString('fr-FR');
          return '<div style="display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px solid rgba(100,116,139,.1)">'
            +'<span>'+esc(tx.description||tx.type)+'</span>'
            +'<span style="color:'+col+';font-weight:700">'+sign+tx.montant+' GEN</span>'
            +'<span style="color:var(--mut)">'+ts+'</span></div>';
        }).join('');
    }
  }catch(e){if(detail)detail.textContent='Erreur de chargement.';}
}

async function _acheterPackGen(pack,btn){
  var t=(typeof _authToken==='function')?_authToken():null;
  if(!t){alert('Connecte-toi d\'abord.');return;}
  var old=btn.innerHTML;btn.disabled=true;btn.textContent='...';
  try{
    var r=await fetch('/credits/recharger',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({pack:pack})});
    var d=await r.json();
    if(r.ok&&d.url)window.location.href=d.url;
    else{alert(d.detail||'Indisponible.');btn.disabled=false;btn.innerHTML=old;}
  }catch(e){alert('Erreur reseau.');btn.disabled=false;btn.innerHTML=old;}
}

function _initPacksGen(){
  document.querySelectorAll('.pack-btn').forEach(function(btn){
    btn.onclick=function(){_acheterPackGen(btn.dataset.pack,btn);};
  });
}

// ===== TELEMETRIE RGPD =====
async function loadTelemetrie(){
  var t=(typeof _authToken==='function')?_authToken():null;
  if(!t)return;
  try{
    var d=await(await fetch('/telemetrie/consentement',{headers:_authHdrs?_authHdrs():{}})).json();
    var niv=d.niveau||'aucun';
    document.querySelectorAll('.tele-btn').forEach(function(b){
      b.classList.toggle('ok',b.dataset.niveau===niv);
    });
    var st=document.getElementById('tele-status');
    if(st)st.textContent=niv==='aucun'?'Pas de contribution active.':'Niveau actif : '+niv;
  }catch(e){}
}

function _initTelemetrie(){
  document.querySelectorAll('.tele-btn').forEach(function(btn){
    btn.onclick=async function(){
      var t=(typeof _authToken==='function')?_authToken():null;
      if(!t){alert('Connecte-toi d\'abord.');return;}
      try{
        var r=await fetch('/telemetrie/consentement',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({niveau:btn.dataset.niveau})});
        var d=await r.json();
        if(d.ok){
          loadTelemetrie();
          if(d.recompense)alert(d.recompense);
        }
      }catch(e){}
    };
  });
}

// ===== TARIFS MULTI-PALIERS =====
var _tarifPeriod='mensuel';
var _PALIERS=[
  {cle:'essential',label:'Essential',prix:{mensuel:'14,99',annuel:'10,49'},couleur:'#16c65e',
   features:[
     '1 500 GEN/mois',
     '4 providers IA + local',
     'Multi-agents · RPA · Apprentissage',
     'Vision active · Crons',
     '5 "Donner vie"/mois · 15 applis · 7 deploiements',
     '10 Mode Juge inclus/mois (puis GEN)',
     '⚡ Mode ECLAIR : -30 a -50% tokens',
   ]},
  {cle:'pro',label:'Pro',prix:{mensuel:'29,99',annuel:'20,99'},couleur:'#00c4a7',
   features:[
     '4 500 GEN/mois',
     '6 providers IA + local',
     'Multi-agents · RPA · Apprentissage',
     'Vision active · Crons illimites · Webhook & API',
     '15 "Donner vie"/mois · 50 applis · 25 deploiements',
     'Mode Juge illimite inclus',
     '⚡ Mode ECLAIR : -30 a -50% tokens',
   ]},
  {cle:'power',label:'Power',prix:{mensuel:'49,99',annuel:'34,99'},couleur:'#4ade80',
   features:[
     '12 000 GEN/mois',
     'Tous providers IA + local',
     'Multi-agents · RPA · Apprentissage',
     'Vision active · Crons illimites · Webhook & API',
     '50 "Donner vie"/mois · 200 applis · 100 deploiements',
     'Mode Juge illimite inclus',
     '⚡ Mode ECLAIR : -30 a -50% tokens',
   ]},
  {cle:'enterprise',label:'Enterprise',prix:{mensuel:'Sur mesure',annuel:'Sur mesure'},couleur:'#00ffaa',contact:true,
   features:[
     'GEN illimites',
     'Infrastructure isolee',
     'SLA 99,9% garanti',
     'Support dedie',
     'Contrat personnalise',
   ]},
];

function renderTarifs(palierActuel){
  var grid=document.getElementById('tarifs-grid');
  if(!grid)return;
  grid.innerHTML=_PALIERS.map(function(p){
    var actif=p.cle===palierActuel;
    var prix=p.prix[_tarifPeriod];
    var per=_tarifPeriod==='annuel'?'/mois (annuel)':'/mois';
    var prixHtml=p.contact
      ?'<div style="font-size:16px;font-weight:700;color:'+p.couleur+';margin-bottom:6px">Sur mesure</div>'
      :'<div style="font-size:18px;font-weight:800;color:var(--txt);margin-bottom:6px">'+prix+'&#8364;<span style="font-size:10px;font-weight:400;color:var(--mut)">'+per+'</span></div>';
    var btnHtml=actif?'<button class="ghost" disabled style="width:100%;font-size:11px;color:'+p.couleur+';opacity:.85;cursor:default">&#10003; Plan actuel</button>'
      :p.contact?'<button class="ghost tarif-contact-btn" style="width:100%;font-size:11px;color:'+p.couleur+';border-color:'+p.couleur+'">Nous contacter</button>'
      :'<button class="ghost tarif-upgrade-btn" data-palier="'+p.cle+'" style="width:100%;font-size:11px;color:'+p.couleur+'">Choisir '+esc(p.label)+'</button>';
    return '<div class="plan-card'+(actif?' plan-card-actif':'')+'" style="box-shadow:inset 0 1px 0 rgba(255,255,255,.10),inset 0 -14px 26px rgba(0,0,0,.20),0 0 28px '+p.couleur+'22,0 16px 40px rgba(0,0,0,.45)">'
      +'<div style="font-size:12px;font-weight:700;color:'+p.couleur+';margin-bottom:4px">'+esc(p.label)+'</div>'
      +prixHtml
      +'<ul style="font-size:11px;color:var(--mut);padding:0 0 0 14px;margin:0 0 10px">'+p.features.map(function(f){return'<li>'+esc(f)+'</li>';}).join('')+'</ul>'
      +btnHtml
      +'</div>';
  }).join('');
  // Bind upgrade btns
  grid.querySelectorAll('.tarif-upgrade-btn').forEach(function(btn){
    btn.onclick=function(){_passerPremium(_tarifPeriod,btn.dataset.palier,btn);};
  });
  grid.querySelectorAll('.tarif-contact-btn').forEach(function(btn){
    btn.onclick=_ouvrirModalContactEntreprise;
  });
}

async function _ouvrirModalContactEntreprise(){
  var ex=document.getElementById('modal-contact-entreprise');if(ex)ex.remove();
  var t=(typeof _authToken==='function')?_authToken():null;
  var user=(t&&typeof _fetchMe==='function')?(await _fetchMe()||{}):{};
  var ov=document.createElement('div');
  ov.id='modal-contact-entreprise';
  ov.style.cssText='position:fixed;inset:0;z-index:10000;background:rgba(4,8,12,.85);display:flex;align-items:center;justify-content:center;padding:20px';
  ov.onclick=function(e){if(e.target===ov)ov.remove();};
  ov.innerHTML='<div style="background:rgba(10,18,30,.98);border:1px solid rgba(255,255,255,.1);border-radius:18px;width:min(440px,96vw);padding:26px;position:relative">'
    +'<button id="mce-close" style="position:absolute;top:12px;right:14px;background:none;border:none;font-size:18px;cursor:pointer;color:rgba(255,255,255,.4)">&times;</button>'
    +'<div style="font-size:17px;font-weight:800;color:#fff;margin-bottom:4px">Parlons de ton besoin Enterprise</div>'
    +'<div style="font-size:12px;color:rgba(255,255,255,.4);margin-bottom:18px">On te repond directement par email.</div>'
    +'<div class="auth-form">'
    +'<div class="auth-field"><label>Nom</label><input type="text" id="mce-nom" placeholder="Ton nom"></div>'
    +'<div class="auth-field"><label>Email</label><input type="email" id="mce-email" placeholder="ton@email.com"></div>'
    +'<div class="auth-field"><label>Societe</label><input type="text" id="mce-societe" placeholder="Nom de ta societe (optionnel)"></div>'
    +'<div class="auth-field"><label>Ton besoin</label><textarea id="mce-besoin" rows="4" placeholder="Volumetrie, cas d\'usage, delai..."></textarea></div>'
    +'</div>'
    +'<div id="mce-err" class="auth-error" style="display:none;margin-top:6px"></div>'
    +'<button id="mce-submit" style="width:100%;margin-top:14px;padding:12px;font-size:14px;font-weight:700;background:rgba(0,255,65,.08);border:1px solid rgba(0,255,65,.5);color:#00ff41;border-radius:10px;cursor:pointer">Envoyer la demande</button>'
    +'<div id="mce-status" style="font-size:12px;margin-top:8px;text-align:center"></div>';
  document.body.appendChild(ov);
  var qr=function(s){return ov.querySelector(s);};
  if(user.email)qr('#mce-email').value=user.email;
  if(user.name)qr('#mce-nom').value=user.name;
  qr('#mce-close').onclick=function(){ov.remove();};
  qr('#mce-submit').onclick=async function(){
    var nom=(qr('#mce-nom').value||'').trim();
    var email=(qr('#mce-email').value||'').trim();
    var societe=(qr('#mce-societe').value||'').trim();
    var besoin=(qr('#mce-besoin').value||'').trim();
    var err=qr('#mce-err'),st=qr('#mce-status'),btn=qr('#mce-submit');
    err.style.display='none';
    if(!email||email.indexOf('@')<0){err.textContent='Email invalide.';err.style.display='';return;}
    if(!besoin){err.textContent='Decris ton besoin.';err.style.display='';return;}
    btn.disabled=true;btn.textContent='Envoi...';
    try{
      var r=await fetch('/contact/entreprise',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({nom:nom,email:email,societe:societe,besoin:besoin})});
      var d=await r.json().catch(function(){return{};});
      if(r.ok){
        st.innerHTML='<span style="color:var(--ok)">Demande envoyee ! On te repond rapidement.</span>';
        setTimeout(function(){ov.remove();},1800);
      }else{err.textContent=d.detail||'Erreur';err.style.display='';btn.disabled=false;btn.textContent='Envoyer la demande';}
    }catch(e){err.textContent='Erreur reseau.';err.style.display='';btn.disabled=false;btn.textContent='Envoyer la demande';}
  };
}

async function _passerPremium(plan,palier,btn){
  var t=(typeof _authToken==='function')?_authToken():null;
  if(!t){alert('Connecte-toi d\'abord (plus bas) pour choisir un plan.');return;}
  var old=btn.textContent;btn.disabled=true;btn.textContent='Redirection...';
  try{
    var r=await fetch('/premium/checkout',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({plan:plan,palier:palier})});
    var d=await r.json();
    if(r.ok&&d.url)window.location.href=d.url;
    else{alert(d.detail||'Paiement indisponible.');btn.disabled=false;btn.textContent=old;}
  }catch(e){alert('Erreur reseau.');btn.disabled=false;btn.textContent=old;}
}

/* Encart upgrade affiche quand une limite freemium (402) est atteinte.
   Reutilise showSection('compte') -> renderTarifs/_passerPremium existants. */
function _showUpsell(cibleEl,detail){
  if(!cibleEl)return;
  cibleEl.innerHTML='<div style="margin-top:10px;padding:14px 16px;border:1px solid rgba(0,255,65,.4);'
    +'background:rgba(0,255,65,.06);border-radius:12px;font-size:13px;line-height:1.55">'
    +'<b style="color:#00ff41">Limite de ton offre atteinte</b><br>'
    +'<span style="color:var(--mut)">'+esc(detail||'Cette action requiert un pack superieur.')+'</span><br>'
    +'<button class="ntr-upsell-btn" style="margin-top:10px;padding:9px 18px;font-size:13px;font-weight:800;'
    +'background:#00ff41;color:#000;border:none;border-radius:9px;cursor:pointer;letter-spacing:.5px">Voir les packs et passer premium →</button>'
    +'</div>';
  var b=cibleEl.querySelector('.ntr-upsell-btn');
  if(b)b.onclick=function(){
    showSection('compte');
    setTimeout(function(){var t=document.getElementById('tarifs-grid');if(t)t.scrollIntoView({behavior:'smooth',block:'center'});},350);
  };
}

/* Detecte un refus 402 sur une reponse fetch et affiche l'encart upgrade.
   Retourne true si c'etait un 402 (l'appelant doit alors s'arreter). */
async function _maybeUpgrade(resp,cibleEl){
  if(!resp||resp.status!==402)return false;
  var d={};try{d=await resp.clone().json();}catch(e){}
  _showUpsell(cibleEl,d.detail);
  return true;
}

function _initTarifToggle(palierActuel){
  document.querySelectorAll('.tarif-period').forEach(function(btn){
    btn.onclick=function(){
      _tarifPeriod=btn.dataset.period;
      document.querySelectorAll('.tarif-period').forEach(function(b){b.classList.remove('active');});
      btn.classList.add('active');
      renderTarifs(palierActuel);
    };
  });
}

async function _confirmerPremiumRetour(){
  var h=location.hash||'';
  // Confirmation abonnement premium
  var m=h.match(/premium_session=([^&]+)/);
  if(m){
    var t=(typeof _authToken==='function')?_authToken():null;
    if(t){
      try{
        var r=await fetch('/premium/confirmer',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t},body:JSON.stringify({session_id:m[1]})});
        var d=await r.json();
        if(d.premium){
          var msg=d.essai?'Essai '+d.palier+' 7 jours active ! Debit apres l\'essai (annulable).':'Bienvenue sur le plan '+d.palier+' !';
          alert(msg);
        }
      }catch(e){}
    }
    location.hash='#compte';
  }
  // Confirmation achat pack GEN
  var mg=h.match(/credits_ok=([^&]+)/);
  if(mg){
    var gen=parseInt(mg[1])||0;
    var sess_id=(h.match(/credits_session=([^&]+)/)||[])[1]||'';
    var t2=(typeof _authToken==='function')?_authToken():null;
    if(t2&&sess_id){
      try{
        await fetch('/credits/confirmer-recharge',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+t2},body:JSON.stringify({session_id:sess_id})});
      }catch(e){}
    }
    if(gen>0)alert(gen+' GEN credites sur ton compte !');
    location.hash='#compte';
  }
}

async function loadQuotas(){
  await _confirmerPremiumRetour();
  var list=document.getElementById('quotas-list'),badge=document.getElementById('quotas-badge'),cta=document.getElementById('quotas-cta');
  if(!list)return;
  try{
    var d=await(await fetch('/quotas/me',{headers:_authHdrs?_authHdrs():{}})).json();
    var palierActuel=d.palier||'gratuit';
    localStorage.setItem('neogen_premium',d.premium?'1':'0');
    localStorage.setItem('neogen_palier',palierActuel);
    var palierLabels={'gratuit':'Gratuit','essential':'Essential','pro':'Pro','power':'Power','enterprise':'Enterprise'};
    var palierColor={'gratuit':'var(--mut)','essential':'#6366f1','pro':'#8b5cf6','power':'#a855f7','enterprise':'#d946ef'};
    if(badge)badge.innerHTML='<span style="font-size:12px;font-weight:700;color:'+palierColor[palierActuel]+'">'+(palierLabels[palierActuel]||palierActuel)+'</span>';
    if(d.premium){
      list.innerHTML='<div style="font-size:13px;color:var(--ok)">&#10003; Fonctions debloquees selon ton palier '+esc(palierLabels[palierActuel]||palierActuel)+'.</div>';
      if(cta)cta.innerHTML='';
    } else if(!d.connecte){
      list.innerHTML='<div style="font-size:13px;color:var(--mut)">Connecte-toi pour suivre tes quotas.</div>';
      if(cta)cta.innerHTML='';
    } else {
      list.innerHTML=(d.quotas||[]).map(function(q){
        var pct=q.limite?Math.min(100,Math.round(q.utilise/q.limite*100)):0;
        var coul=q.reste===0?'var(--ko)':(q.reste<=1?'var(--warn)':'var(--ok)');
        return '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px">'
          +'<span>'+esc(q.libelle)+'</span><span style="color:'+coul+';font-weight:600">'+q.utilise+' / '+q.limite+'</span></div>'
          +'<div style="height:6px;border-radius:99px;background:rgba(100,116,139,.2);overflow:hidden"><div style="height:100%;width:'+pct+'%;background:'+coul+';transition:width .3s"></div></div></div>';
      }).join('')
        +'<div style="font-size:11px;color:var(--mut);margin-top:8px">Depasse tes limites avec un plan superieur. <b style="color:#f59e0b">Depense des GEN</b> pour des actions ponctuelles.</div>';
      if(cta)cta.innerHTML='';
    }
    // Rendu du tableau des tarifs
    renderTarifs(palierActuel);
    _initTarifToggle(palierActuel);
    // Wallet
    await loadWallet();
    // Telemetrie
    loadTelemetrie();
    _initTelemetrie();
    _initPacksGen();
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
// Evolution reste visible pour tout connecte (vue bridee si non-proprietaire, cf. loadEvolutionSysteme).

// ===== COMPETENCES (skills) auto-creees =====
function _familleSkill(s){
  var outils=((s.outils||[]).join(' ')).toLowerCase();
  var all=(outils+' '+(s.nom||'')+' '+(s.description||'')).toLowerCase();
  if(/controler_ecran|ouvrir_url|fermer_onglet|cliquer|rpa|taper|saisir|piloter/.test(all))return'RPA';
  if(/memoriser|rappeler|memoire_continue|memoire/.test(all))return'Memoire';
  if(/creer_application|discerner|pipeline|generer|forger|creation/.test(all))return'Creation';
  if(/analyser|lire_document|resumer|chercher|savoir|recherche|extraire|fetch|syntaxe/.test(all))return'Analyse';
  if(/deleguer|orchestrer|planifier|coordonner|utiliser_skill|lister_skill/.test(all))return'Orchestration';
  return'General';
}
const _FAMILLE_COULEUR={RPA:'#ef4444',Memoire:'#3b82f6',Creation:'#a855f7',Analyse:'#06b6d4',Orchestration:'#f59e0b',General:'#6b7280'};

async function loadSkills(){
  const el=document.getElementById('skills-list');if(!el)return;
  try{
    const d=await(await fetch('/skills')).json();
    const list=d.skills||[];
    if(!list.length){el.innerHTML='<div style="color:var(--mut);font-size:13px">Aucune competence apprise pour le moment. Demande au Cerveau d\'accomplir une tache reproductible, il la cristallisera.</div>';return;}
    const groupes={};
    list.forEach(function(s){var f=_familleSkill(s);if(!groupes[f])groupes[f]=[];groupes[f].push(s);});
    const ORDRE=['RPA','Memoire','Creation','Analyse','Orchestration','General'];
    var html='';
    ORDRE.forEach(function(famille){
      if(!groupes[famille]||!groupes[famille].length)return;
      var col=_FAMILLE_COULEUR[famille]||'#6b7280';
      html+='<div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px">'
        +'<span style="width:8px;height:8px;border-radius:50%;background:'+col+';flex-shrink:0"></span>'
        +'<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:'+col+'">'+famille+'</span>'
        +'<span style="font-size:11px;color:var(--mut);font-weight:400">('+groupes[famille].length+')</span>'
        +'<span style="flex:1;height:1px;background:'+col+'33"></span>'
        +'</div>';
      html+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;margin-bottom:6px">';
      groupes[famille].forEach(function(s){
        var titre=esc(s.titre||s.nom);
        var desc=esc(s.description||'');
        var nbOutils=(s.outils||[]).length;
        html+='<div style="border:1px solid '+col+'33;border-radius:9px;padding:10px 12px;background:'+col+'08;position:relative;min-width:0">'
          +(s.auto?'<span style="position:absolute;top:8px;left:10px;font-size:8px;font-weight:700;color:'+col+';text-transform:uppercase;letter-spacing:.6px;opacity:.7">auto</span>':'')
          +'<div style="font-size:12px;font-weight:700;color:'+col+';margin-bottom:4px;padding-right:20px;'+(s.auto?'margin-top:12px':'')+';word-break:break-word;line-height:1.3">'+titre+'</div>'
          +(desc?'<div style="font-size:11px;color:var(--mut);line-height:1.4;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-bottom:5px">'+desc+'</div>':'')
          +(nbOutils?'<div style="font-size:10px;color:var(--mut);opacity:.55">'+nbOutils+' outil'+(nbOutils>1?'s':'')+'</div>':'')
          +'<span style="position:absolute;top:7px;right:9px;color:rgba(255,255,255,.25);cursor:pointer;font-size:15px;font-weight:700;line-height:1;transition:color .15s" '
          +'onmouseenter="this.style.color=\'#ef4444\'" onmouseleave="this.style.color=\'rgba(255,255,255,.25)\'" '
          +'title="Supprimer" onclick="deleteSkill(\''+esc(s.nom)+'\')">&#215;</span>'
          +'</div>';
      });
      html+='</div>';
    });
    el.innerHTML=html;
  }catch(e){el.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur de chargement.</div>';}
}
window.deleteSkill=async function(nom){
  try{await fetch('/skills/'+encodeURIComponent(nom),{method:'DELETE'});}catch(e){}
  loadSkills();
};
(function(){
  const btn=document.getElementById('skills-refresh');
  if(btn)btn.onclick=function(){btn.textContent='...';loadSkills().finally(()=>{btn.textContent='✓ Actualise';setTimeout(()=>{btn.textContent='Rafraichir';},1500);});};
  loadSkills();
  const libBtn=document.getElementById('skills-library-btn');
  if(libBtn)libBtn.onclick=openSkillsLibrary;
})();

function _starsHtml(note){
  if(!note)return '';
  var full=Math.floor(note),half=(note-full)>=0.3?1:0,empty=5-full-half;
  return '<span class="skill-stars">'+'★'.repeat(full)+(half?'½':'')+('☆'.repeat(empty))+'</span>'
    +'<span class="skill-note-count">('+note.toFixed(1)+')</span>';
}

var _libAllSkills=[];
var _libCatFilter='all';

async function openSkillsLibrary(){
  const modal=document.getElementById('skills-lib-modal');
  if(!modal)return;
  modal.style.display='flex';
  _renderSkillsLibContent();
}

async function _loadSkillsLibData(){
  const d=await(await fetch('/skills/registry')).json();
  const installed=await(await fetch('/skills')).json();
  const installedNames=new Set((installed.skills||[]).map(function(s){return s.nom;}));
  _libAllSkills=(d.skills||[]).map(function(s,i){return Object.assign({},s,{_idx:i,_installed:installedNames.has(s.nom)||installedNames.has((s.nom||'').replace(/\s+/g,'_').toLowerCase())});});
}

async function _renderSkillsLibContent(){
  const listEl=document.getElementById('skills-lib-list');
  const filterEl=document.getElementById('skills-lib-filters');
  const searchEl=document.getElementById('skills-lib-search');
  if(!listEl)return;
  listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Chargement...</div>';
  try{
    await _loadSkillsLibData();
    if(!_libAllSkills.length){listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Aucun skill communautaire disponible.</div>';return;}
    // Filtres categories
    const cats=['all',...new Set(_libAllSkills.map(function(s){return s.categorie||'General';}))];
    if(filterEl){
      filterEl.innerHTML=cats.map(function(c){
        return '<button class="'+(c===_libCatFilter?'active':'')+'" onclick="setSkillLibCat(\''+esc(c)+'\')">'+esc(c==='all'?'Tous':c)+'</button>';
      }).join('');
    }
    _renderSkillsLibList(searchEl?searchEl.value:'');
  }catch(e){listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur : '+esc(String(e))+'</div>';}
}

window.setSkillLibCat=function(cat){
  _libCatFilter=cat;
  const filterEl=document.getElementById('skills-lib-filters');
  if(filterEl)filterEl.querySelectorAll('button').forEach(function(b){b.classList.toggle('active',b.textContent===(cat==='all'?'Tous':cat));});
  _renderSkillsLibList(document.getElementById('skills-lib-search')?document.getElementById('skills-lib-search').value:'');
};

function _renderSkillsLibList(query){
  const listEl=document.getElementById('skills-lib-list');if(!listEl)return;
  query=(query||'').toLowerCase().trim();
  var list=_libAllSkills.filter(function(s){
    if(_libCatFilter!=='all'&&(s.categorie||'General')!==_libCatFilter)return false;
    if(query&&!(s.titre||s.nom||'').toLowerCase().includes(query)&&!(s.description||'').toLowerCase().includes(query))return false;
    return true;
  });
  if(!list.length){listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Aucun skill dans cette categorie.</div>';return;}
  listEl.innerHTML=list.map(function(s){
    var i=s._idx;
    return '<div class="hist-item" style="align-items:flex-start;margin-bottom:10px;gap:10px">'
      +'<div style="flex:1">'
      +'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
      +(s.categorie?'<span class="skill-cat-badge">'+esc(s.categorie)+'</span>':'')
      +'<b style="font-size:13px">'+esc(s.titre||s.nom)+'</b>'
      +'</div>'
      +'<div style="font-size:12px;color:var(--mut);margin-top:3px">'+esc(s.description||'')+'</div>'
      +'<div class="skill-meta-row">'
      +(s.note?_starsHtml(s.note):'')
      +(s.auteur?'<span>par <b>'+esc(s.auteur)+'</b></span>':'')
      +(s.date_publication?'<span>'+esc(s.date_publication.slice(0,10))+'</span>':'')
      +(s.nb_installations?'<span>'+s.nb_installations+' installations</span>':'')
      +(s.outils&&s.outils.length?'<span style="color:var(--acc)">outils: '+esc(s.outils.join(', '))+'</span>':'')
      +'</div>'
      +'</div>'
      +(s._installed
        ?'<span class="tag ok" style="font-size:11px;flex-shrink:0;align-self:center">installe</span>'
        :'<button class="ghost" style="font-size:12px;padding:4px 12px;flex-shrink:0;align-self:center" onclick="installSkill('+i+')">+ Installer</button>')
      +'</div>';
  }).join('');
}

window.installSkill=async function(idx){
  const s=_libAllSkills[idx];if(!s)return;
  try{
    const r=await(await fetch('/skills/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skills:[s]})})).json();
    if(r.importes&&r.importes.length){
      s._installed=true;
      _renderSkillsLibList(document.getElementById('skills-lib-search')?document.getElementById('skills-lib-search').value:'');
      loadSkills();
    }else if(r.ignores&&r.ignores.length){
      alert('Deja installe.');
    }else{
      alert('Erreur : '+(r.erreurs||[]).join(', '));
    }
  }catch(e){alert('Erreur reseau.');}
};

window.openPublishSkillForm=async function(){
  const form=document.getElementById('skills-publish-form');
  const sel=document.getElementById('spf-skill-select');
  if(!form||!sel)return;
  // Charger les skills locaux
  try{
    const d=await(await fetch('/skills')).json();
    const list=d.skills||[];
    sel.innerHTML='<option value="">-- Choisir un skill local --</option>'
      +list.map(function(s){return '<option value="'+esc(s.nom)+'">'+esc(s.titre||s.nom)+'</option>';}).join('');
  }catch(e){}
  form.style.display='block';
  form.scrollIntoView({behavior:'smooth'});
};

window.submitPublishSkill=async function(){
  const sel=document.getElementById('spf-skill-select');
  const desc=document.getElementById('spf-desc');
  const cat=document.getElementById('spf-cat');
  const tags=document.getElementById('spf-tags');
  const st=document.getElementById('spf-status');
  if(!sel||!sel.value){if(st)st.innerHTML='<span style="color:var(--ko)">Selectionnez un skill.</span>';return;}
  if(st)st.textContent='Envoi en cours...';
  try{
    const r=await fetch('/skills/publier',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({nom:sel.value,description:(desc?desc.value:'').slice(0,200),
        categorie:cat?cat.value:'General',tags:(tags?tags.value:'').split(',').map(function(t){return t.trim();}).filter(Boolean)})});
    const d=await r.json();
    if(d.ok){
      if(st)st.innerHTML='<span style="color:var(--ok)">Skill propose pour curation. Tu recevras +100 GEN si approuve.</span>';
      sel.value='';if(desc)desc.value='';if(tags)tags.value='';
    }else{
      if(st)st.innerHTML='<span style="color:var(--ko)">'+(d.detail||'Erreur')+'</span>';
    }
  }catch(e){if(st)st.innerHTML='<span style="color:var(--ko)">Erreur reseau.</span>';}
};

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
  if(btn)btn.onclick=function(){btn.textContent='...';loadMemoire().finally(()=>{btn.textContent='✓ Actualise';setTimeout(()=>{btn.textContent='Rafraichir';},1500);});};
  loadMemoire();
})();

// ===== BEBE-AGENTS CUSTOM =====
(function(){
  const btn=document.getElementById('bebeagents-refresh');
  if(btn)btn.onclick=function(){btn.textContent='...';loadBebeAgents().finally(()=>{btn.textContent='✓ Actualise';setTimeout(()=>{btn.textContent='Rafraichir';},1500);});};
  loadBebeAgents();
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
      var ech=(t.echecs_consecutifs||0);
      var provLabel=(t.provider||'local')+(t.model?(' / '+t.model):'');
      return '<div class="hist-item" style="align-items:flex-start">'
        +'<span class="tag '+(t.actif?'ok':'')+'" style="flex-shrink:0">'+(t.actif?'actif':'pause')+'</span>'
        +'<span style="flex:1;font-size:13px"><b>'+esc(t.nom)+'</b> <span style="color:var(--mut);font-size:11px">('+esc(t.agent)+' · '+esc(provLabel)+' · '+t.intervalle_minutes+'min)</span>'
        +(ech?' <span class="tag" style="background:rgba(245,158,11,.15);color:#f59e0b">'+ech+' echec(s)</span>':'')
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
    var provider=(document.getElementById('tache-provider')||{}).value||'local';
    if(!nom||!msg){return;}
    try{await fetch('/taches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nom:nom,agent:agent,message:msg,intervalle_minutes:interval,provider:provider})});}catch(e){}
    document.getElementById('tache-nom').value='';document.getElementById('tache-msg').value='';
    form.classList.add('hidden');loadTaches();
  };
  // Peupler le select agents dynamiquement depuis /agents
  var sel=document.getElementById('tache-agent');
  if(sel){
    fetch('/agents').then(function(r){return r.json();}).then(function(d){
      if(!d.agents)return;
      sel.innerHTML=Object.entries(d.agents).map(function(e){
        return '<option value="'+esc(e[0])+'">'+esc(e[1].titre||e[0])+'</option>';
      }).join('');
    }).catch(function(){});
  }
  loadTaches();
})();
/* ===== HUB DU SAVOIR — section Evolution ===== */
async function loadHubEtat(){
  try{
    const r=await fetch('/savoir/etat');
    if(r.status===403)return;   // vue bridee geree par loadEvolutionSysteme, section reste visible
    const d=await r.json();
    const tg=document.getElementById('hub-total-grains');
    const pe=document.getElementById('hub-props-en-attente');
    const nav=document.getElementById('evo-badge-nav');
    if(tg)tg.textContent=d.total_grains||0;
    const att=d.propositions_en_attente||0;
    if(pe)pe.textContent=att;
    if(nav){nav.textContent=att;nav.style.display=att>0?'':'none';}
    const sg=document.getElementById('hub-silos-grid');
    if(sg&&d.grains){
      sg.innerHTML='';
      const colors={skill:'#a855f7',memoire:'#3b82f6',erreur:'#ef4444',amelioration:'#f59e0b',ledger:'#6366f1',telemetrie:'#06b6d4'};
      for(const[k,v] of Object.entries(d.grains)){
        const c=colors[k]||'#888';
        const el=document.createElement('div');
        el.style.cssText='text-align:center;padding:12px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08)';
        el.innerHTML='<div style="font-size:18px;font-weight:700;color:'+c+'">'+v+'</div>'
          +'<div style="font-size:10px;opacity:.5;margin-top:2px">'+k+'</div>';
        sg.appendChild(el);
      }
    }
  }catch(e){console.error('loadHubEtat',e);}
}

async function loadHubPropositions(){
  const container=document.getElementById('hub-props-list');
  const counter=document.getElementById('hub-props-count');
  if(!container)return;
  try{
    const r=await fetch('/savoir/propositions?statut=en_attente');
    const props=await r.json();
    if(counter)counter.textContent=props.length+' en attente';
    if(!props.length){
      container.innerHTML='<div style="text-align:center;padding:30px;opacity:.4;font-size:13px">Aucune proposition en attente. Rafraichir pour analyser.</div>';
      return;
    }
    container.innerHTML='';
    for(const p of props){container.appendChild(_renderProp(p));}
  }catch(e){container.innerHTML='<div style="opacity:.4;font-size:12px;padding:20px">Erreur chargement</div>';}
}

function _renderProp(p){
  const colors={lecon_recurrente:'#ef4444',pattern_critique:'#f59e0b',skill_inutilise:'#6366f1',evolution_skill:'#10b981',evolution_systeme:'#a855f7',pensee_creative:'#06b6d4'};
  const col=colors[p.type]||'#888';
  const wrap=document.createElement('div');
  wrap.style.cssText='padding:14px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08);margin-bottom:10px';
  const typLabel={lecon_recurrente:'Lecon recurrente',pattern_critique:'Pattern critique',skill_inutilise:'Skill inutilise',evolution_skill:'Evolution skill',evolution_systeme:'Evolution systeme',pensee_creative:'Pensee creative'};
  let skillHtml='';
  if(p.skill_propose){
    const sk=p.skill_propose;
    skillHtml='<div style="margin-top:10px;padding:10px;background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.15);border-radius:8px;font-size:12px">'
      +'<div style="font-weight:600;color:#10b981;margin-bottom:4px">Skill propose : '+esc(sk.nom||'')+'</div>'
      +'<div style="opacity:.7">'+esc((sk.description||'').slice(0,120))+'</div>'
      +'</div>';
  }
  wrap.innerHTML='<div class="row" style="align-items:flex-start;gap:10px">'
    +'<span style="font-size:11px;font-weight:700;color:'+col+';background:rgba(255,255,255,.06);border-radius:6px;padding:2px 8px;white-space:nowrap">'+esc(typLabel[p.type]||p.type)+'</span>'
    +'<div style="flex:1"><div style="font-weight:600;font-size:13px;margin-bottom:4px">'+esc(p.titre||'')+'</div>'
    +'<div style="font-size:12px;opacity:.6;line-height:1.5">'+esc(p.justification||'')+'</div>'
    +(p.impact_estime?'<div style="font-size:11px;color:#10b981;margin-top:4px">Impact : '+esc(p.impact_estime)+'</div>':'')
    +skillHtml+'</div></div>'
    +'<div class="row" style="margin-top:12px;gap:8px;justify-content:flex-end">'
    +'<button class="ghost" style="font-size:12px;padding:5px 14px;color:#ef4444;border-color:rgba(239,68,68,.3)" data-refuse="'+p.id+'">Refuser</button>'
    +'<button style="font-size:12px;padding:5px 14px;background:#10b981" data-approve="'+p.id+'">Approuver</button>'
    +'</div>';
  wrap.querySelector('[data-approve]').onclick=async function(){
    this.disabled=true;this.textContent='...';
    try{
      const r=await fetch('/savoir/propositions/'+encodeURIComponent(p.id)+'/approuver',{method:'POST'});
      const d=await r.json();
      wrap.style.opacity='.4';
      wrap.querySelector('[data-refuse]').style.display='none';
      this.textContent=d.ok?'Approuve !':'Erreur';
      if(d.ok&&d.job_id){
        _bulleProgression(d.job_id,p.titre||'',this);
      }else if(d.ok){
        _bulleVieDonnee(p.titre||'');
      }
    }catch(e){this.textContent='Erreur';}
    setTimeout(function(){loadHubPropositions();loadHubEtat();loadEvolutionSysteme();loadPensees();},1400);
  };
  wrap.querySelector('[data-refuse]').onclick=async function(){
    this.disabled=true;this.textContent='...';
    try{
      await fetch('/savoir/propositions/'+encodeURIComponent(p.id)+'/refuser',{method:'POST'});
      wrap.style.opacity='.4';
      wrap.querySelector('[data-approve]').style.display='none';
      this.textContent='Refuse';
    }catch(e){this.textContent='Erreur';}
    setTimeout(function(){loadHubPropositions();loadHubEtat();},1200);
  };
  return wrap;
}

(function(){
  const btnR=document.getElementById('btn-hub-refresh');
  const status=document.getElementById('hub-refresh-status');
  if(btnR)btnR.onclick=async function(){
    btnR.disabled=true;btnR.textContent='Analyse...';
    if(status){status.style.display='';status.textContent='Rafraichissement en cours...';}
    try{
      const r=await fetch('/savoir/rafraichir',{method:'POST'});
      const d=await r.json();
      const nb=Object.values(d.grains_par_silo||{}).reduce(function(a,b){return a+b;},0);
      if(status)status.textContent=nb+' grains analyses, '+d.nouvelles_propositions+' nouvelles propositions.';
      loadHubEtat();loadHubPropositions();
    }catch(e){if(status)status.textContent='Erreur : '+e.message;}
    finally{btnR.disabled=false;btnR.textContent='&#8635; Rafraichir';}
  };

  const btnS=document.getElementById('btn-hub-search');
  const inp=document.getElementById('hub-search-input');
  if(btnS)btnS.onclick=async function(){
    const q=(inp&&inp.value||'').trim();
    if(!q)return;
    const dom=(document.getElementById('hub-search-domaine')||{}).value||'';
    const url='/savoir/chercher?q='+encodeURIComponent(q)+(dom?'&domaine='+dom:'');
    const res=document.getElementById('hub-search-results');
    if(res)res.innerHTML='<div style="opacity:.4;font-size:12px">Recherche...</div>';
    try{
      const r=await fetch(url);
      const data=await r.json();
      if(!res)return;
      if(!data.length){res.innerHTML='<div style="opacity:.4;font-size:12px;padding:10px">Aucun resultat.</div>';return;}
      res.innerHTML='';
      for(const item of data){
        const g=item.grain||{};
        const el=document.createElement('div');
        el.style.cssText='padding:10px 12px;background:rgba(255,255,255,.04);border-radius:8px;margin-bottom:6px;font-size:12px;border:1px solid rgba(255,255,255,.07)';
        el.innerHTML='<div class="row" style="gap:8px;align-items:center;margin-bottom:4px">'
          +'<span style="font-weight:600;color:#10b981">'+esc(g.domaine||'')+'</span>'
          +'<span style="opacity:.4">'+esc(g.type||'')+'</span>'
          +'<span style="margin-left:auto;opacity:.5">cos '+item.score_cosinus+'</span></div>'
          +'<div style="opacity:.75;line-height:1.5">'+esc((g.contenu||'').slice(0,180))+'</div>';
        res.appendChild(el);
      }
    }catch(e){if(res)res.innerHTML='<div style="opacity:.4;font-size:12px">Erreur : '+esc(e.message)+'</div>';}
  };
  if(inp)inp.addEventListener('keydown',function(e){if(e.key==='Enter'&&btnS)btnS.click();});
})();

/* ===== LA PENSEE — intelligence collective autonome ===== */
let _penseeWired=false;
async function loadPenseesConfig(){
  try{
    const r=await fetch('/savoir/pensees/config');
    if(!r.ok)return;
    const c=await r.json();
    const m=document.getElementById('pensee-mode');
    const iv=document.getElementById('pensee-intervalle');
    const ac=document.getElementById('pensee-actif');
    if(m)m.value=c.mode||'eco';
    if(iv)iv.value=String(c.intervalle_min||120);
    if(ac)ac.checked=c.actif!==false;
  }catch(e){}
  if(_penseeWired)return; _penseeWired=true;
  async function saveCfg(){
    const m=document.getElementById('pensee-mode'),iv=document.getElementById('pensee-intervalle'),ac=document.getElementById('pensee-actif');
    const st=document.getElementById('pensee-config-status');
    const body={mode:m?m.value:'eco',intervalle_min:iv?parseInt(iv.value,10):120,actif:ac?ac.checked:true};
    try{
      const r=await fetch('/savoir/pensees/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const c=await r.json();
      if(st){st.style.display='';st.textContent='Configuration enregistree'+(c.mode!==body.mode?' (repli '+c.mode+')':'')+'.';setTimeout(function(){st.style.display='none';},2500);}
    }catch(e){if(st){st.style.display='';st.textContent='Erreur : '+esc(e.message);}}
  }
  ['pensee-mode','pensee-intervalle','pensee-actif'].forEach(function(id){var el=document.getElementById(id);if(el)el.addEventListener('change',saveCfg);});
  var _peclair=document.getElementById('pensee-eclrcb');
  if(_peclair){
    _peclair.checked=localStorage.getItem('neogen_eclair')!=='0';
    _peclair.onchange=function(){localStorage.setItem('neogen_eclair',this.checked?'1':'0');
      document.querySelectorAll('[id^="eclrcb-"]').forEach(function(c){c.checked=_peclair.checked;});};
  }
  async function lancerCycle(sujet,btn,label){
    btn.disabled=true;btn.textContent='Pensee en cours...';
    try{
      const body=sujet?JSON.stringify({sujet:sujet}):'{}';
      const r=await fetch('/savoir/pensees/cycle',{method:'POST',headers:{'Content-Type':'application/json'},body:body});
      const d=await r.json();
      if(d&&d.execute){loadPensees();if(d.proposition)loadHubPropositions();const si=document.getElementById('pensee-sujet');if(si&&sujet)si.value='';}
      else{const st=document.getElementById('pensee-config-status');if(st){st.style.display='';st.textContent='Aucune pensee : '+esc((d&&d.raison)||'indisponible')+'.';}}
    }catch(e){}
    finally{btn.disabled=false;btn.textContent=label;}
  }
  const bc=document.getElementById('btn-pensee-cycle');
  if(bc)bc.onclick=function(){lancerCycle(null,bc,'Provoquer une pensee');};
  const bd=document.getElementById('btn-pensee-discuter');
  if(bd)bd.onclick=function(){
    const s=((document.getElementById('pensee-sujet')||{}).value||'').trim();
    if(!s){const si=document.getElementById('pensee-sujet');if(si)si.focus();return;}
    lancerCycle(s,bd,'Discuter');
  };
}

window._penseesData=[];
window._triPenseesCourant='type';

async function loadPensees(){
  const container=document.getElementById('pensee-list');
  const counter=document.getElementById('pensee-count');
  if(!container)return;
  try{
    const r=await fetch('/savoir/pensees?limit=50');
    if(!r.ok)return;
    const d=await r.json();
    window._penseesData=(d&&d.pensees)||[];
    _renderPenseesList();
    const visibles=window._penseesData.filter(function(p){return p.forge_etat!=='archivee';});
    if(counter)counter.textContent=visibles.length+' pensee'+(visibles.length>1?'s':'')+' ('+window._penseesData.length+' total)';
  }catch(e){container.innerHTML='<div style="opacity:.4;font-size:12px;padding:20px">Erreur chargement</div>';}
}

function trierPensees(mode){
  window._triPenseesCourant=mode;
  document.querySelectorAll('.filtre-btn-tri').forEach(function(b){
    const actif=b.dataset.tri===mode;
    b.style.background=actif?'rgba(168,85,247,.15)':'rgba(255,255,255,.03)';
    b.style.borderColor=actif?'rgba(168,85,247,.4)':'rgba(255,255,255,.08)';
    b.style.color=actif?'#a855f7':'#9ca3af';
  });
  _renderPenseesList();
}

function _renderPenseesList(){
  const container=document.getElementById('pensee-list');
  if(!container||!window._penseesData)return;
  const list=window._penseesData;
  if(!list.length){container.innerHTML='<div style="text-align:center;padding:24px;opacity:.4;font-size:13px">Aucune pensee pour l\'instant. Provoquez-en une.</div>';return;}
  container.innerHTML='';
  const mode=window._triPenseesCourant||'type';

  if(mode==='recent'||mode==='ancien'){
    // Tri chronologique — separateurs de periode au lieu des groupes par type
    const sorted=[...list].sort(function(a,b){
      const ta=a.ts||0,tb=b.ts||0;
      return mode==='recent'?tb-ta:ta-tb;
    });
    const now=Date.now()/1000;
    const _periode=function(ts){
      if(!ts)return'inconnue';
      const j=(now-ts)/86400;
      if(j<1)return'Aujourd\'hui';
      if(j<7)return'Cette semaine';
      if(j<30)return'Ce mois';
      if(j<90)return'Il y a 1 a 3 mois';
      return'Plus ancien';
    };
    var dernierePeriode=null;
    for(const p of sorted){
      const per=_periode(p.ts);
      if(per!==dernierePeriode){
        const hdr=document.createElement('div');
        hdr.className='pensee-groupe-header';
        hdr.dataset.groupe='periode-'+per.toLowerCase().replace(/\s/g,'-');
        hdr.style.cssText='font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#6b7280;padding:14px 0 6px;margin-top:4px;border-top:1px solid rgba(255,255,255,.06)';
        hdr.textContent=per;
        container.appendChild(hdr);
        dernierePeriode=per;
      }
      container.appendChild(_renderPensee(p));
    }
  }else{
    // Tri par type (comportement original)
    const ORDRE_TYPE=['sujet','idee','suggestion','reflexion','reve','obsession','desir'];
    const sorted=[...list].sort(function(a,b){
      var ia=ORDRE_TYPE.indexOf(a.type||(a.sujet?'sujet':'idee'));
      var ib=ORDRE_TYPE.indexOf(b.type||(b.sujet?'sujet':'idee'));
      if(ia<0)ia=99;if(ib<0)ib=99;return ia-ib;
    });
    const LABELS_TYPE={sujet:'Sujets de discussion',idee:'Idees',suggestion:'Suggestions',reflexion:'Reflexions',reve:'Reves',obsession:'Obsessions',desir:'Desirs'};
    var dernierType=null;
    for(const p of sorted){
      const ptype=p.type||(p.sujet?'sujet':'idee');
      if(ptype!==dernierType){
        const cnt=sorted.filter(function(x){return (x.type||(x.sujet?'sujet':'idee'))===ptype;}).length;
        const hdr=document.createElement('div');
        hdr.className='pensee-groupe-header';
        hdr.dataset.groupe=ptype;
        hdr.style.cssText='font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#6b7280;padding:14px 0 6px;margin-top:4px;border-top:1px solid rgba(255,255,255,.06)';
        hdr.textContent=(LABELS_TYPE[ptype]||ptype)+' ('+cnt+')';
        container.appendChild(hdr);
        dernierType=ptype;
      }
      container.appendChild(_renderPensee(p));
    }
  }
  if(_filtrePenseesCourant&&_filtrePenseesCourant!=='tous')filtrerPensees(_filtrePenseesCourant);
  else requestAnimationFrame(function(){_applyMasonry('pensee-list',350,8);_attachDetailsToggle('pensee-list',350,8);});

}

function _renderPensee(p){
  const tcol={idee:'#10b981',suggestion:'#3b82f6',obsession:'#ef4444',sujet:'#a855f7',reflexion:'#06b6d4',reve:'#f59e0b',desir:'#ec4899'};
  const col=tcol[p.type]||'#888';
  const wrap=document.createElement('div');
  const etatAttr=p.forge_etat||(p.vie_donnee?'actif':'');
  wrap.style.cssText='padding:14px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08);margin-bottom:10px';
  wrap.dataset.etat=etatAttr;
  wrap.dataset.bulle=p.bulle?'1':'0';
  wrap.dataset.ptype=p.type||'autre';
  const sc=(typeof p.score==='number')?p.score.toFixed(2):'--';
  let badges='<span style="font-size:11px;font-weight:700;color:'+col+';background:rgba(255,255,255,.06);border-radius:6px;padding:2px 8px">'+esc(p.type||'')+'</span>'
    +'<span style="font-size:11px;opacity:.5">'+esc(p.ambiance_label||p.ambiance||'')+'</span>'
    +'<span style="margin-left:auto;font-size:11px;opacity:.6">score '+sc+'</span>';
  if(p.bulle)badges+='<span style="font-size:11px;color:#f59e0b">&#9679; bulle</span>';
  if(etatAttr==='generee')badges+='<span style="font-size:11px;color:#10b981;font-weight:700;background:rgba(16,185,129,.12);border-radius:6px;padding:2px 8px">&#9889; Code genere &amp; teste</span>';
  else if(etatAttr==='actif')badges+='<span style="font-size:11px;color:#10b981;font-weight:700;background:rgba(16,185,129,.1);border-radius:6px;padding:2px 8px">&#10003; Actif</span>';
  else if(etatAttr==='refusee')badges+='<span style="font-size:11px;color:#ef4444;font-weight:700;background:rgba(239,68,68,.1);border-radius:6px;padding:2px 8px">&#10007; Refuse</span>';
  else if(etatAttr==='notee')badges+='<span style="font-size:11px;color:#9ca3af;font-weight:600;background:rgba(255,255,255,.05);border-radius:6px;padding:2px 8px">note</span>';
  else if(etatAttr==='archivee')badges+='<span style="font-size:11px;color:#6b7280;background:rgba(255,255,255,.04);border-radius:6px;padding:2px 8px">archive</span>';
  else if(p.proposition)badges+='<span style="font-size:11px;color:#10b981">&#8594; proposition</span>';
  if(p.sujet)badges='<span style="font-size:11px;color:#a855f7">&#128172; sujet</span>'+badges;
  let tr='';
  if(Array.isArray(p.transcript)&&p.transcript.length){
    // Badge de fraicheur base sur p.ts (quand la conversation a eu lieu)
    const _tsConv=p.ts?p.ts*1000:null;
    let _freshLabel='';let _freshCol='';
    if(_tsConv){
      const _ageS=(Date.now()-_tsConv)/1000;
      const _ageMin=_ageS/60;const _ageH=_ageMin/60;const _ageJ=_ageH/24;
      if(_ageMin<60){_freshLabel='il y a '+Math.max(1,Math.round(_ageMin))+'min';_freshCol='#10b981';}
      else if(_ageH<24){_freshLabel='il y a '+Math.round(_ageH)+'h';_freshCol='#22d3ee';}
      else if(_ageJ<7){_freshLabel='il y a '+Math.round(_ageJ)+'j';_freshCol='#f59e0b';}
      else if(_ageJ<30){_freshLabel='il y a '+Math.round(_ageJ/7)+'sem';_freshCol='#f97316';}
      else{_freshLabel='il y a '+Math.round(_ageJ/30)+'mois';_freshCol='#6b7280';}
    }
    const _dateStr=_tsConv?new Date(_tsConv).toLocaleDateString('fr-FR',{day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit'}):'';
    const _freshBadge=_freshLabel
      ?'<span title="'+_dateStr+'" style="margin-left:8px;font-size:10px;color:'+_freshCol+';background:'+_freshCol+'22;border:1px solid '+_freshCol+'44;border-radius:4px;padding:1px 6px;font-weight:600">'+_freshLabel+'</span>'
      :'';
    tr='<details style="margin-top:8px"><summary style="font-size:12px;opacity:.6;cursor:pointer;list-style:none;display:flex;align-items:center;gap:0">&#9654; Conversation ('+p.transcript.length+')'+_freshBadge+'</summary>'
      +'<div style="margin-top:8px;display:flex;flex-direction:column;gap:6px;max-height:260px;overflow-y:auto;padding-right:4px">';
    for(const t of p.transcript){tr+='<div style="font-size:12px;line-height:1.5"><span style="font-weight:600;color:'+col+'">'+esc(t.agent||'')+'</span> : <span style="opacity:.85">'+esc(t.texte||'')+'</span></div>';}
    tr+='</div></details>';
  }
  const parts=Array.isArray(p.participants)?p.participants.join(', '):'';
  const btnVieId='btn-vie-'+esc(p.id||Math.random().toString(36).slice(2));
  const btnArchiveHtml=(etatAttr!=='archivee')
    ?'<button onclick="archiverPensee(\''+esc(p.id||'')+'\',this)" style="font-size:11px;padding:4px 10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#6b7280;border-radius:6px;cursor:pointer;margin-right:6px">Archiver</button>'
    :'';
  wrap.innerHTML='<div class="row" style="gap:8px;align-items:center;margin-bottom:6px">'+badges+'</div>'
    +'<div style="font-weight:600;font-size:13px;margin-bottom:4px">'+esc(p.titre||'')+'</div>'
    +'<div style="font-size:12px;opacity:.7;line-height:1.5">'+esc(p.synthese||'')+'</div>'
    +(parts?'<div style="font-size:11px;opacity:.4;margin-top:6px">'+esc(parts)+'</div>':'')
    +tr
    +'<div style="margin-top:10px;text-align:right">'
    +btnArchiveHtml
    +'<button id="'+btnVieId+'" onclick="donnerVie(\''+esc(p.id||'')+'\',this)" '
    +'style="font-size:11px;padding:4px 12px;background:rgba(168,85,247,.1);border:1px solid rgba(168,85,247,.3);color:#a855f7;border-radius:6px;cursor:pointer">&#9889; Donner vie a cette idee</button>'
    +'</div>';
  return wrap;
}

/* ── Filtres pensees ──────────────────────────────────────────── */
var _filtrePenseesCourant='tous';

function filtrerPensees(filtre){
  _filtrePenseesCourant=filtre;
  document.querySelectorAll('#pensee-filtres .filtre-btn').forEach(function(b){
    var actif=(b.dataset.filtre===filtre);
    b.style.background=actif?'rgba(168,85,247,.2)':'rgba(255,255,255,.04)';
    b.style.borderColor=actif?'rgba(168,85,247,.5)':'rgba(255,255,255,.1)';
    b.style.color=actif?'#a855f7':'#9ca3af';
  });
  var container=document.getElementById('pensee-list');
  if(!container)return;
  container.scrollTop=0;
  // Masquer/afficher aussi les separateurs de groupe
  container.querySelectorAll('.pensee-groupe-header').forEach(function(h){h.style.display='none';});
  var cartes=container.querySelectorAll('[data-etat]');
  var nb=0;
  cartes.forEach(function(c){
    var vis=false;
    var et=c.dataset.etat||'';
    if(filtre==='tous')vis=(et!=='archivee');
    else if(filtre==='neuves')vis=(!et||et===''||et==='undefined')&&et!=='archivee';
    else if(filtre==='pris-en-vie')vis=(et==='actif'||et==='notee');
    else if(filtre==='bulle')vis=(c.dataset.bulle==='1'&&et!=='archivee');
    else vis=(et===filtre);
    c.style.display=vis?'':'none';
    if(vis)nb++;
  });
  // Ré-afficher les headers dont le groupe a au moins une carte visible
  container.querySelectorAll('.pensee-groupe-header').forEach(function(h){
    var grp=h.dataset.groupe;
    var visible=false;
    var sib=h.nextElementSibling;
    while(sib&&!sib.classList.contains('pensee-groupe-header')){
      if(sib.dataset.ptype===grp&&sib.style.display!=='none'){visible=true;break;}
      sib=sib.nextElementSibling;
    }
    if(visible)h.style.display='';
  });
  var counter=document.getElementById('pensee-count');
  if(counter)counter.textContent=nb+' pensee'+(nb>1?'s':'')+' ('+(filtre==='tous'?'toutes':filtre)+')';
  requestAnimationFrame(function(){_applyMasonry('pensee-list',350,8);_attachDetailsToggle('pensee-list',350,8);});
}

function filtrerProduits(filtre){
  window._filtreProduitsCourant=filtre;
  document.querySelectorAll('#produit-filtres .filtre-btn-prod').forEach(function(b){
    var actif=(b.dataset.filtre===filtre);
    b.style.background=actif?'rgba(168,85,247,.2)':'rgba(255,255,255,.04)';
    b.style.borderColor=actif?'rgba(168,85,247,.5)':'rgba(255,255,255,.1)';
    b.style.color=actif?'#a855f7':'#9ca3af';
  });
  loadProduits();
}

var _filtrePenseesType='tous';
function filtrerPenseesType(type){
  _filtrePenseesType=type;
  document.querySelectorAll('#pensee-filtres-type .filtre-btn-type').forEach(function(b){
    var actif=(b.dataset.type===type);
    b.style.background=actif?'rgba(168,85,247,.15)':'rgba(255,255,255,.03)';
    b.style.borderColor=actif?'rgba(168,85,247,.4)':'rgba(255,255,255,.08)';
    b.style.color=actif?'#a855f7':'#9ca3af';
  });
  var container=document.getElementById('pensee-list');
  if(!container)return;
  container.scrollTop=0;
  // Masquer/afficher cartes selon le type
  container.querySelectorAll('.pensee-groupe-header').forEach(function(h){
    h.style.display=(type==='tous'||h.dataset.groupe===type)?'':'none';
  });
  container.querySelectorAll('[data-ptype]').forEach(function(c){
    if(type==='tous'){
      var et=c.dataset.etat||'';
      var f=_filtrePenseesCourant;
      var vis=f==='tous'?(et!=='archivee'):f==='pris-en-vie'?(et==='actif'||et==='generee'):f==='bulle'?(c.dataset.bulle==='1'&&et!=='archivee'):(et===f);
      c.style.display=vis?'':'none';
    }else{
      c.style.display=(c.dataset.ptype===type)?'':'none';
    }
  });
  requestAnimationFrame(function(){_applyMasonry('pensee-list',350,8);_attachDetailsToggle('pensee-list',350,8);});
}

var _filtreChangelogCourant='tous';
function filtrerChangelog(type){
  _filtreChangelogCourant=type;
  document.querySelectorAll('#changelog-filtres .filtre-btn-cl').forEach(function(b){
    var actif=(b.dataset.cl===type);
    b.style.background=actif?'rgba(16,185,129,.15)':'rgba(255,255,255,.03)';
    b.style.borderColor=actif?'rgba(16,185,129,.4)':'rgba(255,255,255,.08)';
    b.style.color=actif?'#10b981':'#9ca3af';
  });
  var c=document.getElementById('evo-changelog');
  if(!c)return;
  c.querySelectorAll('[data-ctype]').forEach(function(el){
    el.style.display=(type==='tous'||el.dataset.ctype===type)?'':'none';
  });
  requestAnimationFrame(function(){_applyMasonry('evo-changelog',215,8);});
}

function archiverPensee(id,btn){
  if(!id)return;
  if(btn)btn.disabled=true;
  fetch('/savoir/pensees/'+id+'/archiver',{method:'POST',headers:_authHdrs()})
    .then(function(r){return r.json();})
    .then(function(d){
      if(d.ok){
        var carte=btn?btn.closest('[data-etat]'):null;
        if(carte){carte.dataset.etat='archivee';carte.style.display='none';}
      }else if(btn){btn.disabled=false;}
    })
    .catch(function(){if(btn)btn.disabled=false;});
}

function _bulleVieDonnee(titre){
  const el=document.createElement('div');
  el.style.cssText='position:fixed;right:20px;bottom:80px;max-width:320px;z-index:9999;padding:16px 18px;background:rgba(16,22,30,.97);border:1px solid rgba(168,85,247,.5);border-radius:14px;box-shadow:0 12px 36px rgba(0,0,0,.6);backdrop-filter:blur(10px)';
  el.innerHTML='<div style="font-size:11px;color:#a855f7;font-weight:700;margin-bottom:6px">&#9889; Votre idee prend vie</div>'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:4px">'+esc(titre)+'</div>'
    +'<div style="font-size:11px;opacity:.55;line-height:1.4">La regle est appliquee. La page se recharge dans 2s.</div>';
  document.body.appendChild(el);
  setTimeout(function(){if(el.parentNode)el.remove();},5000);
  setTimeout(function(){location.reload();},2200);
}

async function donnerVie(id,btn){
  if(!id)return;
  btn.disabled=true;btn.textContent='En cours...';
  try{
    const r=await fetch('/savoir/pensees/'+encodeURIComponent(id)+'/donner-vie',{method:'POST'});
    const d=await r.json();
    if(d.voie==='forge_blocs'&&d.ok&&d.html){
      // Idee d'affichage : apercu HTML -> active la Forge de blocs avec le preview charge.
      btn.textContent='Apercu Forge';
      _activerForgeBlocs(d);
    }else if(d.voie==='forge_blocs'&&!d.ok){
      btn.textContent='Forge : '+(d.raison||'echec');
      btn.style.color='#ef4444';btn.disabled=false;
    }else if(d.voie==='interface'&&d.css){
      btn.textContent='Apercu pret';
      _bulleApercuInterface(d,btn);
    }else if(d.voie==='interface'&&!d.ok){
      btn.textContent='Interface : '+(d.raison||'echec');
      btn.style.color='#ef4444';btn.disabled=false;
    }else if(d.voie==='forge'&&d.job_id){
      // Idee technique : la forge genere du VRAI code (asynchrone). Bulle de progression vivante.
      btn.textContent='Forge en cours...';
      _bulleProgression(d.job_id,(btn.closest('div')&&'idee')||'idee',btn);
    }else if(d.voie==='data+forge'&&d.job_id){
      // Regle comportementale : stockee dans JSON + AUSSI forgee en code.
      btn.textContent='Stockee + Forge...';btn.style.color='#10b981';
      _bulleProgression(d.job_id,'regle',btn);
      if(typeof loadEvolutionSysteme==='function')setTimeout(loadEvolutionSysteme,800);
    }else if(d.ok||d.prop_id){
      btn.textContent=d.voie==='note'?'Notee':'Proposee dans Evolution';
      btn.style.color='#10b981';btn.style.borderColor='rgba(16,185,129,.3)';
      btn.style.background='rgba(16,185,129,.08)';
      if(typeof loadEvolutionSysteme==='function')setTimeout(loadEvolutionSysteme,800);
      // Rafraichir la liste des propositions sans rechargement page.
      // Placeholder immediat pour indiquer que quelque chose arrive.
      if(d.prop_id){
        const _c=document.getElementById('hub-props-list');
        if(_c){
          const _ph=document.createElement('div');
          _ph.style.cssText='padding:12px 14px;background:rgba(168,85,247,.05);border:1px dashed rgba(168,85,247,.3);border-radius:10px;margin-bottom:10px;font-size:12px;color:#a855f7;opacity:.8;display:flex;align-items:center;gap:8px';
          _ph.innerHTML='<span>&#8987;</span> Proposition enregistree, chargement…';
          _c.prepend(_ph);
        }
        setTimeout(function(){if(typeof loadHubPropositions==='function')loadHubPropositions();},700);
      }
    }else{
      btn.textContent='Refuse : '+(d.raison||'?');
      btn.style.color='#ef4444';btn.disabled=false;
    }
  }catch(e){btn.textContent='Erreur';btn.disabled=false;}
}

/* Bulle de PROGRESSION vivante — style Matrix NEOGEN.
   Poll /savoir/evolution/forge/{jobId} toutes les 1.5s jusqu'au verdict. */
function _bulleProgression(jobId,titre,btn){
  const el=document.createElement('div');
  el.id='forge-bubble-'+jobId;
  el.style.cssText=[
    'position:fixed;right:22px;bottom:22px;max-width:360px;min-width:280px;z-index:10000',
    'padding:16px 18px 14px',
    'background:rgba(0,7,2,.97)',
    'border:1px solid rgba(0,255,65,.28)',
    'border-radius:8px',
    'box-shadow:0 0 28px rgba(0,255,65,.10),0 18px 44px rgba(0,0,0,.88)',
    'backdrop-filter:blur(14px)',
    'color:#e2e8f0',
    'font-family:ui-monospace,"SF Mono",Consolas,monospace'
  ].join(';');

  el.innerHTML=
    /* header */
    '<div style="display:flex;align-items:center;gap:7px;margin-bottom:10px">'
      +'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#00e869;box-shadow:0 0 6px #00e869;animation:_mpulse 1.2s ease-in-out infinite"></span>'
      +'<span style="font-size:10px;letter-spacing:.14em;color:rgba(0,255,65,.65);text-transform:uppercase;font-weight:600">Ingenieur actif</span>'
    +'</div>'
    /* etape courante */
    +'<div id="fp-etape-'+jobId+'" style="font-size:12px;color:#00e869;min-height:16px;margin-bottom:10px;word-break:break-all">Initialisation…</div>'
    /* barre */
    +'<div style="height:3px;background:rgba(0,255,65,.10);border-radius:3px;overflow:hidden;margin-bottom:10px">'
      +'<div id="fp-bar-'+jobId+'" style="height:100%;width:5%;background:linear-gradient(90deg,#00c454,#00e869);transition:width .6s ease;box-shadow:0 0 6px rgba(0,255,65,.5)"></div>'
    +'</div>'
    /* note */
    +'<div id="fp-note-'+jobId+'" style="font-size:10px;color:rgba(0,255,65,.38);line-height:1.6">forge &rarr; test sandbox &rarr; controle murs</div>';

  /* animation pulse (injectee une seule fois) */
  if(!document.getElementById('_mpulse-style')){
    const s=document.createElement('style');s.id='_mpulse-style';
    s.textContent='@keyframes _mpulse{0%,100%{opacity:1}50%{opacity:.3}}';
    document.head.appendChild(s);
  }
  document.body.appendChild(el);

  const timer=setInterval(async function(){
    let st;
    try{ st=await (await fetch('/savoir/evolution/forge/'+encodeURIComponent(jobId))).json(); }
    catch(e){ return; }
    const et=document.getElementById('fp-etape-'+jobId);
    const bar=document.getElementById('fp-bar-'+jobId);
    const note=document.getElementById('fp-note-'+jobId);
    if(et&&st.etape_label)et.textContent=st.etape_label;
    if(bar&&typeof st.pct==='number')bar.style.width=Math.max(5,st.pct)+'%';

    if(st.etat==='generee'||st.etat==='termine'||st.etat==='integree'||st.etat==='forgee'){
      clearInterval(timer);
      var _ok=!!(st.nom);
      var _sac=(st.etat==='forgee');  /* cellule dans le sac user, pas integree au systeme */
      if(bar){bar.style.width='100%';}
      el.querySelector('span[style*="animation"]').style.animation='none';
      el.querySelector('span[style*="animation"]').style.background='#00e869';
      el.querySelector('span[style*="animation"]').style.boxShadow='0 0 10px #00e869';
      el.style.borderColor='rgba(0,255,65,.6)';
      el.style.boxShadow='0 0 32px rgba(0,255,65,.18),0 18px 44px rgba(0,0,0,.88)';
      if(et)et.textContent=_ok?(_sac?'> skill forge dans ton espace':'> cellule integree & fonctionnelle'):'> traitement termine';
      et.style.color='#00e869';et.style.fontWeight='700';
      var _rap=esc((st.rapport||'').slice(0,340));
      if(note)note.innerHTML=(_ok
        ?'<span style="color:rgba(0,255,65,.65)">'+(_sac?'skill forge':'cellule')+' </span><b style="color:#00e869">'+esc(st.nom)+'</b><span style="color:rgba(0,255,65,.65)">'+(_sac?' (ton espace)':' integree au systeme')+'</span><br>':''
      )+'<div style="margin-top:5px;max-height:110px;overflow:auto;white-space:pre-wrap;color:rgba(0,255,65,.4);font-size:10px">'+_rap+'</div>';
      if(btn){btn.textContent=_ok?(_sac?'> forge':'> integre'):'> traite';btn.style.color='#00e869';btn.style.borderColor='rgba(0,255,65,.3)';btn.style.background='rgba(0,255,65,.06)';btn.disabled=false;}
      if(typeof loadEvolutionSysteme==='function')setTimeout(loadEvolutionSysteme,400);
      if(typeof loadMesSkills==='function')setTimeout(loadMesSkills,500);
      if(!_ok&&typeof loadIngenieur==='function')setTimeout(loadIngenieur,500);
      setTimeout(function(){if(el.parentNode)el.remove();},_ok?3000:14000);
      if(_ok&&!_sac)setTimeout(function(){location.reload();},3100);

    }else if(st.etat==='refusee'){
      clearInterval(timer);
      if(bar){bar.style.width='100%';bar.style.background='#ef4444';bar.style.boxShadow='none';}
      el.querySelector('span[style*="animation"]').style.animation='none';
      el.querySelector('span[style*="animation"]').style.background='#ef4444';
      el.querySelector('span[style*="animation"]').style.boxShadow='0 0 6px #ef4444';
      el.style.borderColor='rgba(239,68,68,.55)';
      el.style.boxShadow='0 0 24px rgba(239,68,68,.10),0 18px 44px rgba(0,0,0,.88)';
      if(et){et.textContent='> echec — idee non integree';et.style.color='#ef4444';et.style.fontWeight='700';}
      if(note)note.innerHTML='<span style="color:rgba(239,68,68,.65)">raison : '
        +esc(st.raison||'erreur inconnue')+' — aucun code installe.</span>';
      if(btn){btn.textContent='echec';btn.style.color='#ef4444';btn.disabled=false;}
      setTimeout(function(){if(el.parentNode)el.remove();},10000);
    }
  },1500);
}

/* Apercu d'une evolution d'INTERFACE : montre le CSS reel + ce que ca change,
   puis APPLIQUE sur confirmation (decision Jordan : donner vie -> apercu -> confirmer). */
function _bulleApercuInterface(d,btn){
  const id='ui-apercu-'+Math.random().toString(36).slice(2);
  const el=document.createElement('div');
  el.id=id;
  el.style.cssText='position:fixed;right:20px;bottom:20px;max-width:420px;z-index:10001;padding:18px;background:rgba(16,22,30,.99);border:1px solid rgba(168,85,247,.55);border-radius:14px;box-shadow:0 16px 44px rgba(0,0,0,.7);backdrop-filter:blur(10px);color:#e2e8f0';
  el.innerHTML='<div style="font-size:11px;color:#a855f7;font-weight:700;margin-bottom:6px">&#9889; Apercu : ton interface va changer</div>'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:6px">'+esc(d.titre||'')+'</div>'
    +'<div style="font-size:12px;opacity:.75;line-height:1.45;margin-bottom:8px">'+esc(d.explication||'')+'</div>'
    +'<pre style="background:rgba(0,0,0,.4);border-radius:8px;padding:10px;overflow:auto;font-size:11px;max-height:160px;white-space:pre-wrap;margin:0 0 12px">'+esc(d.css||'')+'</pre>'
    +'<div class="row" style="gap:8px;justify-content:flex-end">'
    +'<button id="'+id+'-no" class="ghost" style="font-size:12px;padding:6px 14px;color:#9ca3af">Annuler</button>'
    +'<button id="'+id+'-ok" style="font-size:12px;padding:6px 16px;background:#a855f7;border:none;border-radius:8px;color:#fff;font-weight:600;cursor:pointer">Appliquer a mon interface</button>'
    +'</div>';
  document.body.appendChild(el);
  document.getElementById(id+'-no').onclick=function(){el.remove();if(btn){btn.textContent='Annule';btn.disabled=false;}};
  document.getElementById(id+'-ok').onclick=async function(){
    this.disabled=true;this.textContent='Application...';
    try{
      const r=await fetch('/savoir/evolution/ui/appliquer',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({css:d.css,titre:d.titre||''})});
      const res=await r.json();
      if(r.ok&&res.ok){
        if(res.portee==='remonte'){
          el.innerHTML='<div style="font-size:13px;color:#10b981;font-weight:600">Propose a l\'admin pour validation.</div>';
          setTimeout(function(){el.remove();},3000);
        }else{
          el.innerHTML='<div style="font-size:13px;color:#10b981;font-weight:600">&#9889; Interface mise a jour. Rechargement…</div>';
          if(btn){btn.textContent='⚡ Interface modifiee';btn.style.color='#10b981';btn.style.borderColor='rgba(16,185,129,.3)';btn.style.background='rgba(16,185,129,.08)';}
          setTimeout(function(){location.reload();},1400);
        }
      }else{
        el.innerHTML='<div style="font-size:13px;color:#ef4444;font-weight:600">Refuse : '+esc((res&&res.detail)||(res&&res.raison)||'?')+'</div>';
        if(btn){btn.disabled=false;btn.textContent='Refuse';}
        setTimeout(function(){el.remove();},5000);
      }
    }catch(e){el.innerHTML='<div style="color:#ef4444">Erreur reseau</div>';}
  };
}

/* Charge l'override CSS d'interface au demarrage : l'evolution d'interface devient visible.
   Per-utilisateur : envoie le token -> chacun recoit le CSS de SON sac (isole des autres). */
async function _injectUserCss(){
  try{
    const r=await fetch('/savoir/evolution/ui.css',{cache:'no-store',headers:_authHdrs()});
    if(!r.ok)return;
    const css=await r.text();
    let st=document.getElementById('neogen-ui-overrides');
    if(!st){st=document.createElement('style');st.id='neogen-ui-overrides';document.head.appendChild(st);}
    st.textContent=css||'';
  }catch(e){}
}
(function(){
  if(document.readyState!=='loading')_injectUserCss();
  else document.addEventListener('DOMContentLoaded',_injectUserCss);
})();

/* Bulles de notification : poll des pensees a haut score non lues. */
(function(){
  function showBubble(b){
    if(document.getElementById('pensee-bubble-'+b.id))return;
    const el=document.createElement('div');
    el.id='pensee-bubble-'+b.id;
    el.style.cssText='position:fixed;right:20px;bottom:20px;max-width:300px;z-index:9999;padding:14px 16px;background:rgba(20,22,28,.96);border:1px solid rgba(245,158,11,.4);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.5);cursor:pointer;backdrop-filter:blur(8px);color:#e2e8f0';
    el.innerHTML='<div style="font-size:11px;color:#f59e0b;font-weight:700;margin-bottom:4px">&#128173; Une pensee a emerge</div>'
      +'<div style="font-size:13px;font-weight:600;margin-bottom:2px">'+esc(b.titre||'')+'</div>'
      +'<div style="font-size:11px;opacity:.6;line-height:1.4">'+esc((b.synthese||'').slice(0,110))+'</div>';
    el.onclick=async function(){
      try{await fetch('/savoir/pensees/'+encodeURIComponent(b.id)+'/lue',{method:'POST'});}catch(e){}
      el.remove();
      if(typeof showSection==='function')showSection('evolution');
    };
    document.body.appendChild(el);
    setTimeout(function(){if(el.parentNode)el.style.opacity='.85';},8000);
  }
  async function poll(){
    try{
      const r=await fetch('/savoir/pensees/bulles');
      if(!r.ok)return; // 403 si non-proprietaire -> on ignore
      const d=await r.json();
      (d.bulles||[]).slice(0,3).forEach(showBubble);
    }catch(e){}
  }
  setTimeout(poll,5000);
  setInterval(poll,60000);
})();

/* ===== SUPER-CAPACITE — evolution gouvernee ===== */
let _evoWired=false;
async function loadEvolutionSysteme(){
  const bridee=document.getElementById('evo-vue-bridee');
  const panneaux=document.getElementById('evo-panneaux-owner');
  try{
    const r=await fetch('/savoir/evolution/etat');
    const archMount=document.getElementById('evo-architecte-mount');
    if(!r.ok){
      // Non-proprietaire : Evolution reste visible mais bridee, chemin sur vers Mes skills.
      // L'Architecte (agent systeme, profil inexistant hors instance owner) reste cache :
      // pas de widget qui erreurait a chaque message.
      if(archMount)archMount.style.display='none';
      if(bridee)bridee.style.display='';
      if(panneaux)panneaux.style.display='none';
      const btn=document.getElementById('evo-vers-mes-skills');
      if(btn&&!btn._wired){
        btn._wired=true;
        btn.onclick=function(){showSection('compte');};
      }
      return;
    }
    if(archMount)archMount.style.display='';
    if(bridee)bridee.style.display='none';
    if(panneaux)panneaux.style.display='';
    const d=await r.json();
    const n=d.noyau||{};
    const corps=document.getElementById('evo-noyau-corps');
    if(corps){
      corps.innerHTML='<b>Mission</b> : '+esc((n.adn&&n.adn.mission)||'')
        +'<br><b>Murs</b> : '+esc(((n.murs)||[]).join(', '))
        +'<br><b>Zones protegees</b> : '+((n.zones_protegees)||[]).length+' fichiers du noyau';
    }
    const gen=d.generation||{};
    const gn=document.getElementById('evo-gen-num');if(gn)gn.textContent='v'+(gen.numero||1);
    const gc=document.getElementById('evo-gen-chg');if(gc)gc.textContent=gen.changements_cette_annee||0;
    const badge=document.getElementById('evo-portee-badge');
    if(badge)badge.textContent='ADMIN — capacite complete';
  }catch(e){return;}
  loadEvolutionChangelog();
  loadConscience();
  loadSubconscient();
  loadEvolutionCellules();
  loadFragments();
  if(_evoWired)return; _evoWired=true;
  wireFragments();
  const br=document.getElementById('btn-ui-reset');
  if(br)br.onclick=async function(){
    br.disabled=true;br.textContent='...';
    try{
      const r=await fetch('/savoir/evolution/ui/reset',{method:'POST'});
      if(r.ok){br.textContent='Reinitialisee';setTimeout(function(){location.reload();},900);}
      else{br.textContent='Erreur';br.disabled=false;}
    }catch(e){br.textContent='Erreur';br.disabled=false;}
  };
  const bp=document.getElementById('btn-evo-proposer');
  if(bp)bp.onclick=async function(){
    const st=document.getElementById('evo-proposer-status');
    const type=(document.getElementById('evo-type')||{}).value||'regle';
    const titre=(document.getElementById('evo-titre')||{}).value||'';
    const raison=(document.getElementById('evo-raison')||{}).value||'';
    let payload={};
    const ptxt=((document.getElementById('evo-payload')||{}).value||'').trim();
    if(ptxt){try{payload=JSON.parse(ptxt);}catch(e){if(st){st.style.display='';st.style.color='#ef4444';st.textContent='payload JSON invalide : '+esc(e.message);}return;}}
    if(st){st.style.display='';st.style.color='';st.textContent='Envoi...';}
    bp.disabled=true;
    try{
      const r=await fetch('/savoir/evolution/proposer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:type,payload:payload,titre:titre,raison:raison})});
      const d=await r.json();
      if(r.ok&&d.ok){
        if(st){st.style.color='#10b981';st.textContent='Propose (portee '+esc(d.portee||'?')+'). A approuver dans Propositions.';}
        loadHubPropositions();
      }else{
        if(st){st.style.color='#ef4444';st.textContent='Refuse par le noyau : '+esc((d&&d.detail)||(d&&d.raison)||'non autorise');}
      }
    }catch(e){if(st){st.style.color='#ef4444';st.textContent='Erreur : '+esc(e.message);}}
    finally{bp.disabled=false;}
  };
}

/* Activation de la Forge de blocs depuis "Donner vie" (voie forge_blocs).
   Charge l'apercu HTML dans le panel existant, scrolle vers la Forge, met a jour la zone. */
function _activerForgeBlocs(d){
  _fragApercuCourant={html:d.html,zone:d.zone||'evolution',titre:d.titre||''};
  const apZone=document.getElementById('frag-apercu-zone');
  const titreEl=document.getElementById('frag-apercu-titre');
  const renderEl=document.getElementById('frag-apercu-render');
  const explEl=document.getElementById('frag-apercu-expl');
  const zoneEl=document.getElementById('frag-zone');
  if(titreEl)titreEl.textContent='— '+esc(_fragApercuCourant.titre);
  if(renderEl)renderEl.innerHTML=_fragApercuCourant.html;
  if(explEl)explEl.textContent=d.explication||'';
  if(zoneEl)zoneEl.value=_fragApercuCourant.zone;
  if(apZone)apZone.style.display='';
  const forgeSection=document.getElementById('forge-frag-panel');
  if(forgeSection)forgeSection.scrollIntoView({behavior:'smooth',block:'start'});
  else if(apZone)apZone.scrollIntoView({behavior:'smooth',block:'nearest'});
}

/* --- Forge de fragments : de vrais blocs HTML injectes a l'ecran (proprio) --- */
var _fragApercuCourant=null;

async function loadFragments(){
  const sel=document.getElementById('frag-zone');
  const liste=document.getElementById('frag-liste');
  if(!sel||!liste)return;
  try{
    const r=await fetch('/savoir/fragments',{headers:_authHdrs()});
    if(r.status===403){const p=document.getElementById('forge-frag-panel');if(p)p.style.display='none';return;}
    if(!r.ok)return;
    const d=await r.json();
    // remplir le select des zones (une seule fois)
    if(!sel.dataset.rempli){
      sel.innerHTML=(d.zones||[]).map(function(z){return '<option value="'+esc(z[0])+'">'+esc(z[1])+'</option>';}).join('');
      sel.dataset.rempli='1';
    }
    // lister les fragments existants
    const frags=d.fragments||{};
    const zones=Object.keys(frags);
    if(!zones.length){liste.innerHTML='<div style="opacity:.4;font-size:12px">Aucun bloc forge. Decris-en un ci-dessus.</div>';return;}
    let html='';
    for(const z of zones){
      for(const f of frags[z]){
        const off=!f.actif;
        html+='<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:8px;margin-bottom:6px;'+(off?'opacity:.5':'')+'">'
          +'<span style="font-size:10px;padding:1px 7px;border-radius:8px;background:rgba(168,85,247,.15);color:#a855f7">'+esc(z)+'</span>'
          +'<span style="font-weight:600;font-size:12px">'+esc(f.titre||f.id)+'</span>'
          +'<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:rgba(59,130,246,.15);color:#3b82f6">v'+esc(f.version||'1')+'</span>'
          +'<span style="margin-left:auto;display:flex;gap:6px">'
          +'<button class="ghost" style="font-size:11px;padding:3px 9px" onclick="basculerFragment(\''+esc(z)+'\',\''+esc(f.id)+'\')">'+(off?'Activer':'Desactiver')+'</button>'
          +'<button class="ghost" style="font-size:11px;padding:3px 9px;color:#f59e0b" onclick="graverFragment(\''+esc(z)+'\',\''+esc(f.id)+'\',\''+esc(f.titre||f.id)+'\')">&#128190; Graver</button>'
          +'<button class="ghost" style="font-size:11px;padding:3px 9px;color:#ef4444" onclick="supprimerFragment(\''+esc(z)+'\',\''+esc(f.id)+'\')">Supprimer</button>'
          +'</span></div>';
      }
    }
    liste.innerHTML=html;
  }catch(e){}
}

function wireFragments(){
  const apBtn=document.getElementById('frag-apercu-btn');
  const apZone=document.getElementById('frag-apercu-zone');
  const st=document.getElementById('frag-status');
  if(apBtn)apBtn.onclick=async function(){
    const zone=(document.getElementById('frag-zone')||{}).value||'';
    const idee=((document.getElementById('frag-idee')||{}).value||'').trim();
    if(!idee){if(st){st.style.color='#ef4444';st.textContent='Decris le bloc d abord.';}return;}
    apBtn.disabled=true;apBtn.textContent='Generation...';
    if(st){st.style.color='';st.textContent='Le forgeron genere le bloc...';}
    try{
      const r=await fetch('/savoir/fragments/apercu',{method:'POST',headers:{'Content-Type':'application/json',..._authHdrs()},body:JSON.stringify({idee:idee,zone:zone})});
      const d=await r.json();
      if(r.ok&&d.ok){
        _fragApercuCourant={html:d.html,zone:zone,titre:d.titre};
        document.getElementById('frag-apercu-titre').textContent='— '+(d.titre||'');
        document.getElementById('frag-apercu-render').innerHTML=d.html;
        document.getElementById('frag-apercu-expl').textContent=d.explication||'';
        if(apZone)apZone.style.display='';
        if(st)st.textContent='';
      }else{if(st){st.style.color='#ef4444';st.textContent='Refuse : '+esc((d&&d.detail)||(d&&d.raison)||'echec');}}
    }catch(e){if(st){st.style.color='#ef4444';st.textContent='Erreur : '+esc(e.message);}}
    finally{apBtn.disabled=false;apBtn.textContent='Generer un apercu';}
  };
  const okBtn=document.getElementById('frag-appliquer-btn');
  if(okBtn)okBtn.onclick=async function(){
    if(!_fragApercuCourant)return;
    okBtn.disabled=true;okBtn.textContent='...';
    try{
      const r=await fetch('/savoir/fragments/appliquer',{method:'POST',headers:{'Content-Type':'application/json',..._authHdrs()},body:JSON.stringify(_fragApercuCourant)});
      const d=await r.json();
      if(r.ok&&d.ok){
        if(st){st.style.color='#10b981';st.textContent='Bloc applique ('+esc(d.action||'')+'). Recharge dans un instant...';}
        setTimeout(function(){location.reload();},1100);
      }else{if(st){st.style.color='#ef4444';st.textContent='Refuse : '+esc((d&&d.detail)||(d&&d.raison)||'echec');}}
    }catch(e){if(st){st.style.color='#ef4444';st.textContent='Erreur : '+esc(e.message);}}
    finally{okBtn.disabled=false;okBtn.textContent='Appliquer ce bloc';}
  };
  const gravBtn=document.getElementById('frag-graver-btn');
  if(gravBtn)gravBtn.onclick=async function(){
    if(!_fragApercuCourant)return;
    if(!confirm('Graver ce bloc dans le VRAI code (permanent, versionne git) ?\n\nUn backup automatique est cree et un rollback se declenche si le bloc casserait l interface.'))return;
    gravBtn.disabled=true;gravBtn.textContent='Gravure...';
    try{
      const r=await fetch('/savoir/ui-python/graver',{method:'POST',headers:{'Content-Type':'application/json',..._authHdrs()},body:JSON.stringify({zone:_fragApercuCourant.zone,html:_fragApercuCourant.html,titre:_fragApercuCourant.titre})});
      const d=await r.json();
      if(r.ok&&d.ok){
        if(st){st.style.color='#10b981';st.textContent='Bloc grave dans le code (permanent). Recharge...';}
        setTimeout(function(){location.reload();},1100);
      }else{if(st){st.style.color='#ef4444';st.textContent='Refuse : '+esc((d&&d.detail)||(d&&d.raison)||'echec');}}
    }catch(e){if(st){st.style.color='#ef4444';st.textContent='Erreur : '+esc(e.message);}}
    finally{gravBtn.disabled=false;gravBtn.innerHTML='&#128190; Graver (permanent, code)';}
  };
  const noBtn=document.getElementById('frag-annuler-btn');
  if(noBtn)noBtn.onclick=function(){_fragApercuCourant=null;if(apZone)apZone.style.display='none';if(st)st.textContent='';};
}

async function basculerFragment(zone,id){
  try{await fetch('/savoir/fragments/'+encodeURIComponent(zone)+'/'+encodeURIComponent(id)+'/basculer',{method:'POST',headers:_authHdrs()});location.reload();}catch(e){}
}
async function supprimerFragment(zone,id){
  if(!confirm('Supprimer ce bloc definitivement ?'))return;
  try{await fetch('/savoir/fragments/'+encodeURIComponent(zone)+'/'+encodeURIComponent(id)+'/supprimer',{method:'POST',headers:_authHdrs()});location.reload();}catch(e){}
}
async function graverFragment(zone,id,titre){
  if(!confirm('Graver ce bloc dans le VRAI code (permanent, versionné git) ?\n\nBackup auto + rollback si ça casse l\'interface.'))return;
  try{
    const rf=await fetch('/savoir/fragments/'+encodeURIComponent(zone)+'/'+encodeURIComponent(id),{headers:_authHdrs()});
    if(!rf.ok){alert('Impossible de recuperer le bloc.');return;}
    const frag=await rf.json();
    const r=await fetch('/savoir/ui-python/graver',{method:'POST',headers:{'Content-Type':'application/json',..._authHdrs()},body:JSON.stringify({zone:zone,html:frag.html,titre:titre})});
    const d=await r.json();
    if(r.ok&&d.ok){alert('Bloc grave dans le code (permanent). L\'interface va recharger.');location.reload();}
    else{alert('Refuse : '+((d&&d.detail)||(d&&d.raison)||'echec'));}
  }catch(e){alert('Erreur : '+e.message);}
}

const _STATUT_BADGE={
  actif:   {txt:'actif',   c:'#00e869',bg:'rgba(0,232,105,.12)', br:'rgba(0,232,105,.3)',  i:'&#9679;'},
  erreur:  {txt:'erreur',  c:'#ef4444',bg:'rgba(239,68,68,.12)',  br:'rgba(239,68,68,.3)',   i:'&#9888;'},
  inactif: {txt:'inactif', c:'#9ca3af',bg:'rgba(156,163,175,.1)', br:'rgba(156,163,175,.2)',i:'&#9675;'},
  inconnu: {txt:'?',       c:'#6b7280',bg:'rgba(107,114,128,.08)',br:'rgba(107,114,128,.2)',i:'&#8943;'},
};
function _statutBadge(s){
  const m=_STATUT_BADGE[s]||_STATUT_BADGE.inconnu;
  return '<span title="Statut : '+m.txt+'" style="display:inline-flex;align-items:center;gap:3px;font-size:9px;padding:1px 6px;border-radius:99px;color:'+m.c+';background:'+m.bg+';border:1px solid '+m.br+';white-space:nowrap;vertical-align:middle">'+m.i+' '+m.txt+'</span>';
}

async function loadEvolutionChangelog(){
  const c=document.getElementById('evo-changelog');
  if(!c)return;
  try{
    const r=await fetch('/savoir/evolution/generation');
    if(!r.ok)return;
    const d=await r.json();
    const log=(d.changelog)||[];
    if(!log.length){c.innerHTML='<div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucun changement applique cette annee.</div>';return;}
    c.innerHTML='';
    const _CL_COL={interface:'#06b6d4',regle:'#10b981',loi:'#f59e0b',idee:'#a855f7',agent:'#3b82f6',modele:'#ec4899',savoir:'#f97316',cellule:'#22d3ee',skill:'#fb923c',fonction:'#fb923c'};
    for(const e of log){
      const el=document.createElement('div');
      const sr=e.statut_reel||'inconnu';
      const borderCol=sr==='actif'?'rgba(0,232,105,.18)':sr==='erreur'?'rgba(239,68,68,.18)':'rgba(255,255,255,.07)';
      el.style.cssText='padding:8px 12px;background:rgba(255,255,255,.04);border-radius:8px;margin-bottom:6px;font-size:12px;border:1px solid '+borderCol;
      el.dataset.ctype=(e.type||'').toLowerCase();
      const dt=e.ts?new Date(e.ts*1000).toLocaleDateString():'';
      const col=_CL_COL[el.dataset.ctype]||'#10b981';
      const _vmatch=(e.detail||'').match(/\bv(\d+(?:\.\d+)*)\b/);
      const _vbadge=_vmatch?'<span style="display:inline-block;margin-left:6px;font-size:10px;padding:1px 6px;border-radius:10px;background:rgba(255,255,255,.1);color:#e2e8f0;vertical-align:middle">v'+esc(_vmatch[1])+'</span>':'';
      const _isMaj=(e.detail||'').includes('mis a jour');
      const _actionBadge=_isMaj?'<span style="display:inline-block;margin-left:4px;font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(251,146,60,.15);color:#fb923c;vertical-align:middle">MAJ</span>':'';
      el.innerHTML='<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
        +'<span style="font-weight:700;color:'+col+'">['+esc(e.type||'')+']</span> '
        +'<span style="font-weight:600">'+esc(e.titre||'')+'</span>'+_vbadge+_actionBadge
        +' '+_statutBadge(sr)
        +'<span style="margin-left:auto;opacity:.4;font-size:10px">'+esc(dt)+'</span>'
        +'</div>'
        +(e.detail?'<div style="opacity:.55;margin-top:3px;font-size:11px">'+esc(e.detail||'')+'</div>':'');
      if(_filtreChangelogCourant!=='tous'&&el.dataset.ctype!==_filtreChangelogCourant)
        el.style.display='none';
      c.appendChild(el);
    }
    requestAnimationFrame(function(){_applyMasonry('evo-changelog',215,8);});
  }catch(e){}
}

/* Bebe-agents custom : liste avec version + role court. */
async function loadBebeAgents(){
  const c=document.getElementById('bebeagents-list');
  if(!c)return;
  try{
    const r=await fetch('/savoir/evolution/etat');
    if(!r.ok)return;
    const d=await r.json();
    const agents=(d.stores||{}).agents_custom||{};
    const keys=Object.keys(agents);
    if(!keys.length){c.innerHTML='<div style="color:var(--mut);font-size:12px;opacity:.6">Aucun bebe-agent cree. « Donner vie » a une idee agent en cree un.</div>';return;}
    c.innerHTML='';
    for(const cle of keys){
      const a=agents[cle];
      const v=a.version||'1';
      const isMaj=v.includes('.');
      const vBadge='<span style="display:inline-block;font-size:10px;padding:1px 6px;border-radius:10px;background:'+(isMaj?'rgba(251,146,60,.18)':'rgba(59,130,246,.18)')+';color:'+(isMaj?'#fb923c':'#3b82f6')+';margin-left:6px">v'+esc(v)+'</span>';
      const majBadge=isMaj?'<span style="display:inline-block;font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(251,146,60,.12);color:#fb923c;margin-left:4px">MAJ</span>':'';
      const el=document.createElement('div');
      el.style.cssText='padding:10px 12px;background:rgba(59,130,246,.05);border:1px solid rgba(59,130,246,.12);border-radius:8px;margin-bottom:6px;font-size:12px';
      el.innerHTML='<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px">'
        +'<span style="font-weight:700;color:#3b82f6">'+esc(a.titre||cle)+'</span>'+vBadge+majBadge
        +'<span style="margin-left:auto;display:flex;gap:6px;align-items:center">'
        +'<span style="opacity:.4;font-size:10px">tier '+esc(a.tier||'moyen')+(a.outils&&a.outils.length?' · '+a.outils.length+' outils':'')+'</span>'
        +'<button class="ghost" style="font-size:10px;padding:2px 8px;color:#ef4444" onclick="supprimerBebeAgent(\''+esc(cle)+'\',\''+esc(a.titre||cle)+'\')">Supprimer</button>'
        +'</span></div>'
        +(a.role?'<div style="opacity:.55;margin-top:4px;line-height:1.5">'+esc(a.role)+'</div>':'');
      c.appendChild(el);
    }
  }catch(e){c.innerHTML='<div style="color:var(--mut);font-size:12px">Erreur chargement.</div>';}
}

async function supprimerBebeAgent(cle, titre){
  if(!confirm('Supprimer le bebe-agent "'+titre+'" ?\n\nCette action est irreversible.'))return;
  try{
    const r=await fetch('/savoir/evolution/agents/'+encodeURIComponent(cle),{method:'DELETE',headers:_authHdrs()});
    const d=await r.json();
    if(r.ok&&d.ok){loadBebeAgents();}
    else{alert('Refuse : '+((d&&d.raison)||(d&&d.detail)||'echec'));}
  }catch(e){alert('Erreur : '+e.message);}
}

/* Cellules forgees : le VRAI code genere par la forge. Clic -> deplie le code + verdict. */
async function loadEvolutionCellules(){
  const c=document.getElementById('evo-cellules');
  if(!c)return;
  try{
    const r=await fetch('/savoir/evolution/cellules',{headers:_authHdrs()});
    if(!r.ok)return;
    const d=await r.json();
    const cells=(d.cellules)||[];
    if(!cells.length){c.innerHTML='<div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucune cellule forgee. « Donner vie » a une idee technique en genere une.</div>';return;}
    c.innerHTML='';
    // Banner si des cellules sont a_reverifier
    const nbKo=cells.filter(cl=>cl.a_reverifier).length;
    if(nbKo){
      const banner=document.createElement('div');
      banner.style.cssText='padding:8px 12px;background:rgba(251,146,60,.1);border:1px solid rgba(251,146,60,.4);border-radius:8px;margin-bottom:10px;font-size:12px;display:flex;align-items:center;gap:8px';
      banner.innerHTML='<span style="color:#fb923c;font-size:15px">&#9888;</span>'
        +'<span style="flex:1;color:#fb923c"><b>'+nbKo+' cellule(s) a verifier</b> apres mise a jour du noyau — le code peut etre obsolete ou incompatible.</span>'
        +'<button class="ghost" style="font-size:11px;padding:4px 8px" onclick="scanCompatibilite()">Relancer scan</button>';
      c.appendChild(banner);
    }
    for(const cell of cells){
      const ko=!!cell.a_reverifier;
      const el=document.createElement('div');
      el.style.cssText='padding:10px 12px;background:'+(ko?'rgba(251,146,60,.05)':'rgba(16,185,129,.05)')+';border-radius:8px;margin-bottom:6px;font-size:12px;border:1px solid '+(ko?'rgba(251,146,60,.35)':'rgba(16,185,129,.18)');
      const dt=cell.ts?new Date(cell.ts*1000).toLocaleDateString():'';
      const det=document.createElement('details');
      const icone=ko?'&#9888;':'&#9889;';
      const couleur=ko?'#fb923c':'#10b981';
      const badgeKo=ko?'<span style="margin-left:6px;background:rgba(251,146,60,.15);color:#fb923c;border:1px solid rgba(251,146,60,.4);border-radius:4px;padding:1px 6px;font-size:10px">a verifier</span>':'';
      det.innerHTML='<summary style="cursor:pointer;list-style:none">'
        +'<span style="font-weight:700;color:'+couleur+'">'+icone+' '+esc(cell.nom||'')+'</span>'
        +badgeKo+' '
        +'<span style="opacity:.7">'+esc(cell.description||'')+'</span>'
        +'<span style="float:right;opacity:.5">score '+(cell.score||'--')+' &middot; '+esc(dt)+'</span>'
        +'</summary>';
      const corps=document.createElement('div');
      corps.style.cssText='margin-top:8px';
      const penseeLink=cell.pensee_id
        ?'<div style="font-size:11px;color:var(--mut);margin-bottom:6px">Nee de la pensee : <a href="#evolution" style="color:var(--acc);text-decoration:none" onclick="window._penseeScroll=\''+esc(cell.pensee_id)+'\'">'+esc(cell.pensee_titre||cell.pensee_id)+'</a></div>'
        :'';
      const raisonKo=ko&&cell.raison_reverification
        ?'<div style="font-size:11px;color:#fb923c;margin-bottom:6px;padding:4px 8px;background:rgba(251,146,60,.08);border-radius:4px">Erreur : '+esc(cell.raison_reverification)+'</div>'
        :'';
      corps.innerHTML=penseeLink+raisonKo
        +'<div style="opacity:.6;margin-bottom:6px">Verdict : '+esc(cell.verdict||'')
        +(cell.test&&cell.test.resume?' &middot; test : '+esc(cell.test.resume):'')+'</div>'
        +'<pre style="background:rgba(0,0,0,.35);border-radius:8px;padding:10px;overflow:auto;font-size:11px;max-height:300px;white-space:pre-wrap" id="cellcode-'+esc(cell.nom)+'">Chargement du code…</pre>';
      det.appendChild(corps);
      det.addEventListener('toggle',async function(){
        if(!det.open)return;
        const pre=document.getElementById('cellcode-'+cell.nom);
        if(pre&&pre.dataset.charge)return;
        try{
          const rc=await fetch('/savoir/evolution/cellules/'+encodeURIComponent(cell.nom),{headers:_authHdrs()});
          const dc=await rc.json();
          if(pre){pre.textContent=dc.code||'(code indisponible)';pre.dataset.charge='1';}
        }catch(e){if(pre)pre.textContent='Erreur de chargement';}
      });
      el.appendChild(det);
      c.appendChild(el);
    }
    requestAnimationFrame(function(){_applyMasonry('evo-cellules',215,8);});
  }catch(e){}
}

async function scanCompatibilite(){
  try{
    const r=await fetch('/savoir/evolution/compatibilite?forcer=true',{headers:_authHdrs()});
    const d=await r.json();
    loadEvolutionCellules();
    if(d.ko===0)alert('Toutes les cellules sont compatibles avec la version actuelle du noyau.');
  }catch(e){}
}

/* ===== CONSCIENCE DU SYSTEME : ce que NEOGEN sait de lui-meme ===== */
const _STATUT_META={
  integree:{l:'integree',c:'#00e869',b:'rgba(0,232,105,.14)',br:'rgba(0,232,105,.4)',i:'&#9889;'},
  stockee:{l:'stockee',c:'#38bdf8',b:'rgba(56,189,248,.12)',br:'rgba(56,189,248,.35)',i:'&#128190;'},
  forgee:{l:'forgee (sur disque)',c:'#fbbf24',b:'rgba(251,191,36,.12)',br:'rgba(251,191,36,.35)',i:'&#9881;'},
  a_reparer:{l:'a reparer',c:'#fb923c',b:'rgba(251,146,60,.14)',br:'rgba(251,146,60,.4)',i:'&#128295;'},
  echouee:{l:'en echec',c:'#ef4444',b:'rgba(239,68,68,.12)',br:'rgba(239,68,68,.4)',i:'&#10007;'},
  proposee:{l:'proposee',c:'#9ca3af',b:'rgba(156,163,175,.1)',br:'rgba(156,163,175,.3)',i:'&#8230;'},
  obsolete:{l:'obsolete',c:'#6b7280',b:'rgba(107,114,128,.1)',br:'rgba(107,114,128,.25)',i:'&#9866;'}
};
function _statutMeta(s){return _STATUT_META[s]||_STATUT_META.proposee;}

/* Tableau de bord de L'INGENIEUR : patchs de code proposes, autorisations noyau
   en attente (le mur : Jordan decide), badge rebuild requis. */
async function loadDecisionsIngenieur(){
  const wrap=document.getElementById('ing-decisions');
  if(!wrap)return;
  try{
    const r=await fetch('/savoir/evolution/ingenieur/decisions');
    if(!r.ok){wrap.style.display='none';return;}
    const d=await r.json();
    const decisions=d.decisions||[];
    if(!decisions.length){wrap.style.display='none';wrap.innerHTML='';return;}
    wrap.style.display='';
    wrap.innerHTML=decisions.map(function(dec){
      const opts=(dec.options||[]).map(function(o,i){
        return '<button class="ing-dec-opt ghost" data-job="'+esc(dec.job_id)+'" data-label="'+esc(o.label||'')+'" '
          +'style="font-size:12px;padding:8px 14px;text-align:left;display:block;width:100%;margin-bottom:6px;border-color:rgba(16,185,129,.4)">'
          +'<b>'+esc(o.label||'')+'</b>'+(o.description?'<div style="opacity:.6;font-size:11px;margin-top:2px">'+esc(o.description)+'</div>':'')
          +'</button>';
      }).join('');
      return '<div class="panel glass" style="margin-bottom:12px;border-color:rgba(16,185,129,.35)">'
        +'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
        +'<span style="font-size:16px">🔧</span>'
        +'<div style="font-size:12px;font-weight:700;color:#10b981">L\'Ingenieur attend ta decision — '+esc(dec.titre||'')+'</div>'
        +'</div>'
        +'<div style="font-size:13px;margin-bottom:12px;line-height:1.5">'+esc(dec.question||'')+'</div>'
        +opts
        +'<div style="display:flex;gap:8px;margin-top:8px">'
        +'<input type="text" class="ing-dec-autre" data-job="'+esc(dec.job_id)+'" placeholder="Ou ecris ta propre reponse…" '
        +'style="flex:1;font-size:12px;padding:8px 10px;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#e2e8f0">'
        +'<button class="ing-dec-envoyer ghost" data-job="'+esc(dec.job_id)+'" style="font-size:12px;padding:8px 14px">Envoyer</button>'
        +'</div>'
        +'<div class="ing-dec-err" style="display:none;font-size:11px;color:#ef4444;margin-top:6px"></div>'
        +'</div>';
    }).join('');
    async function _envoyerDecision(jobId, reponse, btn){
      if(!reponse.trim())return;
      const carte=btn.closest('.panel');
      const err=carte?carte.querySelector('.ing-dec-err'):null;
      if(err)err.style.display='none';
      const anciens=carte?Array.from(carte.querySelectorAll('button')):[];
      anciens.forEach(function(b){b.disabled=true;});
      try{
        const r=await fetch('/savoir/evolution/ingenieur/decisions/'+encodeURIComponent(jobId)+'/repondre',
          {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reponse:reponse.trim()})});
        const res=await r.json();
        if(!r.ok){if(err){err.textContent=res.detail||'Erreur';err.style.display='';}anciens.forEach(function(b){b.disabled=false;});return;}
        if(carte)carte.remove();
        if(res.job_id&&typeof _bulleProgression==='function')_bulleProgression(res.job_id,'ingenieur',null);
        loadDecisionsIngenieur();
      }catch(e){if(err){err.textContent='Erreur reseau.';err.style.display='';}anciens.forEach(function(b){b.disabled=false;});}
    }
    wrap.querySelectorAll('.ing-dec-opt').forEach(function(b){
      b.onclick=function(){_envoyerDecision(b.dataset.job,b.dataset.label,b);};
    });
    wrap.querySelectorAll('.ing-dec-envoyer').forEach(function(b){
      b.onclick=function(){
        const inp=wrap.querySelector('.ing-dec-autre[data-job="'+CSS.escape(b.dataset.job)+'"]');
        _envoyerDecision(b.dataset.job,(inp&&inp.value)||'',b);
      };
    });
  }catch(e){wrap.style.display='none';}
}

async function loadIngenieur(){
  loadDecisionsIngenieur();
  const box=document.getElementById('ingenieur-corps');
  if(!box)return;
  try{
    const r=await fetch('/savoir/evolution/ingenieur');
    if(!r.ok){box.innerHTML='<div style="opacity:.5;font-size:12px">Reserve au proprietaire.</div>';return;}
    const d=await r.json();
    // Badge rebuild dans la nav laterale.
    const navb=document.getElementById('ing-rebuild-nav');
    if(navb)navb.style.display=(d.rebuild&&d.rebuild.requis)?'':'none';
    let h='';
    // Badge rebuild requis.
    if(d.rebuild&&d.rebuild.requis){
      const nb=(d.rebuild.raisons||[]).length;
      h+='<div style="padding:10px 12px;margin-bottom:10px;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.4);border-radius:10px">'
        +'<div style="color:#f59e0b;font-weight:700;font-size:12px">&#9888; Rebuild requis</div>'
        +'<div style="font-size:11px;opacity:.75;margin:4px 0 8px">'+nb+' changement(s) de module attendent <code>docker compose up -d --build</code>.</div>'
        +'<button id="ing-rebuild-fait" class="ghost" style="font-size:11px;padding:5px 12px">Marquer rebuild fait</button></div>';
    }
    // Autorisations noyau (le mur).
    const auts=d.autorisations||[];
    if(auts.length){
      h+='<div style="font-size:12px;font-weight:700;color:#ef4444;margin:6px 0">&#128274; Autorisations noyau requises ('+auts.length+')</div>';
      auts.forEach(function(a){
        h+='<div style="padding:9px 11px;margin-bottom:7px;background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:9px">'
          +'<div style="font-size:12px;font-weight:600">'+esc(a.chemin||'')+'</div>'
          +'<div style="font-size:11px;opacity:.7;margin:3px 0 7px">'+esc(a.raison||'')+'</div>'
          +'<div class="row" style="gap:6px"><button class="ing-aut-ok ghost" data-id="'+esc(a.id)+'" style="font-size:11px;padding:4px 12px;color:#10b981">Autoriser</button>'
          +'<button class="ing-aut-no ghost" data-id="'+esc(a.id)+'" style="font-size:11px;padding:4px 12px;color:#ef4444">Refuser</button></div></div>';
      });
    }
    // Patchs proposes.
    const patchs=(d.patchs||[]).filter(function(p){return p.statut==='propose';});
    if(patchs.length){
      h+='<div style="font-size:12px;font-weight:700;margin:8px 0 4px">&#128296; Patchs proposes ('+patchs.length+')</div>';
      patchs.forEach(function(p){
        h+='<div style="padding:8px 11px;margin-bottom:6px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:9px">'
          +'<div style="font-size:12px;font-weight:600">'+esc(p.chemin||'')+'</div>'
          +'<div style="font-size:11px;opacity:.7">'+esc(p.raison||'')+'</div></div>';
      });
    }
    if(!h)h='<div style="opacity:.5;font-size:12px">Aucune intervention en attente. L\'Ingenieur agit quand tu donnes vie a une idee technique.</div>';
    box.innerHTML=h;
    // Wiring.
    const br=document.getElementById('ing-rebuild-fait');
    if(br)br.onclick=async function(){br.disabled=true;br.textContent='...';
      try{await fetch('/savoir/evolution/ingenieur/rebuild-fait',{method:'POST'});loadIngenieur();}catch(e){br.disabled=false;}};
    box.querySelectorAll('.ing-aut-ok').forEach(function(b){b.onclick=function(){_decideAut(b.dataset.id,true);};});
    box.querySelectorAll('.ing-aut-no').forEach(function(b){b.onclick=function(){_decideAut(b.dataset.id,false);};});
  }catch(e){box.innerHTML='<div style="opacity:.5;font-size:12px">Erreur de chargement.</div>';}
  // Champ « Confier une tache a l'Ingenieur » (cable une seule fois).
  const tbtn=document.getElementById('ing-tache-btn');
  const tinp=document.getElementById('ing-tache-input');
  if(tbtn&&tinp&&!tbtn._wired){
    tbtn._wired=true;
    const lancer=async function(){
      const d=(tinp.value||'').trim(); if(!d)return;
      tbtn.disabled=true;tbtn.textContent='…';
      try{
        const r=await fetch('/savoir/evolution/ingenieur/tache',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({demande:d})});
        const res=await r.json();
        if(r.ok&&res.job_id){
          tinp.value='';
          if(typeof _bulleProgression==='function')_bulleProgression(res.job_id,'ingenieur',tbtn);
          else{tbtn.textContent='Confiee';setTimeout(function(){tbtn.textContent='Confier';tbtn.disabled=false;},2000);}
        }else{tbtn.textContent='Erreur';tbtn.disabled=false;}
      }catch(e){tbtn.textContent='Erreur';tbtn.disabled=false;}
      setTimeout(function(){tbtn.textContent='Confier';tbtn.disabled=false;},1500);
    };
    tbtn.onclick=lancer;
    tinp.onkeydown=function(e){if(e.key==='Enter')lancer();};
  }
  // Bouton « Diagnostic instantane » (sans LLM, immediat).
  const dbtn=document.getElementById('ing-diag-btn');
  const dout=document.getElementById('ing-diag-out');
  if(dbtn&&dout&&!dbtn._wired){
    dbtn._wired=true;
    dbtn.onclick=async function(){
      dbtn.disabled=true;dbtn.textContent='…';dout.style.display='block';dout.textContent='Diagnostic en cours…';
      try{
        const r=await fetch('/savoir/evolution/ingenieur/diagnostic');
        const d=await r.json();
        dout.textContent=d.diagnostic||'(vide)';
      }catch(e){dout.textContent='Erreur de diagnostic.';}
      dbtn.disabled=false;dbtn.textContent='🔍 Diagnostic instantane';
    };
  }
}
async function _decideAut(aid,accordee){
  try{
    await fetch('/savoir/evolution/ingenieur/autorisation/'+encodeURIComponent(aid),
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accordee:accordee})});
    loadIngenieur();
  }catch(e){}
}

async function loadSubconscient(){
  const etatEl=document.getElementById('subconscient-etat');
  const revesEl=document.getElementById('subconscient-reves');
  if(!etatEl)return;
  try{
    const r=await fetch('/savoir/reves');
    if(!r.ok){etatEl.textContent='Indisponible';return;}
    const d=await r.json();
    const g=d.graphe||{};
    etatEl.innerHTML='<b>'+( g.concepts||0)+'</b> concepts &nbsp;·&nbsp; <b>'+(g.liens||0)+'</b> liens &nbsp;·&nbsp; <b>'+(g.ponts||0)+'</b> ponts &nbsp;·&nbsp; <b>'+(d.reves_archives||0)+'</b> reve(s) archive(s)';
    const reves=(d.reves||[]).slice(0,5);
    if(!reves.length){if(revesEl)revesEl.innerHTML='<div style="font-size:11px;opacity:.4;padding:6px 0">Aucun reve encore — clique « Faire rever NEOGEN » pour un premier cycle.</div>';return;}
    if(revesEl){
      revesEl.innerHTML='';
      for(const rv of reves){
        const el=document.createElement('div');
        el.style.cssText='padding:7px 10px;background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.18);border-radius:8px;font-size:11px';
        el.innerHTML='<span style="color:#f59e0b;font-weight:700">'+esc(rv.titre||'Reve')+'</span>'
          +' <span style="opacity:.4">(nouveaute '+((rv.nouveaute||0).toFixed(2))+')</span>'
          +(rv.paire?'<br><span style="opacity:.45">'+esc(rv.paire.join(' × '))+'</span>':'');
        revesEl.appendChild(el);
      }
    }
  }catch(e){if(etatEl)etatEl.textContent='Erreur chargement subconscient';}
}

async function faireRever(btn){
  const etatEl=document.getElementById('subconscient-etat');
  if(btn){btn.disabled=true;btn.textContent='Reve en cours…';}
  if(etatEl)etatEl.textContent='Bisociation + conceptual blending en cours…';
  try{
    const r=await fetch('/savoir/reves/rever',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({n:3})});
    const d=await r.json();
    if(r.ok&&d.ok){
      const msg=d.emergents>0?('&#127769; '+d.emergents+' reve(s) emergent(s) en bulle !'):('0 emergent (sous le seuil de nouveaute — NEOGEN enrichit quand meme l\'archive)');
      if(etatEl){etatEl.innerHTML='<span style="color:'+(d.emergents?'#f59e0b':'#9ca3af')+'">'+msg+'</span>';}
      setTimeout(loadSubconscient,800);
      if(d.emergents>0)setTimeout(function(){if(typeof loadPensees==='function')loadPensees();},1200);
    }else{
      if(etatEl)etatEl.textContent='Erreur : '+(d.detail||d.raison||'inconnu');
    }
  }catch(e){if(etatEl)etatEl.textContent='Erreur reseau : '+esc(e.message);}
  finally{if(btn){btn.disabled=false;btn.innerHTML='&#127769; Faire rever NEOGEN';}}
}

async function loadConscience(){
  const cont=document.getElementById('conscience-capacites');
  const jauge=document.getElementById('conscience-jauge');
  if(!cont)return;
  await _chargerAncrages();
  try{
    const r=await fetch('/savoir/conscience');
    if(!r.ok)return;
    const d=await r.json();
    const etat=d.etat||{};const caps=(d.capacites||[]).filter(function(c){return c.statut!=='obsolete';});
    // Jauge : sante globale + repartition par statut.
    if(jauge){
      const ps=etat.par_statut||{};
      let chips='<div style="font-size:22px;font-weight:800;color:'+(etat.sante_pct>=70?'#00e869':etat.sante_pct>=40?'#fbbf24':'#ef4444')+'">'
        +(etat.sante_pct!=null?etat.sante_pct:100)+'%<span style="font-size:11px;font-weight:400;opacity:.6"> sain</span></div>';
      chips+='<div style="font-size:11px;opacity:.7;align-self:center">'+(etat.total||0)+' capacite(s)</div>';
      for(const s in ps){const m=_statutMeta(s);
        chips+='<div style="align-self:center;font-size:11px;padding:3px 9px;border-radius:99px;color:'+m.c+';background:'+m.b+';border:1px solid '+m.br+'">'+m.i+' '+ps[s]+' '+m.l+'</div>';}
      jauge.innerHTML=chips;
    }
    if(!caps.length){cont.innerHTML='<div style="text-align:center;padding:18px;opacity:.4;font-size:12px">Aucune capacite enregistree. Donne vie a une idee : elle apparaitra ici avec son statut reel.</div>';return;}
    cont.innerHTML='';
    for(const cap of caps){
      const m=_statutMeta(cap.statut);
      const el=document.createElement('div');
      el.style.cssText='padding:9px 12px;background:'+m.b+';border:1px solid '+m.br+';border-radius:8px;margin-bottom:6px;font-size:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap';
      const consomme=(cap.consomme_par&&cap.consomme_par.length)?'<span style="opacity:.5;font-size:10px"> &rarr; '+esc(cap.consomme_par.join(', '))+'</span>':'';
      const sig=cap.signature?'<span style="opacity:.55;font-size:10px;font-family:ui-monospace,monospace"> '+esc(cap.signature)+'</span>':'';
      let inner='<span style="font-size:11px;padding:2px 9px;border-radius:99px;color:'+m.c+';background:rgba(0,0,0,.2);border:1px solid '+m.br+';white-space:nowrap">'+m.i+' '+m.l+'</span>'
        +'<span style="flex:1;min-width:140px"><b>'+esc(cap.titre||cap.id)+'</b> <span style="opacity:.45;font-size:10px">['+esc(cap.type||'?')+']</span>'+sig+consomme+'</span>';
      // Auto-cablage : pour une cellule integree, choisir OU elle se declenche toute seule.
      if(cap.type==='cellule'&&cap.statut==='integree'&&_ANCRAGES){
        let opts='';
        for(const k in _ANCRAGES){opts+='<option value="'+k+'"'+((cap.point_ancrage||'manuel')===k?' selected':'')+'>'+k+'</option>';}
        inner+='<select title="Point d-ancrage : ou la cellule s-execute automatiquement" onchange="definirAncrage(\''+esc(cap.id)+'\',this.value,this)" style="font-size:10px;padding:3px 6px;background:rgba(0,0,0,.25);border:1px solid rgba(0,232,105,.25);color:#9fe6b8;border-radius:6px">'+opts+'</select>';
      }
      if(cap.statut==='a_reparer'||cap.statut==='echouee'){
        inner+='<button onclick="reparerCapacite(\''+esc(cap.id)+'\',this)" style="font-size:11px;padding:4px 12px;background:rgba(251,146,60,.15);border:1px solid rgba(251,146,60,.4);color:#fb923c;border-radius:6px;cursor:pointer">&#128295; Reparer</button>';
      }
      el.innerHTML=inner;
      cont.appendChild(el);
    }
  }catch(e){}
}

let _ANCRAGES=null;
async function _chargerAncrages(){
  if(_ANCRAGES)return _ANCRAGES;
  try{const r=await fetch('/savoir/conscience/ancrages');if(r.ok){_ANCRAGES=(await r.json()).ancrages||{};}}catch(e){_ANCRAGES={};}
  return _ANCRAGES;
}

async function definirAncrage(id,point,sel){
  if(sel)sel.disabled=true;
  try{
    const r=await fetch('/savoir/conscience/'+encodeURIComponent(id)+'/ancrage',
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({point:point})});
    const d=await r.json();
    if(sel){sel.disabled=false;if(d.ok){sel.style.borderColor='rgba(0,232,105,.6)';setTimeout(function(){sel.style.borderColor='rgba(0,232,105,.25)';},1200);}}
  }catch(e){if(sel)sel.disabled=false;}
}

async function autoReparerConscience(btn){
  if(btn){btn.disabled=true;btn.textContent='Reparation…';}
  try{
    const r=await fetch('/savoir/conscience/auto-reparer',{method:'POST'});
    const d=await r.json();
    const n=(d.relancees||[]).length;
    if(btn){btn.innerHTML=n?('&#128295; '+n+' relancee(s)'):'Rien a reparer';setTimeout(function(){btn.innerHTML='&#128295; Auto-reparer';btn.disabled=false;},2500);}
    setTimeout(loadConscience,2500);
  }catch(e){if(btn){btn.textContent='Erreur';btn.disabled=false;}}
}

/* Resoudre un objectif : les 3 etats appliques, forge des manques, demandes de donnees. */
const _ETAT_META={CERTAIN:{c:'#00e869',i:'&#10003;'},INCONNU:{c:'#fbbf24',i:'&#9881;'},ANGLE_MORT:{c:'#fb923c',i:'?'}};
async function resoudreObjectif(btn){
  const inp=document.getElementById('obj-input');const out=document.getElementById('obj-resultat');
  const obj=(inp&&inp.value||'').trim();
  if(!obj){if(inp)inp.focus();return;}
  if(btn){btn.disabled=true;btn.textContent='Analyse…';}
  if(out){out.style.display='block';out.innerHTML='<div style="opacity:.6;font-size:12px;padding:8px">NEOGEN applique les 3 etats a ton objectif…</div>';}
  try{
    const r=await fetch('/savoir/objectif/resoudre',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({objectif:obj})});
    const d=await r.json();
    if(!d.ok){if(out)out.innerHTML='<div style="color:#ef4444;font-size:12px">Echec : '+esc(d.detail||d.raison||'')+'</div>';return;}
    const an=d.analyse;let h='';
    h+='<div style="font-size:12px;margin-bottom:8px"><b>'+(an.faisable?'<span style=\"color:#00e869\">Faisable</span>':'<span style=\"color:#fb923c\">A clarifier</span>')+'</b> &middot; '+esc(an.resume||'')+'</div>';
    h+='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;font-size:11px">';
    for(const k in an.compteurs){const m=_ETAT_META[k]||{c:'#888',i:'-'};h+='<span style="padding:2px 9px;border-radius:99px;color:'+m.c+';background:rgba(0,0,0,.25);border:1px solid '+m.c+'55">'+m.i+' '+an.compteurs[k]+' '+k.replace('_',' ')+'</span>';}
    h+='</div>';
    for(const e of an.elements){const m=_ETAT_META[e.etat]||{c:'#888',i:'-'};
      const det=esc(e.capacite_existante||e.besoin_forge||e.question||'');
      h+='<div style="font-size:11px;padding:4px 0;border-top:1px solid rgba(255,255,255,.05)"><span style="color:'+m.c+'">'+m.i+' '+e.etat.replace('_',' ')+'</span> &middot; '+esc(e.description)+(det?' <span style="opacity:.55">— '+det+'</span>':'')+'</div>';}
    if((d.forges||[]).length)h+='<div style="font-size:11px;margin-top:8px;color:#fbbf24">&#9881; '+d.forges.length+' brique(s) en cours de forge (vrai code teste, integre si OK).</div>';
    if((d.donnees_a_demander||[]).length)h+='<div style="font-size:11px;margin-top:8px;padding:8px;border-radius:8px;background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.3);color:#7dd3fc"><b>&#128274; Donnees a fournir</b> (je ne les invente pas) : '+esc(d.donnees_a_demander.join(' ; '))+'</div>';
    if((d.questions||[]).length)h+='<div style="font-size:11px;margin-top:8px;padding:8px;border-radius:8px;background:rgba(251,146,60,.1);border:1px solid rgba(251,146,60,.3);color:#fdba74"><b>? A clarifier</b> : '+esc(d.questions.join(' ; '))+'</div>';
    if(out)out.innerHTML=h;
    setTimeout(loadConscience,3000);
  }catch(e){if(out)out.innerHTML='<div style="color:#ef4444;font-size:12px">Erreur : '+esc(e.message)+'</div>';}
  finally{if(btn){btn.disabled=false;btn.textContent='Resoudre';}}
}

async function diagnostiquerConscience(btn){
  if(btn){btn.disabled=true;btn.textContent='Le systeme se regarde…';}
  try{
    const r=await fetch('/savoir/conscience/diagnostiquer',{method:'POST'});
    const d=await r.json();
    if(btn){
      const nb=(d.changements||[]).length;
      btn.textContent=nb?(nb+' changement(s) detecte(s)'):'A jour';
      setTimeout(function(){btn.textContent='Diagnostiquer';btn.disabled=false;},2200);
    }
    loadConscience();
  }catch(e){if(btn){btn.textContent='Erreur';btn.disabled=false;}}
}

async function reparerCapacite(id,btn){
  if(btn){btn.disabled=true;btn.textContent='Forge…';}
  try{
    const r=await fetch('/savoir/conscience/'+encodeURIComponent(id)+'/reparer',{method:'POST'});
    const d=await r.json();
    if(d.ok&&d.job_id){
      if(typeof _bulleProgression==='function')_bulleProgression(d.job_id,'cellule',btn);
      else if(btn){btn.textContent='Forge lancee';}
      setTimeout(loadConscience,2500);
    }else{
      if(btn){btn.textContent='Echec : '+((d.detail||d.raison||'')+'').slice(0,30);btn.disabled=false;}
    }
  }catch(e){if(btn){btn.textContent='Erreur';btn.disabled=false;}}
}

/* ══════════════════════════════════════════════════════════════════════════
   ONBOARDING — 3 étapes (Compte → Modèle IA → Profil)
   Déclenché au premier accès ou tant que profil_complet = false.
   Seul le login revient en cas d'expiration de session / inactivité.
   ══════════════════════════════════════════════════════════════════════════ */

const _INACTIVITY_MS = 7 * 24 * 60 * 60 * 1000; /* 7 jours */

/* Tracker d'activité — met à jour neogen_last_active toutes les 30s max */
(function(){
  var _tmr;
  function _touch(){try{localStorage.setItem('neogen_last_active',Date.now().toString());}catch(e){}}
  function _deb(){clearTimeout(_tmr);_tmr=setTimeout(_touch,30000);}
  ['mousemove','click','keydown','scroll','touchstart'].forEach(function(ev){
    document.addEventListener(ev,_deb,{passive:true});
  });
  _touch();
})();

function _isInactive(){
  try{
    var la=parseInt(localStorage.getItem('neogen_last_active')||'0',10);
    if(!la)return false;
    return(Date.now()-la)>_INACTIVITY_MS;
  }catch(e){return false;}
}


/* ===================================================================
   ONBOARDING 4 etapes - NEOGEN
   1: Bienvenue · 2: Presentation · 3: Compte+API · 4: Plans
=================================================================== */

/* ===== SYSTEME TUTORIAL (modal ? + tour guide) ===== */
var _TUTOS={
  cerveau:{titre:'Le Cerveau',icon:'🧠',color:'#a855f7',video:'/static/video_tuto/Cerveau.mp4',
    etapes:['Parle en langage naturel — le Cerveau comprend, délègue et synthétise',
             'Il forge ses propres compétences (skills) quand une tâche réussie est reproductible, et les réinvoque automatiquement la prochaine fois',
             'Sa mémoire retient tes préférences, projets et faits d\'une session à l\'autre pour personnaliser chaque réponse',
             'Crée des tâches autonomes — l\'agent agit seul selon le planning que tu fixes']},
  creation:{titre:'Création',icon:'✨',color:'var(--c-creation)',
    videos:['/static/video_tuto/ADN.mp4','/static/video_tuto/scanneretConseil.mp4'],
    etapes:['Décris ce que tu veux créer — texte, image, rapport, script, application...',
             'NEOGEN scanne ton intention et forge un ADN : la structure génétique qui définit ce que ta création va devenir',
             'Il génère ensuite le résultat avec le modèle IA que tu as configuré dans Intégrations, à partir de cet ADN',
             'Chaque résultat est archivé dans Production pour y revenir ou déployer']},
  production:{titre:'Production',icon:'📦',color:'var(--c-production)',video:'/static/video_tuto/Productionetligne.mp4',
    etapes:['Retrouve toutes tes créations — filtre par actives, toutes ou archivées',
             'Chaque création a une lignée : son historique de générations, tu peux comparer les versions et revenir à une génération précédente',
             'Déploie directement sur ton domaine Hostinger en un clic',
             'Chaque fichier est versionné et téléchargeable à tout moment']},
  compte:{titre:'Compte',icon:'👤',color:'var(--c-compte)',
    videos:['/static/video_tuto/comptedarkclair.mp4','/static/video_tuto/Pre_Compte.mp4'],
    etapes:['Configure ton profil — les agents l\'utilisent pour personnaliser leurs réponses',
             'Gère ton abonnement, tes crédits et ton historique de sessions']},
  analyse:{titre:'Dev & Analyse',icon:'📊',color:'var(--c-analyse)',video:'/static/video_tuto/devetanalyse.mp4',
    etapes:['Onglet Analyse : visualise les métriques en temps réel — requêtes, modèles, coûts, succès',
             'Onglet Ingénieur : confie une tâche de code, diagnostique ou répare en direct',
             'Les deux agents coordonnent pour observer ET améliorer le système']},
  evolution:{titre:'Evolution',icon:'🌱',color:'#10b981',video:'/static/video_tuto/evolution.mp4',
    etapes:['NEOGEN analyse ses silos de savoir et génère des propositions d\'amélioration',
             'Propose un sujet et déclenche une pensée : le système en discute, et plusieurs agents peuvent dialoguer entre eux sur ce sujet',
             'Tu peux participer à la conversation en direct plutôt que d\'observer seulement',
             'Chaque proposition te revient — tu approuves ou refuses, tu gardes le contrôle',
             'Les évolutions validées s\'intègrent au système en direct, sans redémarrage']},
  marketing:{titre:'Marketing',icon:'🪁',color:'var(--c-marketing)',video:'/static/video_tuto/Pre_Marketing.mp4',
    etapes:['Parle à Mercure — stratégie réseaux, copywriting, campagnes, visuels et vidéos IA',
             'Utilise un MCP créateur de vidéo ou d\'image (ex. Magnific) pour que l\'agent produise avec toi exactement ce que tu souhaites',
             'NotebookLM synthétise les tendances pour construire tes briefings marketing']},
  integrations:{titre:'Intégrations',icon:'🔌',color:'var(--c-integration)',video:'/static/video_tuto/Pre_Intergration.mp4',
    etapes:['Connecte ton modèle IA favori — Anthropic, OpenAI, Gemini, local (Ollama)...',
             'L\'agent RPA automatise des actions réelles sur ton ordinateur',
             'L\'apprentissage continu enregistre tes routines automatiquement']}
};
var _TOUR_ORDER=['cerveau','creation','production','evolution','marketing','integrations'];

function _tutoModal(section,opts){
  opts=opts||{};
  var t=_TUTOS[section];if(!t)return;
  var ov=document.createElement('div');
  ov.style.cssText='position:fixed;inset:0;z-index:10000;background:rgba(4,8,12,.96);display:flex;align-items:center;justify-content:center;padding:20px;animation:_fIn .18s ease';
  var box=document.createElement('div');
  box.style.cssText='background:rgba(10,18,30,.98);border:1px solid rgba(255,255,255,.1);border-radius:20px;width:min(560px,96vw);max-height:88vh;overflow-y:auto;padding:28px;position:relative';

  /* barre de progression tour */
  var progHtml='';
  if(opts.tourMode&&opts.total>1){
    progHtml='<div style="display:flex;gap:5px;justify-content:center;margin-bottom:22px">'
      +Array.from({length:opts.total},function(_,i){
        return '<div style="width:32px;height:3px;border-radius:99px;background:'+(i===opts.current?t.color||'#00ff41':'rgba(255,255,255,.12)')+'"></div>';
      }).join('')+'</div>';
  }

  /* video(s) + placeholder — supporte plusieurs videos par tuto (onglets) */
  var vids=t.videos||(t.video?[t.video]:[]);
  var vidTabs=vids.length>1?'<div style="display:flex;gap:6px;margin-bottom:8px">'
    +vids.map(function(_,i){
      return '<button class="ng-tvid-tab" data-i="'+i+'" style="flex:1;padding:6px 0;font-size:11px;font-weight:700;border-radius:8px;cursor:pointer;font-family:inherit;'
        +(i===0?'background:rgba(0,255,65,.12);border:1px solid rgba(0,255,65,.4);color:#00ff41':'background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4)')
        +'">'+(i+1)+'</button>';
    }).join('')+'</div>':'';
  var vid=vidTabs+'<div style="position:relative;border-radius:12px;overflow:hidden;background:#050d15;margin-bottom:22px;aspect-ratio:16/9">'
    +'<video id="ng-tvid" autoplay muted loop playsinline style="width:100%;height:100%;object-fit:cover;display:block;opacity:0;transition:opacity .3s">'
    +(vids[0]?'<source src="'+vids[0]+'" type="video/mp4">':'')+'</video>'
    +'<div id="ng-tph" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px;color:rgba(255,255,255,.25);text-align:center;pointer-events:none">'
    +'<div style="font-size:40px">🎬</div>'
    +'<div style="font-size:13px;line-height:1.5">Vidéo en cours de production<br><span style="font-size:11px;opacity:.6">Les étapes ci-dessous résument tout</span></div>'
    +'</div></div>';

  /* étapes numérotées */
  var steps='<div style="display:flex;flex-direction:column;gap:12px;margin-bottom:26px">'
    +t.etapes.map(function(e,i){
      return '<div style="display:flex;gap:12px;align-items:flex-start">'
        +'<div style="flex-shrink:0;width:24px;height:24px;border-radius:50%;background:rgba(0,255,65,.1);border:1px solid rgba(0,255,65,.28);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;color:#00ff41;margin-top:1px">'+(i+1)+'</div>'
        +'<div style="font-size:14px;color:rgba(255,255,255,.82);line-height:1.55">'+e+'</div>'
        +'</div>';
    }).join('')+'</div>';

  /* boutons */
  var isLast=opts.tourMode&&(opts.current===opts.total-1);
  var nav='<div style="display:flex;gap:8px">';
  if(opts.tourMode){
    nav+='<button id="ng-tskip" style="flex:1;background:transparent;border:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.35);border-radius:10px;padding:11px;font-size:13px;cursor:pointer;font-family:inherit">Passer le tour</button>';
    if(opts.current>0)nav+='<button id="ng-tprev" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);color:rgba(255,255,255,.7);border-radius:10px;padding:11px 16px;font-size:13px;cursor:pointer;font-family:inherit">← Retour</button>';
    nav+='<button id="ng-tnext" style="flex:2;background:rgba(0,255,65,.1);border:1px solid rgba(0,255,65,.4);color:#00ff41;border-radius:10px;padding:11px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit">'+(isLast?'Terminer ✓':'Suivant →')+'</button>';
  }else{
    nav+='<button id="ng-tclose" style="width:100%;background:rgba(0,255,65,.08);border:1px solid rgba(0,255,65,.35);color:#00ff41;border-radius:10px;padding:12px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit">Compris ✓</button>';
  }
  nav+='</div>';

  box.innerHTML=progHtml
    +'<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">'
    +'<div style="font-size:28px;line-height:1">'+t.icon+'</div>'
    +'<div><div style="font-size:18px;font-weight:800;color:#fff">'+t.titre+'</div>'
    +(opts.tourMode?'<div style="font-size:12px;color:rgba(255,255,255,.3);margin-top:2px">Étape '+(opts.current+1)+' / '+opts.total+'</div>':'')
    +'</div></div>'
    +vid+steps+nav;
  ov.appendChild(box);document.body.appendChild(ov);

  /* video canplay -> fade in, masque placeholder */
  var v=box.querySelector('#ng-tvid'),ph=box.querySelector('#ng-tph');
  if(v){
    v.addEventListener('canplay',function(){v.style.opacity='1';if(ph)ph.style.display='none';});
    v.load();
  }
  /* onglets multi-video : bascule la source au clic */
  box.querySelectorAll('.ng-tvid-tab').forEach(function(tab){
    tab.onclick=function(){
      var i=parseInt(tab.dataset.i,10);
      box.querySelectorAll('.ng-tvid-tab').forEach(function(b){
        var on=b===tab;
        b.style.background=on?'rgba(0,255,65,.12)':'rgba(255,255,255,.05)';
        b.style.borderColor=on?'rgba(0,255,65,.4)':'rgba(255,255,255,.1)';
        b.style.color=on?'#00ff41':'rgba(255,255,255,.4)';
      });
      if(v&&vids[i]){
        v.style.opacity='0';if(ph)ph.style.display='';
        v.querySelector('source').src=vids[i];
        v.load();
      }
    };
  });

  function _rm(){ov.remove();}
  var bc=box.querySelector('#ng-tclose');if(bc)bc.onclick=_rm;
  var bs=box.querySelector('#ng-tskip');if(bs)bs.onclick=function(){localStorage.setItem('neogen_tour_done','1');_rm();};
  var bn=box.querySelector('#ng-tnext');if(bn)bn.onclick=function(){_rm();if(opts.onNext)opts.onNext();else{localStorage.setItem('neogen_tour_done','1');}};
  var bp=box.querySelector('#ng-tprev');if(bp)bp.onclick=function(){_rm();if(opts.onPrev)opts.onPrev();};
  ov.addEventListener('click',function(e){if(e.target===ov)_rm();});
}

var _AGENT_TUTO={createur:'creation',analyste:'analyse',marketeur:'marketing',connecteur:'integrations',genealogiste:'evolution',secretaire:'compte',ingenieur:'analyse',architecte:'evolution'};
function showTuto(section){_tutoModal(_AGENT_TUTO[section]||section||'cerveau',{tourMode:false});}

function _startTour(){
  if(localStorage.getItem('neogen_tour_done'))return;
  var secs=_TOUR_ORDER;
  function go(i){
    if(i>=secs.length){localStorage.setItem('neogen_tour_done','1');return;}
    _tutoModal(secs[i],{tourMode:true,current:i,total:secs.length,
      onNext:function(){go(i+1);},
      onPrev:i>0?function(){go(i-1);}:null});
  }
  go(0);
}

/* Injection des boutons ? dans chaque section */
document.addEventListener('DOMContentLoaded',function(){
  Object.keys(_TUTOS).forEach(function(sec){
    var el=document.getElementById('section-'+sec);if(!el)return;
    var hdr=el.querySelector('.sec-header');if(!hdr)return;
    hdr.style.position='relative';
    var btn=document.createElement('button');
    btn.className='ghost';btn.title='Comment ça marche ?';btn.textContent='?';
    btn.style.cssText='position:absolute;top:4px;right:4px;width:32px;height:32px;padding:0;font-size:14px;font-weight:800;border-radius:50%;display:flex;align-items:center;justify-content:center;opacity:.85;transition:all .15s;font-family:inherit;border:1px solid rgba(0,255,65,.35);color:var(--acc);background:rgba(0,255,65,.07)';
    btn.onmouseenter=function(){this.style.opacity='1';this.style.background='rgba(0,255,65,.15)';};
    btn.onmouseleave=function(){this.style.opacity='.85';this.style.background='rgba(0,255,65,.07)';};
    btn.onclick=function(){showTuto(sec);};
    hdr.appendChild(btn);
  });
});

function _applyPremiumUi(palier){
  var free=(!palier||palier==='gratuit');
  document.querySelectorAll('.eco-toggle').forEach(function(el){
    if(free){
      el.classList.add('eco-locked');
      var cb=el.querySelector('input[type=checkbox]');if(cb){cb.checked=false;cb.disabled=true;}
      el.title='Mode premium requis — passez à Essential ou supérieur';
    }else{
      el.classList.remove('eco-locked');
      var cb=el.querySelector('input[type=checkbox]');if(cb)cb.disabled=false;
    }
  });
}

async function _checkOnboarding(){
  if(_authToken()&&_isInactive()){localStorage.removeItem('neogen_auth_token');}
  if(!_authToken()){_applyPremiumUi('gratuit');_showOnboardingOverlay(1);return;}
  const user=await _fetchMe();
  if(!user){localStorage.removeItem('neogen_auth_token');_applyPremiumUi('gratuit');_showOnboardingOverlay(1);return;}
  _applyPremiumUi(user.palier||'gratuit');
  if(!user.profil_complet){_showOnboardingOverlay(2,user);return;}
  if(!localStorage.getItem('neogen_ob_done')){_showOnboardingOverlay(4,user);return;}
  /* utilisateur completement onboarde -> tour guide si jamais vu */
  setTimeout(_startTour,600);
}

/* Overlay d'onboarding : MEME comportement en local et en public (coherence). Base
   uniquement sur l'etat reel (connecte ? profil complet ? onboarding deja fait ?),
   jamais sur le hostname — sinon le proprietaire ne peut jamais verifier ce flux en local.
   #landing demarre invisible (voir ui.py) pour eviter le flash de l'accueil avant que
   l'overlay ne se decide : on ne le revele qu'une fois la decision prise (avec ou sans
   overlay par-dessus, ca ne change rien puisque l'overlay est plein ecran). */
document.addEventListener('DOMContentLoaded',function(){
  var landingEl=document.getElementById('landing');
  function reveal(){if(landingEl)landingEl.style.visibility='';}
  _checkOnboarding().then(reveal).catch(reveal);
});

/* -- Canvas pluie Matrix ----------------------------------------- */
function _matrixCanvas(overlay){
  var c=document.createElement('canvas');
  c.style.cssText='position:absolute;inset:0;width:100%;height:100%;opacity:0.13;pointer-events:none;z-index:0';
  overlay.appendChild(c);
  var ctx=c.getContext('2d'),cols,drops;
  function init(){
    c.width=overlay.offsetWidth||window.innerWidth;
    c.height=overlay.offsetHeight||window.innerHeight;
    cols=Math.floor(c.width/14);
    drops=Array.from({length:cols},function(){return Math.random()*-60|0;});
  }
  init();
  window.addEventListener('resize',init,{passive:true});
  var chars='NEOGEN01アイウエオカキクケコサシスセソ23456789';
  var raf;
  function draw(){
    ctx.fillStyle='rgba(0,0,0,0.05)';ctx.fillRect(0,0,c.width,c.height);
    ctx.fillStyle='#00ff41';ctx.font='13px monospace';
    for(var i=0;i<drops.length;i++){
      ctx.fillText(chars[Math.random()*chars.length|0],i*14,drops[i]*14);
      if(drops[i]*14>c.height&&Math.random()>0.975)drops[i]=0;
      drops[i]++;
    }
    raf=requestAnimationFrame(draw);
  }
  draw();
  return function(){cancelAnimationFrame(raf);window.removeEventListener('resize',init);c.remove();};
}

function _showOnboardingOverlay(startStep,user){
  var ex=document.getElementById('ntr-onboarding');if(ex)ex.remove();
  var overlay=document.createElement('div');
  overlay.id='ntr-onboarding';
  overlay.style.cssText='position:fixed;inset:0;z-index:10000;background:#04080c;display:flex;align-items:center;justify-content:center;overflow:auto;padding:20px 0';
  document.body.appendChild(overlay);
  var stopMatrix=_matrixCanvas(overlay);
  var step=startStep;
  var _compteStartMode='register'; // 'register' ou 'login', mutable depuis _obBienvenue

  function render(){
    var oldBox=overlay.querySelector('.ntr-ob-box');if(oldBox)oldBox.remove();
    var isPlans=(step===4);
    var box=document.createElement('div');
    box.className='ntr-ob-box';
    box.style.cssText='position:relative;z-index:1;width:min('+(isPlans?'840px':'500px')+',96vw);max-height:92vh;overflow-y:auto;border-radius:24px;'
      +'background:rgba(2,14,5,.55);backdrop-filter:blur(38px) saturate(220%) brightness(.95);-webkit-backdrop-filter:blur(38px) saturate(220%) brightness(.95);'
      +'border:1px solid rgba(255,255,255,.12);padding:36px 32px 28px';
    overlay.appendChild(box);

    if(step>1){
      var labels={2:'Presentation',3:'Mon compte',4:'Mon pack'};
      var sh='<div style="display:flex;align-items:center;justify-content:center;gap:0;margin-bottom:28px">';
      for(var i=2;i<=4;i++){
        var done=i<step,active=i===step;
        sh+='<div style="display:flex;align-items:center">'
          +'<div style="display:flex;flex-direction:column;align-items:center;gap:5px">'
          +'<div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;transition:all .3s;'
          +(done?'background:#00ff41;color:#000;box-shadow:0 0 14px rgba(0,255,65,.5)':'')
          +(active?'background:rgba(0,255,65,.12);color:#00ff41;border:2px solid #00ff41;box-shadow:0 0 24px rgba(0,255,65,.25)':'')
          +(!done&&!active?'background:rgba(255,255,255,.05);color:rgba(255,255,255,.25);border:1px solid rgba(255,255,255,.08)':'')
          +'">'+(done?'✓':(i-1))+'</div>'
          +'<div style="font-size:10px;letter-spacing:.5px;'+(active?'color:#00ff41':'color:rgba(255,255,255,.25)')+'">'+labels[i]+'</div>'
          +'</div>';
        if(i<4)sh+='<div style="width:50px;height:1px;background:'+(done?'rgba(0,255,65,.4)':'rgba(255,255,255,.07)')+';margin:0 6px;margin-bottom:20px"></div>';
        sh+='</div>';
      }
      sh+='</div>';
      box.innerHTML=sh;
    }

    if(step===1)_obBienvenue(box,
      function(){_compteStartMode='register';step=2;render();},      // Commencer (flux normal)
      function(){_compteStartMode='login';step=3;render();}           // Deja inscrit -> login direct
    );
    else if(step===2)_obPresentation(box,function(){step=3;render();},function(){step=1;render();});
    else if(step===3){
      var _cm=_compteStartMode;_compteStartMode='register'; // reset apres usage
      _obCompte(box,function(u){
        /* Toujours presenter les packs/essai apres creation du compte.
           neogen_ob_done n'est pose QUE dans _obPlans (choix pack ou freemium explicite). */
        step=4;render();
      },_cm,function(){step=(_cm==='login')?1:2;render();});
    }
    else if(step===4)_obPlans(box,overlay,stopMatrix);
  }
  render();
}

/* -- Step 1 - Bienvenue ------------------------------------------ */
function _obBienvenue(box,onNext,onLogin){
  var d=document.createElement('div');
  d.style.cssText='text-align:center;padding:24px 8px 12px';
  d.innerHTML=''
    +'<div style="font-size:46px;font-weight:900;letter-spacing:5px;color:#00ff41;'
    +'text-shadow:0 0 40px rgba(0,255,65,.7),0 0 80px rgba(0,255,65,.3);margin-bottom:10px">NEOGEN</div>'
    +'<div style="font-size:11px;color:rgba(0,255,65,.45);letter-spacing:4px;text-transform:uppercase;margin-bottom:36px">Intelligence collective autonome</div>'
    +'<div style="font-size:15px;color:rgba(255,255,255,.65);line-height:1.75;max-width:400px;margin:0 auto 40px">'
    +'Bienvenue. NEOGEN est un systeme multi-agents qui pense, cree et evolue avec toi.<br>'
    +'Avant de commencer, laisse-moi apprendre a te connaitre.'
    +'</div>'
    +'<button id="ob-start" style="padding:16px 56px;font-size:16px;font-weight:800;'
    +'background:linear-gradient(160deg,#22e070 0%,#16c65e 55%,#0d9e48 100%);border:0;color:#04150a;'
    +'border-radius:16px;cursor:pointer;letter-spacing:2px;text-transform:uppercase;'
    +'transition:transform .18s,box-shadow .18s;'
    +'box-shadow:inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)">Commencer</button>'
    +'<div style="margin-top:22px;font-size:11px;color:rgba(255,255,255,.18)">'
    +'Prend 2 minutes &middot; 7 jours d\'essai gratuits &middot; Annulable a tout moment'
    +'</div>'
    +'<div style="margin-top:28px;padding-top:20px;border-top:1px solid rgba(255,255,255,.06)">'
    +'<span style="font-size:13px;color:rgba(255,255,255,.35)">Deja un compte ?</span> '
    +'<button id="ob-login-link" style="background:none;border:none;cursor:pointer;font-size:13px;'
    +'color:#00ff41;text-decoration:underline;text-underline-offset:3px;padding:0">Connecte-toi</button>'
    +'</div>'
    +'<div style="margin-top:26px;padding-top:22px;border-top:1px solid rgba(255,255,255,.06)">'
    +'<div style="font-size:10px;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:12px">3 facons d\'utiliser NEOGEN</div>'
    +'<div style="display:flex;flex-direction:column;gap:8px;text-align:left;max-width:380px;margin:0 auto">'
    +'<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.06);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.12)">'
    +'<span style="font-size:16px">&#9729;</span>'
    +'<div><div style="font-size:12px;font-weight:700;color:#00ff41">Cloud NetroIA (ici)</div>'
    +'<div style="font-size:11px;color:rgba(255,255,255,.4)">Heberge par NetroIA. Connecte ta cle IA pour demarrer (essai premium 7j). Clique "Commencer" ci-dessus.</div></div>'
    +'</div>'
    +'<a href="https://github.com/captainNetroia/NEOGEN" target="_blank" rel="noopener" style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.10);text-decoration:none">'
    +'<span style="font-size:16px">&#128187;</span>'
    +'<div><div style="font-size:12px;font-weight:700;color:#fff">En local, 100% gratuit</div>'
    +'<div style="font-size:11px;color:rgba(255,255,255,.4)">Sur ta machine, avec Ollama (aucune cle payante) ou ta propre cle. <code style="color:rgba(0,255,65,.6)">docker compose up</code></div></div>'
    +'</a>'
    +'<details style="border-radius:10px;background:rgba(255,255,255,.05);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.11);padding:0 12px">'
    +'<summary style="cursor:pointer;font-size:11px;color:#00ff41;padding:10px 0;list-style:none">&#128214; Tuto : une IA gratuite avec Ollama (2 min)</summary>'
    +'<div style="font-size:11px;color:rgba(255,255,255,.5);line-height:1.75;padding:2px 0 12px">'
    +'<b style="color:rgba(255,255,255,.75)">1.</b> Installe Ollama : <a href="https://ollama.com/download" target="_blank" rel="noopener" style="color:#00ff41;text-decoration:underline">ollama.com/download</a><br>'
    +'<b style="color:rgba(255,255,255,.75)">2.</b> Telecharge un modele (bon en francais et en JSON) :<br><code style="color:rgba(0,255,65,.7)">ollama pull qwen2.5</code><br>'
    +'<b style="color:rgba(255,255,255,.75)">3.</b> Lance NEOGEN sur ta machine :<br><code style="color:rgba(0,255,65,.7)">docker compose up</code><br>'
    +'<b style="color:rgba(255,255,255,.75)">4.</b> Dans NEOGEN &rarr; Integrations &rarr; choisis <b>Ollama (local)</b>, URL <code style="color:rgba(0,255,65,.7)">http://host.docker.internal:11434/v1</code>, modele <code style="color:rgba(0,255,65,.7)">qwen2.5</code>.<br>'
    +'<span style="color:rgba(255,255,255,.35)">Astuce : lance Ollama avec <code style="color:rgba(0,255,65,.55)">OLLAMA_HOST=0.0.0.0</code> pour qu\'il soit joignable depuis le conteneur. Zero cle, zero cout.</span>'
    +'</div></details>'
    +'<a href="https://github.com/captainNetroia/NEOGEN/blob/main/docker-compose.prod.yml" target="_blank" rel="noopener" style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.04);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.10);text-decoration:none">'
    +'<span style="font-size:16px">&#128274;</span>'
    +'<div><div style="font-size:12px;font-weight:700;color:#fff">Sur ton serveur, isole</div>'
    +'<div style="font-size:11px;color:rgba(255,255,255,.4)">Deploiement durci (socket-proxy + reseaux isoles), ton domaine.</div></div>'
    +'</a>'
    +'</div>'
    +'<div style="margin-top:14px;font-size:10px;color:rgba(255,255,255,.22)">Coeur open source sous '
    +'<a href="https://github.com/captainNetroia/NEOGEN/blob/main/LICENSE" target="_blank" rel="noopener" style="color:rgba(255,255,255,.4);text-decoration:underline">Business Source License 1.1</a>'
    +'</div>'
    +'<div style="margin-top:10px;font-size:10px;color:rgba(255,255,255,.28);display:flex;gap:14px;justify-content:center;flex-wrap:wrap">'
    +'<a href="/legal/mentions-legales" style="color:rgba(255,255,255,.4);text-decoration:none">Mentions legales</a>'
    +'<a href="/legal/cgu" style="color:rgba(255,255,255,.4);text-decoration:none">CGU</a>'
    +'<a href="/legal/confidentialite" style="color:rgba(255,255,255,.4);text-decoration:none">Confidentialite</a>'
    +'</div>'
    +'</div>';
  box.appendChild(d);
  var btn=d.querySelector('#ob-start');
  btn.onmouseenter=function(){this.style.boxShadow='inset 0 1.5px 0 rgba(255,255,255,.6),inset 0 -3px 8px rgba(0,0,0,.15),0 14px 40px rgba(0,200,80,.45),0 2px 6px rgba(0,0,0,.2)';this.style.transform='translateY(-2px)';};
  btn.onmouseleave=function(){this.style.boxShadow='inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)';this.style.transform='';};
  btn.onclick=onNext;
  var lnk=d.querySelector('#ob-login-link');
  if(lnk&&onLogin)lnk.onclick=onLogin;
}

/* -- Step 2 - Presentation (interrogatoire de copinage) ---------- */
function _obPresentation(box,onDone,onBack){
  var prev={};try{prev=JSON.parse(localStorage.getItem('neogen_ob_profil')||'{}');}catch(e){}
  var d=document.createElement('div');
  d.innerHTML=''
    +'<button id="ob-back2" style="background:none;border:none;cursor:pointer;font-size:12px;'
    +'color:rgba(255,255,255,.35);padding:0;margin-bottom:18px;display:flex;align-items:center;gap:4px">&larr; Retour</button>'
    +'<div style="text-align:center;margin-bottom:28px">'
    +'<div style="font-size:20px;font-weight:800;color:#fff;margin-bottom:8px">Fais connaissance avec NEOGEN</div>'
    +'<div style="font-size:13px;color:rgba(255,255,255,.45);line-height:1.6">'
    +'Ses agents utiliseront ces infos pour te parler comme il faut.<br>'
    +'Plus c\'est precis, plus NEOGEN s\'adapte a toi.'
    +'</div></div>'
    +'<div class="auth-form">'
    +'<div class="auth-field"><label>Comment tu veux qu\'on t\'appelle ? <span style="color:#ef4444">*</span></label>'
    +'<input type="text" id="ob-prenom" placeholder="Alex, Sam, Max..." value="'+(prev.prenom||'')+'" autocomplete="given-name"></div>'
    +'<div class="auth-field"><label>T\'es ou avec l\'IA ?</label>'
    +'<select id="ob-niveau" style="width:100%;padding:10px 12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:var(--txt);font-size:14px">'
    +'<option value="">- Ton niveau -</option>'
    +'<option value="debutant"'+(prev.niveau==='debutant'?' selected':'')+'>Debutant — Je decouvre l\'IA</option>'
    +'<option value="intermediaire"'+(prev.niveau==='intermediaire'?' selected':'')+'>Intermediaire — Je l\'utilise au quotidien</option>'
    +'<option value="avance"'+(prev.niveau==='avance'?' selected':'')+'>Avance — Je code avec les APIs</option>'
    +'<option value="expert"'+(prev.niveau==='expert'?' selected':'')+'>Expert — Je construis des systemes IA</option>'
    +'</select></div>'
    +'<div class="auth-field"><label>Tes passions / hobbies</label>'
    +'<textarea id="ob-hobbies" placeholder="IA, automatisation, gaming, musique, business, voyage..." rows="2" style="resize:none">'+(prev.hobbies||'')+'</textarea></div>'
    +'<div class="auth-field"><label>Ton style de travail</label>'
    +'<textarea id="ob-style" placeholder="Sessions longues le matin, plan avant d\'agir, autonome..." rows="2" style="resize:none">'+(prev.style_travail||'')+'</textarea></div>'
    +'<div class="auth-field"><label>Ta vision / ton projet</label>'
    +'<textarea id="ob-vision" placeholder="Lancer un SaaS IA, automatiser mon business, explorer les LLMs..." rows="2" style="resize:none">'+(prev.vision||'')+'</textarea></div>'
    +'<div class="auth-field"><label>Tes objectifs avec NEOGEN</label>'
    +'<textarea id="ob-objectifs" placeholder="Gagner du temps, creer des agents, apprendre..." rows="2" style="resize:none">'+(prev.objectifs||'')+'</textarea></div>'
    +'</div>'
    +'<div id="ob-err2" class="auth-error" style="display:none;margin-top:12px"></div>'
    +'<button id="ob-next2" style="width:100%;margin-top:18px;padding:14px;font-size:15px;font-weight:800;'
    +'background:linear-gradient(160deg,#22e070 0%,#16c65e 55%,#0d9e48 100%);border:0;color:#04150a;'
    +'border-radius:16px;cursor:pointer;transition:transform .18s,box-shadow .18s;'
    +'box-shadow:inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)">Suivant ></button>';
  box.appendChild(d);
  function qr(s){return d.querySelector(s);}
  if(onBack)qr('#ob-back2').onclick=onBack;
  qr('#ob-next2').onclick=function(){
    var prenom=(qr('#ob-prenom').value||'').trim();
    if(!prenom){var e=qr('#ob-err2');e.textContent='Dis-moi comment t\'appeler.';e.style.display='';return;}
    localStorage.setItem('neogen_ob_profil',JSON.stringify({
      prenom:prenom,niveau:qr('#ob-niveau').value,
      hobbies:(qr('#ob-hobbies').value||'').trim(),
      style_travail:(qr('#ob-style').value||'').trim(),
      vision:(qr('#ob-vision').value||'').trim(),
      objectifs:(qr('#ob-objectifs').value||'').trim()
    }));
    onDone();
  };
  setTimeout(function(){var el=qr('#ob-prenom');if(el)el.focus();},80);
}

/* -- Step 3 - Compte + API (optionnel) --------------------------- */
function _obCompte(box,onDone,startMode,onBack){
  var mode=startMode||'register';
  var prev={};try{prev=JSON.parse(localStorage.getItem('neogen_ob_profil')||'{}');}catch(e){}
  var fd=document.createElement('div');
  fd.innerHTML=''
    +'<button id="ob-back3" style="background:none;border:none;cursor:pointer;font-size:12px;color:rgba(255,255,255,.35);padding:0;margin-bottom:16px;display:flex;align-items:center;gap:4px">&larr; Retour</button>'
    +'<div style="text-align:center;margin-bottom:20px">'
    +'<div style="font-size:19px;font-weight:800;color:#fff;margin-bottom:5px">Cree ton compte NEOGEN</div>'
    +'<div style="font-size:13px;color:rgba(255,255,255,.35)">Pour sauvegarder ton profil et acceder a tes agents</div>'
    +'</div>'
    +'<div class="auth-tabs">'
    +'<div class="auth-tab active" id="ob-tab-r">Creer un compte</div>'
    +'<div class="auth-tab" id="ob-tab-l" style="opacity:.55">Deja un compte</div>'
    +'</div>'
    +'<div class="auth-form">'
    +'<div class="auth-field" id="ob-name-w"><label>Prenom</label>'
    +'<input type="text" id="ob-name" placeholder="Ton prenom..." value="'+(prev.prenom||'')+'"></div>'
    +'<div class="auth-field"><label>Email</label>'
    +'<input type="email" id="ob-email" placeholder="ton@email.com" autocomplete="email"></div>'
    +'<div class="auth-field"><label>Mot de passe</label>'
    +'<input type="password" id="ob-pw" placeholder="6 caracteres minimum..." autocomplete="new-password"></div>'
    +'<div class="auth-field" id="ob-pw2-w"><label>Confirmer le mot de passe</label>'
    +'<input type="password" id="ob-pw2" placeholder="..." autocomplete="new-password"></div>'
    +'<div id="ob-err3" class="auth-error" style="display:none"></div>'
    +'<button id="ob-sub3" style="width:100%;margin-top:6px;background:linear-gradient(160deg,#22e070 0%,#16c65e 55%,#0d9e48 100%);border:0;color:#04150a;border-radius:16px;font-weight:800;padding:14px;font-size:15px;cursor:pointer;transition:transform .18s,box-shadow .18s;box-shadow:inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)">Creer mon compte</button>'
    +'</div>'
    +'<div style="margin-top:18px;border-top:1px solid rgba(255,255,255,.06);padding-top:16px">'
    +'<div style="font-size:12px;color:rgba(255,255,255,.3);margin-bottom:10px;text-align:center">Optionnel — Connecte ton modele IA maintenant</div>'
    +'<div style="display:flex;gap:8px">'
    +'<select id="ob-prov3" style="flex:1;min-width:0;padding:9px 8px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:var(--txt);font-size:12px">'
    +'<option value="">Provider IA...</option>'
    +'<option value="anthropic">Anthropic (Claude)</option>'
    +'<option value="openai">OpenAI (GPT)</option>'
    +'<option value="gemini">Gemini</option>'
    +'<option value="deepseek">DeepSeek</option>'
    +'<option value="mistral">Mistral</option>'
    +'<option value="local">Ollama (local)</option>'
    +'</select>'
    +'<input type="password" id="ob-key3" placeholder="Cle API..." '
    +'style="flex:2;min-width:0;padding:9px 10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:var(--txt);font-size:12px;font-family:monospace" autocomplete="off">'
    +'</div>'
    +'</div>';
  box.appendChild(fd);
  var qr=function(s){return fd.querySelector(s);};
  var errEl=qr('#ob-err3'),sub=qr('#ob-sub3');
  var backBtn=qr('#ob-back3');if(backBtn&&onBack)backBtn.onclick=onBack;
  function setTab(m){
    mode=m;
    qr('#ob-tab-l').classList.toggle('active',m==='login');
    qr('#ob-tab-r').classList.toggle('active',m==='register');
    qr('#ob-tab-l').style.opacity=m==='login'?'1':'0.55';
    qr('#ob-tab-r').style.opacity=m==='register'?'1':'0.55';
    qr('#ob-name-w').style.display=m==='register'?'flex':'none';
    qr('#ob-pw2-w').style.display=m==='register'?'flex':'none';
    sub.textContent=m==='register'?'Creer mon compte':'Se connecter';
    errEl.style.display='none';
  }
  if(startMode==='login')setTab('login'); // positionnement initial si venu via "Deja un compte"
  qr('#ob-tab-r').onclick=function(){setTab('register');};
  qr('#ob-tab-l').onclick=function(){setTab('login');};
  async function doAuth(){
    var email=(qr('#ob-email').value||'').trim();
    var pw=qr('#ob-pw').value||'';
    var name=(qr('#ob-name')?qr('#ob-name').value||'':'');
    var pw2=(qr('#ob-pw2')?qr('#ob-pw2').value||'':'');
    errEl.style.display='none';
    if(!email||!pw){errEl.textContent='Email et mot de passe requis.';errEl.style.display='';return;}
    if(mode==='register'&&pw.length<6){errEl.textContent='Mot de passe trop court (6 min).';errEl.style.display='';return;}
    if(mode==='register'&&pw!==pw2){errEl.textContent='Mots de passe differents.';errEl.style.display='';return;}
    sub.disabled=true;sub.textContent='...';
    try{
      var url=mode==='login'?'/auth/login':'/auth/register';
      var regName=(name||(prev.prenom||'')||email.split('@')[0]).trim();
      var body=mode==='login'?{email:email,password:pw}:{email:email,password:pw,name:regName};
      var r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      var d=await r.json();
      if(!r.ok){errEl.textContent=d.detail||'Erreur';errEl.style.display='';sub.disabled=false;sub.textContent=mode==='register'?'Creer mon compte':'Se connecter';return;}
      localStorage.setItem('neogen_auth_token',d.token);
      if(typeof _injectUserCss==='function')_injectUserCss();
      if(prev&&prev.prenom){
        await fetch('/compte/profil',{method:'POST',
          headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),
          body:JSON.stringify({prenom:prev.prenom,projets:(prev.vision||''),aime:(prev.hobbies||''),naime_pas:'',style_travail:(prev.style_travail||'')})
        }).catch(function(){});
      }
      var prov=qr('#ob-prov3').value,key=(qr('#ob-key3').value||'').trim();
      if(prov&&key){
        var mdls={anthropic:['claude-opus-4-8'],openai:['gpt-5.2'],gemini:['gemini-3.1-pro-preview'],deepseek:['deepseek-v4-flash'],mistral:['mistral-large-latest'],local:['llama3.2']};
        localStorage.setItem('neogen_key_'+prov,key);
        localStorage.setItem('neogen_active_provider',prov);
        localStorage.setItem('neogen_active_model',(mdls[prov]&&mdls[prov][0])||'');
      }
      var me=await _fetchMe();
      onDone(me);
    }catch(e){errEl.textContent='Erreur reseau.';errEl.style.display='';sub.disabled=false;sub.textContent=mode==='register'?'Creer mon compte':'Se connecter';}
  }
  sub.onclick=doAuth;
  ['#ob-email','#ob-pw','#ob-pw2'].forEach(function(s){var el=qr(s);if(el)el.addEventListener('keydown',function(e){if(e.key==='Enter')doAuth();});});
  setTimeout(function(){var el=qr('#ob-email');if(el)el.focus();},80);
}

/* -- Step 4 - Choix de pack -------------------------------------- */
function _obPlans(box,overlay,stopMatrix){
  var prev={};try{prev=JSON.parse(localStorage.getItem('neogen_ob_profil')||'{}');}catch(e){}
  var prenom=prev.prenom?' '+prev.prenom:'';
  var d=document.createElement('div');
  d.innerHTML=''
    +'<div style="text-align:center;margin-bottom:30px">'
    +'<div style="font-size:22px;font-weight:900;color:#fff;margin-bottom:8px">Lance ton aventure'+prenom+' !</div>'
    +'<div style="font-size:13px;color:rgba(255,255,255,.4)">7 jours gratuits — annulable avant la fin d\'essai — rappel mail J-2</div>'
    +'</div>'

    /* Essential hero card */
    +'<div style="border:1px solid rgba(255,255,255,.14);border-radius:20px;padding:26px 28px;margin-bottom:22px;'
    +'background:rgba(2,14,5,.34);backdrop-filter:blur(32px) saturate(200%);-webkit-backdrop-filter:blur(32px) saturate(200%);'
    +'box-shadow:inset 0 1.5px 0 rgba(255,255,255,.14),inset 0 -16px 30px rgba(0,0,0,.20),0 0 50px rgba(0,255,65,.06)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:6px">'
    +'<div style="font-size:20px;font-weight:800;color:#00ff41;letter-spacing:1px">Essential</div>'
    +'<div style="background:rgba(0,255,65,.15);border:1px solid rgba(0,255,65,.5);border-radius:20px;padding:4px 14px;font-size:11px;color:#00ff41;font-weight:800;letter-spacing:1px">7 JOURS GRATUITS</div>'
    +'</div>'
    +'<div style="font-size:28px;font-weight:900;color:#fff;margin-bottom:18px">14,99€<span style="font-size:14px;font-weight:400;color:rgba(255,255,255,.4)">/mois apres essai</span></div>'
    +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px 20px;margin-bottom:22px">'
    +['1 500 GEN/mois','4 providers IA + local','Multi-agents RPA Apprentissage','Vision active Crons','5 Donner vie/mois','15 applis + 7 deploiements','10 Mode Juge/mois','Integrations tierces illimitees'].map(function(f){
      return'<div style="font-size:12.5px;color:rgba(255,255,255,.72);display:flex;align-items:center;gap:7px"><span style="color:#00ff41;font-size:10px">●</span>'+f+'</div>';
    }).join('')
    +'</div>'
    +'<button id="ob-essential" style="width:100%;padding:16px;font-size:15px;font-weight:900;background:linear-gradient(160deg,#22e070 0%,#16c65e 55%,#0d9e48 100%);color:#04150a;border:0;border-radius:16px;cursor:pointer;letter-spacing:1px;text-transform:uppercase;transition:transform .18s,box-shadow .18s;box-shadow:inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)">'
    +'Demarrer mon essai gratuit →'
    +'</button>'
    +'<div style="text-align:center;margin-top:10px;font-size:11px;color:rgba(255,255,255,.28)">'
    +'Rappel par mail 2 jours avant le 1er debit · Annulable a tout moment · Aucun frais cache'
    +'</div>'
    +'</div>'

    /* Pro + Power */
    +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">'
    +[
      {n:'Pro',p:'29,99€',pal:'pro',feats:['4 500 GEN/mois','6 providers IA + local','Crons illimites','15 Donner vie/mois · 50 applis','Webhook & API','⚡ ECLAIR -30 a -50% tokens']},
      {n:'Power',p:'49,99€',pal:'power',feats:['12 000 GEN/mois','Tous providers IA','50 Donner vie/mois · 200 applis','100 deploiements geres','Webhook & API','⚡ ECLAIR -30 a -50% tokens']}
    ].map(function(pk){
      return'<div style="border:1px solid rgba(255,255,255,.11);border-radius:16px;padding:18px;background:rgba(255,255,255,.05);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);box-shadow:inset 0 1px 0 rgba(255,255,255,.10)">'
        +'<div style="font-size:15px;font-weight:700;color:rgba(255,255,255,.85);margin-bottom:3px">'+pk.n+'</div>'
        +'<div style="font-size:22px;font-weight:800;color:#fff;margin-bottom:14px">'+pk.p+'<span style="font-size:11px;font-weight:400;color:rgba(255,255,255,.35)">/mois</span></div>'
        +pk.feats.map(function(f){return'<div style="font-size:11.5px;color:rgba(255,255,255,.48);margin-bottom:5px;display:flex;align-items:center;gap:5px"><span style="color:rgba(0,255,65,.4);font-size:9px">●</span>'+f+'</div>';}).join('')
        +'<button data-pal="'+pk.pal+'" class="ob-plan-btn" style="width:100%;margin-top:14px;padding:9px;font-size:13px;font-weight:600;background:rgba(255,255,255,.06);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.16);color:rgba(255,255,255,.7);border-radius:12px;cursor:pointer;transition:all .2s">Choisir '+pk.n+'</button>'
        +'</div>';
    }).join('')
    +'</div>'

    /* Enterprise */
    +'<div style="border:1px solid rgba(255,255,255,.10);border-radius:14px;padding:14px 20px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:12px;background:rgba(255,255,255,.03);backdrop-filter:blur(14px)">'
    +'<div><div style="font-size:14px;font-weight:700;color:rgba(255,255,255,.6)">Enterprise</div>'
    +'<div style="font-size:11.5px;color:rgba(255,255,255,.28);margin-top:2px">Infrastructure isolee · SLA 99,9% · Support dedie · Contrat personnalise</div></div>'
    +'<div style="font-size:14px;font-weight:700;color:rgba(255,255,255,.4);white-space:nowrap">Sur mesure</div>'
    +'</div>'

    /* Freemium */
    +'<div style="text-align:center">'
    +'<button id="ob-freemium" style="background:transparent;border:none;font-size:12px;color:rgba(255,255,255,.28);cursor:pointer;padding:10px 20px;text-decoration:underline">'
    +'Passer en version Freemium (acces limite, sans CB)'
    +'</button></div>';

  box.appendChild(d);

  d.querySelectorAll('.ob-plan-btn').forEach(function(btn){
    btn.onmouseenter=function(){this.style.background='rgba(255,255,255,.12)';this.style.borderColor='rgba(255,255,255,.28)';this.style.color='rgba(255,255,255,.9)';};
    btn.onmouseleave=function(){this.style.background='rgba(255,255,255,.06)';this.style.borderColor='rgba(255,255,255,.16)';this.style.color='rgba(255,255,255,.7)';};
  });

  var essBtn=d.querySelector('#ob-essential');
  essBtn.onmouseenter=function(){this.style.transform='translateY(-2px)';this.style.boxShadow='inset 0 1.5px 0 rgba(255,255,255,.6),inset 0 -3px 8px rgba(0,0,0,.15),0 14px 40px rgba(0,200,80,.45),0 2px 6px rgba(0,0,0,.2)';};
  essBtn.onmouseleave=function(){this.style.transform='';this.style.boxShadow='inset 0 1.5px 0 rgba(255,255,255,.55),inset 0 -3px 8px rgba(0,0,0,.15),0 10px 32px rgba(0,200,80,.35),0 2px 6px rgba(0,0,0,.2)';};
  essBtn.onclick=async function(){
    this.disabled=true;this.textContent='Redirection vers Stripe...';
    try{
      var r=await fetch('/premium/checkout',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),body:JSON.stringify({palier:'essential',plan:'mensuel'})});
      var j=await r.json();
      if(j.url){localStorage.setItem('neogen_ob_done','1');window.location.href=j.url;}
      else{this.disabled=false;this.textContent='Demarrer mon essai gratuit →';}
    }catch(e){this.disabled=false;this.textContent='Demarrer mon essai gratuit →';}
  };

  d.querySelectorAll('.ob-plan-btn').forEach(function(btn){
    btn.onclick=async function(){
      var pal=this.getAttribute('data-pal'),orig=this.textContent;
      this.disabled=true;this.textContent='...';
      try{
        var r=await fetch('/premium/checkout',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},_authHdrs()),body:JSON.stringify({palier:pal,plan:'mensuel'})});
        var j=await r.json();
        if(j.url){localStorage.setItem('neogen_ob_done','1');window.location.href=j.url;}
        else{this.disabled=false;this.textContent=orig;}
      }catch(e){this.disabled=false;this.textContent=orig;}
    };
  });

  d.querySelector('#ob-freemium').onclick=function(){
    localStorage.setItem('neogen_ob_done','1');
    stopMatrix();overlay.remove();loadCompte();
    setTimeout(_startTour,500);
  };
}

/* Lancer le check onboarding au chargement - DESACTIVE EN LOCAL */
(function(){})();

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
const LABELS={creation:'Creation',production:'Production',compte:'Compte',analyse:'Analyse',evolution:'Evolution',integrations:'Integrations',don:'Soutenir'};

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
  if(name==='cerveau'){loadMemoire();loadSkills();}
  if(name==='evolution'){loadHubEtat();loadHubPropositions();loadPenseesConfig();loadPensees();loadEvolutionSysteme();}
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
    moonshot:{label:'Kimi (Moonshot)',check:k=>k.trim().length>=8,
      models:['kimi-k2.7-code','kimi-k2.6','kimi-k2.7-code-highspeed','kimi-k2.5','moonshot-v1-128k'],
      ph:'sk-... (cle Moonshot)'},
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
      var dejaPayes=['anthropic','openai','gemini','deepseek','mistral','moonshot'].filter(function(pr){return pr!==curProv && localStorage.getItem('neogen_key_'+pr);});
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
  if(name==='cerveau'&&window.loadSkills){loadSkills();if(window.loadMemoire)loadMemoire();if(window.loadTaches)loadTaches();if(window.loadBebeAgents)loadBebeAgents();}
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
    +'<input type="checkbox" id="ececb-'+role+'"><span>&#127793; Eco</span></label>'
    +'<button class="agent-chat-clear" id="acclr-'+role+'" title="Effacer la conversation">&#128465;</button></div>'
    +'<div class="agent-chat-log" id="aclog-'+role+'"></div>'
    +'<div class="agent-chat-input" style="flex-direction:column;align-items:stretch">'
    +'<div class="ac-img-prev" id="acimgprev-'+role+'"></div>'
    +'<div style="display:flex;gap:8px;align-items:flex-end">'
    +'<textarea id="acin-'+role+'" rows="1" placeholder="Parler a '+esc(titre)+'... (Ctrl+V = coller image)"></textarea>'
    +'<input type="file" id="acfile-'+role+'" accept="image/*,.pdf,.pptx,.ppt,.docx,.doc,.txt,.md,.csv" style="display:none">'
    +'<button class="ghost" id="acattach-'+role+'" title="Joindre image ou fichier (PDF, PPTX, DOCX...)" style="padding:10px 12px;border-radius:12px;flex-shrink:0">&#128247;</button>'
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
  let _imgB64=null,_imgMime='image/png';
  let _fichierB64=null,_fichierNom='';
  function _clearImg(){_imgB64=null;_imgMime='image/png';if(imgPrev){imgPrev.style.display='none';imgPrev.innerHTML='';}if(fileIn)fileIn.value='';}
  function _clearDoc(){_fichierB64=null;_fichierNom='';if(imgPrev){imgPrev.style.display='none';imgPrev.innerHTML='';}if(fileIn)fileIn.value='';}
  function _setDoc(file){
    if(!file)return;
    _fichierNom=file.name;
    const fr=new FileReader();
    fr.onload=function(e){
      _fichierB64=e.target.result.split(',')[1];
      if(imgPrev){
        const ext=file.name.split('.').pop().toLowerCase();
        const ico=ext==='pdf'?'📄':ext==='pptx'||ext==='ppt'?'📊':ext==='docx'||ext==='doc'?'📝':'📎';
        imgPrev.style.display='flex';
        imgPrev.innerHTML=ico+' <span style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-left:4px">'+esc(file.name)+'</span><span style="cursor:pointer;padding:0 4px;font-weight:700;color:var(--ko)">×</span>';
        const x=imgPrev.querySelector('span:last-child');if(x)x.onclick=_clearDoc;
      }
    };
    fr.readAsDataURL(file);
  }
  function _setImg(file){
    if(!file||!file.type.startsWith('image/'))return;
    _imgMime=file.type||'image/png';
    const fr=new FileReader();
    fr.onload=function(e){
      _imgB64=e.target.result.split(',')[1];
      if(imgPrev){
        imgPrev.style.display='flex';
        imgPrev.innerHTML='<img src="'+e.target.result+'" alt="img"><span style="margin-left:auto;cursor:pointer;padding:0 4px;font-weight:700;color:var(--ko)">×</span>';
        const x=imgPrev.querySelector('span');if(x)x.onclick=_clearImg;
      }
    };
    fr.readAsDataURL(file);
  }
  if(attachBtn)attachBtn.onclick=function(){if(fileIn)fileIn.click();};
  if(fileIn)fileIn.onchange=function(e){
    const f=e.target.files&&e.target.files[0];if(!f)return;
    if(f.type.startsWith('image/')){_setImg(f);}else{_setDoc(f);}
  };
  inp.addEventListener('paste',function(e){
    var items=e.clipboardData&&e.clipboardData.items;if(!items)return;
    for(var i=0;i<items.length;i++){if(items[i].type.startsWith('image/')){_setImg(items[i].getAsFile());break;}}
  });
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
      const body={message:msg,historique:hist};
      if(_imgB64){body.image_b64=_imgB64;body.image_mime=_imgMime;}_clearImg();
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
    if(detail)detail.innerHTML='<span style="color:var(--ok);font-weight:600">'+esc(palierLabel[d.palier]||d.palier)+'</span>'
      +(d.gen_mensuel>0?' · <span style="color:#f59e0b">+'+d.gen_mensuel+' GEN/mois</span>':'');
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
  {cle:'essential',label:'Essential',prix:{mensuel:'14,99',annuel:'10,49'},couleur:'#6366f1',
   features:['Productions illimitees','1 provider IA','Mode Juge 1 GEN','200 GEN/mois']},
  {cle:'pro',label:'Pro',prix:{mensuel:'29,99',annuel:'20,99'},couleur:'#8b5cf6',
   features:['3 providers IA','RPA + Apprentissage','10 crons, Telegram','600 GEN/mois']},
  {cle:'power',label:'Power',prix:{mensuel:'49,99',annuel:'34,99'},couleur:'#a855f7',
   features:['Delegation multi-agents','Vision activee','Cron illimite','1 500 GEN/mois']},
  {cle:'enterprise',label:'Enterprise',prix:{mensuel:'99,99',annuel:'69,99'},couleur:'#d946ef',
   features:['GEN illimites','Telemetrie privee','Webhooks API','SLA 99,9%']},
];

function renderTarifs(palierActuel){
  var grid=document.getElementById('tarifs-grid');
  if(!grid)return;
  grid.innerHTML=_PALIERS.map(function(p){
    var actif=p.cle===palierActuel;
    var prix=p.prix[_tarifPeriod];
    var per=_tarifPeriod==='annuel'?'/mois (annuel)':'/mois';
    return '<div style="border:1px solid '+p.couleur+(actif?';box-shadow:0 0 0 2px '+p.couleur:'')+';border-radius:12px;padding:12px;background:rgba(0,0,0,.2)">'
      +'<div style="font-size:12px;font-weight:700;color:'+p.couleur+';margin-bottom:4px">'+esc(p.label)+'</div>'
      +'<div style="font-size:18px;font-weight:800;color:var(--txt);margin-bottom:6px">'+prix+'&#8364;<span style="font-size:10px;font-weight:400;color:var(--mut)">'+per+'</span></div>'
      +'<ul style="font-size:11px;color:var(--mut);padding:0 0 0 14px;margin:0 0 10px">'+p.features.map(function(f){return'<li>'+esc(f)+'</li>';}).join('')+'</ul>'
      +(actif?'<button class="ghost" disabled style="width:100%;font-size:11px;opacity:.5">Plan actuel</button>'
        :'<button class="ghost tarif-upgrade-btn" data-palier="'+p.cle+'" style="width:100%;font-size:11px;color:'+p.couleur+'">Choisir '+esc(p.label)+'</button>')
      +'</div>';
  }).join('');
  // Bind upgrade btns
  grid.querySelectorAll('.tarif-upgrade-btn').forEach(function(btn){
    btn.onclick=function(){_passerPremium(_tarifPeriod,btn.dataset.palier,btn);};
  });
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
// Vérification silencieuse owner au démarrage — masque Evolution si non-propriétaire
fetch('/savoir/etat').then(function(r){if(r.status===403){var si=document.getElementById('side-evolution');if(si)si.style.display='none';}}).catch(function(){});

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
    // Grouper par famille
    const groupes={};
    list.forEach(function(s){
      var f=_familleSkill(s);
      if(!groupes[f])groupes[f]=[];
      groupes[f].push(s);
    });
    const ORDRE=['RPA','Memoire','Creation','Analyse','Orchestration','General'];
    var html='';
    ORDRE.forEach(function(famille){
      if(!groupes[famille]||!groupes[famille].length)return;
      var col=_FAMILLE_COULEUR[famille]||'#6b7280';
      html+='<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:'+col+';padding:12px 0 6px;border-top:1px solid rgba(255,255,255,.06)">'
        +famille+' <span style="opacity:.5;font-weight:400">('+groupes[famille].length+')</span></div>';
      groupes[famille].forEach(function(s){
        html+='<div class="hist-item" style="align-items:flex-start">'
          +'<span class="tag ok" style="flex-shrink:0;background:'+col+'22;color:'+col+';border:1px solid '+col+'44">'+esc(s.nom)+'</span>'
          +'<span style="flex:1"><b style="font-size:13px">'+esc(s.titre||s.nom)+'</b>'
          +(s.auto?' <span class="badge live" style="font-size:9px">auto</span>':'')
          +'<br><span style="font-size:12px;color:var(--mut)">'+esc(s.description||'')+'</span>'
          +(s.outils&&s.outils.length?'<br><span style="font-size:11px;color:var(--mut)">outils: '+esc(s.outils.join(', '))+'</span>':'')
          +'</span>'
          +'<span style="color:var(--ko);cursor:pointer;font-weight:700;flex-shrink:0" title="Supprimer" onclick="deleteSkill(\''+esc(s.nom)+'\')">&times;</span>'
          +'</div>';
      });
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

async function openSkillsLibrary(){
  const modal=document.getElementById('skills-lib-modal');
  const listEl=document.getElementById('skills-lib-list');
  modal.style.display='flex';
  listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Chargement du registry...</div>';
  try{
    const d=await(await fetch('/skills/registry')).json();
    const list=d.skills||[];
    if(!list.length){listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Aucun skill disponible.</div>';return;}
    // Charger les skills deja installes pour griser les boutons.
    const installed=await(await fetch('/skills')).json();
    const installedNames=new Set((installed.skills||[]).map(function(s){return s.nom;}));
    listEl.innerHTML=list.map(function(s,i){
      const already=installedNames.has(s.nom)||installedNames.has(s.nom.replace(/\s+/g,'_').toLowerCase());
      return '<div class="hist-item" style="align-items:flex-start;margin-bottom:8px">'
        +'<span style="flex:1"><b style="font-size:13px">'+esc(s.titre||s.nom)+'</b>'
        +'<br><span style="font-size:12px;color:var(--mut)">'+esc(s.description||'')+'</span>'
        +(s.outils&&s.outils.length?'<br><span style="font-size:11px;color:var(--mut)">outils: '+esc(s.outils.join(', '))+'</span>':'')
        +'</span>'
        +(already
          ?'<span class="tag ok" style="font-size:11px;flex-shrink:0">installe</span>'
          :'<button class="ghost" style="font-size:12px;padding:3px 10px;flex-shrink:0" onclick="installSkill('+i+')">Installer</button>')
        +'</div>';
    }).join('');
    window._libSkills=list;
  }catch(e){listEl.innerHTML='<div style="color:var(--mut);font-size:13px">Erreur : '+esc(String(e))+'</div>';}
}

window.installSkill=async function(idx){
  const s=window._libSkills&&window._libSkills[idx];if(!s)return;
  try{
    const r=await(await fetch('/skills/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({skills:[s]})})).json();
    if(r.importes&&r.importes.length){
      openSkillsLibrary();loadSkills();
    }else if(r.ignores&&r.ignores.length){
      alert('Deja installe.');
    }else{
      alert('Erreur : '+(r.erreurs||[]).join(', '));
    }
  }catch(e){alert('Erreur reseau.');}
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
  loadTaches();
})();
/* ===== HUB DU SAVOIR — section Evolution ===== */
async function loadHubEtat(){
  try{
    const r=await fetch('/savoir/etat');
    if(r.status===403){
      const si=document.getElementById('side-evolution');if(si)si.style.display='none';
      const lc=document.querySelector('[onclick*="showSection(\'evolution\')"]');if(lc)lc.style.display='none';
      return;
    }
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
      if(d.ok) _bulleVieDonnee(p.titre||'');
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
  // Masquer/afficher cartes selon le type
  container.querySelectorAll('.pensee-groupe-header').forEach(function(h){
    h.style.display=(type==='tous'||h.dataset.groupe===type)?'':'none';
  });
  container.querySelectorAll('[data-ptype]').forEach(function(c){
    if(type==='tous'){
      // Réappliquer le filtre de statut
      var et=c.dataset.etat||'';
      var f=_filtrePenseesCourant;
      var vis=f==='tous'?(et!=='archivee'):f==='pris-en-vie'?(et==='actif'||et==='generee'):f==='bulle'?(c.dataset.bulle==='1'&&et!=='archivee'):(et===f);
      c.style.display=vis?'':'none';
    }else{
      c.style.display=(c.dataset.ptype===type)?'':'none';
    }
  });
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

/* Bulle de PROGRESSION vivante : la forge n'est pas instantanee (Opus + Docker).
   Poll /savoir/evolution/forge/{jobId} et montre l'etape reelle jusqu'au verdict. */
function _bulleProgression(jobId,titre,btn){
  const el=document.createElement('div');
  el.id='forge-bubble-'+jobId;
  el.style.cssText='position:fixed;right:20px;bottom:20px;max-width:340px;z-index:10000;padding:16px 18px;background:rgba(16,22,30,.98);border:1px solid rgba(168,85,247,.55);border-radius:14px;box-shadow:0 14px 40px rgba(0,0,0,.65);backdrop-filter:blur(10px)';
  el.innerHTML='<div style="font-size:11px;color:#a855f7;font-weight:700;margin-bottom:6px">&#9889; Votre idee prend vie</div>'
    +'<div id="fp-etape-'+jobId+'" style="font-size:13px;font-weight:600;margin-bottom:8px">Initialisation…</div>'
    +'<div style="height:6px;background:rgba(255,255,255,.08);border-radius:6px;overflow:hidden">'
    +'<div id="fp-bar-'+jobId+'" style="height:100%;width:5%;background:linear-gradient(90deg,#a855f7,#10b981);transition:width .5s"></div></div>'
    +'<div id="fp-note-'+jobId+'" style="font-size:11px;opacity:.55;line-height:1.4;margin-top:8px">La forge genere du vrai code, le teste en sandbox isolee, puis controle les murs. Cela prend un moment.</div>';
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
    if(st.etat==='generee'){
      clearInterval(timer);
      if(et)et.textContent='⚡ Code genere & teste';
      el.style.borderColor='rgba(16,185,129,.6)';
      if(note)note.innerHTML='Cellule <b>'+esc(st.nom||'')+'</b> (score '+(st.score||'--')+'). Voir « Cellules forgees ». Recharge dans 2s.';
      if(btn){btn.textContent='⚡ Code genere';btn.style.color='#10b981';btn.style.borderColor='rgba(16,185,129,.3)';btn.style.background='rgba(16,185,129,.08)';}
      if(typeof loadEvolutionSysteme==='function')setTimeout(loadEvolutionSysteme,400);
      setTimeout(function(){location.reload();},2200);
    }else if(st.etat==='refusee'){
      clearInterval(timer);
      if(et)et.textContent='✗ Refuse';
      el.style.borderColor='rgba(239,68,68,.6)';
      if(bar)bar.style.background='#ef4444';
      if(note)note.textContent='Refuse : '+(st.raison||'raison inconnue')+'. Aucun code installe.';
      if(btn){btn.textContent='✗ Refuse';btn.style.color='#ef4444';btn.disabled=false;}
      setTimeout(function(){if(el.parentNode)el.remove();},8000);
    }
  },1500);
}

/* Apercu d'une evolution d'INTERFACE : montre le CSS reel + ce que ca change,
   puis APPLIQUE sur confirmation (decision Jordan : donner vie -> apercu -> confirmer). */
function _bulleApercuInterface(d,btn){
  const id='ui-apercu-'+Math.random().toString(36).slice(2);
  const el=document.createElement('div');
  el.id=id;
  el.style.cssText='position:fixed;right:20px;bottom:20px;max-width:420px;z-index:10001;padding:18px;background:rgba(16,22,30,.99);border:1px solid rgba(168,85,247,.55);border-radius:14px;box-shadow:0 16px 44px rgba(0,0,0,.7);backdrop-filter:blur(10px)';
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

/* Charge l'override CSS d'interface au demarrage : l'evolution d'interface devient visible. */
(function(){
  async function injecter(){
    try{
      const r=await fetch('/savoir/evolution/ui.css',{cache:'no-store'});
      if(!r.ok)return;
      const css=await r.text();
      let st=document.getElementById('neogen-ui-overrides');
      if(!st){st=document.createElement('style');st.id='neogen-ui-overrides';document.head.appendChild(st);}
      st.textContent=css||'';
    }catch(e){}
  }
  if(document.readyState!=='loading')injecter();
  else document.addEventListener('DOMContentLoaded',injecter);
})();

/* Bulles de notification : poll des pensees a haut score non lues. */
(function(){
  function showBubble(b){
    if(document.getElementById('pensee-bubble-'+b.id))return;
    const el=document.createElement('div');
    el.id='pensee-bubble-'+b.id;
    el.style.cssText='position:fixed;right:20px;bottom:20px;max-width:300px;z-index:9999;padding:14px 16px;background:rgba(20,22,28,.96);border:1px solid rgba(245,158,11,.4);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.5);cursor:pointer;backdrop-filter:blur(8px)';
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
  try{
    const r=await fetch('/savoir/evolution/etat');
    if(!r.ok)return;
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
    if(badge){
      const admin=await fetch('/savoir/etat').then(function(x){return x.status!==403;}).catch(function(){return false;});
      badge.textContent=admin?'ADMIN — capacite complete':'PUBLIC — bride';
    }
  }catch(e){}
  loadEvolutionChangelog();
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
  const forgeSection=document.getElementById('forge-section')||document.querySelector('[data-section="forge"]');
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
      el.style.cssText='padding:8px 12px;background:rgba(255,255,255,.04);border-radius:8px;margin-bottom:6px;font-size:12px;border:1px solid rgba(255,255,255,.07)';
      el.dataset.ctype=(e.type||'').toLowerCase();
      const dt=e.ts?new Date(e.ts*1000).toLocaleDateString():'';
      const col=_CL_COL[el.dataset.ctype]||'#10b981';
      // Extraire la version du detail (ex: "bebe-agent 'x' mis a jour v1.2 ...")
      const _vmatch=(e.detail||'').match(/\bv(\d+(?:\.\d+)*)\b/);
      const _vbadge=_vmatch?'<span style="display:inline-block;margin-left:6px;font-size:10px;padding:1px 6px;border-radius:10px;background:rgba(255,255,255,.1);color:#e2e8f0;vertical-align:middle">v'+esc(_vmatch[1])+'</span>':'';
      const _isMaj=(e.detail||'').includes('mis a jour');
      const _actionBadge=_isMaj?'<span style="display:inline-block;margin-left:4px;font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(251,146,60,.15);color:#fb923c;vertical-align:middle">MAJ</span>':'';
      el.innerHTML='<span style="font-weight:700;color:'+col+'">['+esc(e.type||'')+']</span> '
        +'<span style="font-weight:600">'+esc(e.titre||'')+'</span>'+_vbadge+_actionBadge
        +'<span style="float:right;opacity:.4">'+esc(dt)+'</span>'
        +'<div style="opacity:.6;margin-top:2px">'+esc(e.detail||'')+'</div>';
      // Appliquer le filtre courant immediatement
      if(_filtreChangelogCourant!=='tous'&&el.dataset.ctype!==_filtreChangelogCourant)
        el.style.display='none';
      c.appendChild(el);
    }
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
    const r=await fetch('/savoir/evolution/cellules');
    if(!r.ok)return;
    const d=await r.json();
    const cells=(d.cellules)||[];
    if(!cells.length){c.innerHTML='<div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucune cellule forgee. « Donner vie » a une idee technique en genere une.</div>';return;}
    c.innerHTML='';
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
        +'<pre style="background:rgba(0,0,0,.35);border-radius:8px;padding:10px;overflow:auto;font-size:11px;max-height:300px;white-space:pre-wrap" id="cellcode-'+esc(cell.nom)+'">Chargement du code…</pre>';
      det.appendChild(corps);
      det.addEventListener('toggle',async function(){
        if(!det.open)return;
        const pre=document.getElementById('cellcode-'+cell.nom);
        if(pre&&pre.dataset.charge)return;
        try{
          const rc=await fetch('/savoir/evolution/cellules/'+encodeURIComponent(cell.nom));
          const dc=await rc.json();
          if(pre){pre.textContent=dc.code||'(code indisponible)';pre.dataset.charge='1';}
        }catch(e){if(pre)pre.textContent='Erreur de chargement';}
      });
      el.appendChild(det);
      c.appendChild(el);
    }
  }catch(e){}
}

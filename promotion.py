"""
VIVARIUM - Promotion : un produit validE devient une appli web responsive

A partir du contrat (schema d'entree) d'un produit promu, on genere une page HTML
autonome, mobile-first, qui :
  - construit un formulaire derive du schema (texte / nombre / booleen / liste d'objets),
  - pre-remplit avec l'exemple du contrat,
  - envoie les donnees a POST /produits/{id}/executer et affiche le resultat.

Une seule page generique, pilotee par le schema injecte : marche pour n'importe quel
produit promu. Design aligne sur ui.py (sombre, accent menthe), cibles tactiles >= 44px.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import json

_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITRE__ - VIVARIUM</title>
<style>
  :root { --bg:#0a0e14; --panel:#121821; --line:#1f2a3a; --txt:#e6edf3; --mut:#8b98a9;
          --acc:#4fd1c5; --ok:#3fb950; --ko:#f85149; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:16px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  .wrap { max-width:680px; margin:0 auto; padding:20px 16px 64px; }
  header h1 { margin:0; font-size:20px; letter-spacing:1px; }
  header h1 b { color:var(--acc); }
  header p { color:var(--mut); font-size:14px; margin:6px 0 0; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:14px;
           padding:16px; margin-top:18px; }
  label.champ { display:block; margin:14px 0 6px; font-size:14px; color:var(--txt); }
  input[type=text], input[type=number] { width:100%; min-height:44px; background:#0d131c;
           color:var(--txt); border:1px solid var(--line); border-radius:10px; padding:10px 12px;
           font-size:16px; }
  .switch { display:flex; align-items:center; gap:10px; min-height:44px; }
  .switch input { width:22px; height:22px; }
  .liste-item { border:1px solid var(--line); border-radius:10px; padding:12px; margin:10px 0;
                position:relative; }
  .liste-item .sup { position:absolute; top:8px; right:10px; color:var(--ko); cursor:pointer;
                     background:none; border:0; font-size:20px; min-height:32px; }
  .mini { font-size:12px; color:var(--mut); margin:2px 0 6px; }
  button.act { width:100%; min-height:50px; background:var(--acc); color:#06231f; border:0;
               border-radius:12px; font-size:17px; font-weight:700; cursor:pointer; margin-top:10px; }
  button.ghost { background:transparent; color:var(--acc); border:1px dashed var(--acc);
                 border-radius:10px; min-height:44px; width:100%; cursor:pointer; }
  button:disabled { opacity:.5; }
  #resultat { margin-top:16px; }
  .tag { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:700; }
  .tag.ok { background:rgba(63,185,80,.15); color:var(--ok); }
  .tag.ko { background:rgba(248,81,73,.15); color:var(--ko); }
  pre { background:#0d131c; border:1px solid var(--line); border-radius:10px; padding:14px;
        overflow:auto; font:13px/1.5 ui-monospace,Consolas,monospace; color:#c9d6e3; white-space:pre-wrap;
        word-break:break-word; }
  .footer { color:var(--mut); font-size:12px; text-align:center; margin-top:22px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>VIVA<b>RIUM</b></h1>
    <p>__DESCRIPTION__</p>
  </header>
  <div class="panel"><form id="form"></form>
    <button class="act" id="go">Lancer</button>
  </div>
  <div id="resultat"></div>
  <div class="footer">Genere et gouverne par VIVARIUM. Execute en bac a sable isole.</div>
</div>
<script>
const SCHEMA = __SCHEMA__;
const EXEMPLE = __EXEMPLE__;
const PRODUIT_ID = "__PRODUIT_ID__";
const $ = s => document.querySelector(s);

function champInput(c, valeur) {
  if (c.type === 'booleen') {
    const w = document.createElement('div'); w.className = 'switch';
    const i = document.createElement('input'); i.type='checkbox'; i.dataset.nom=c.nom;
    i.checked = !!valeur;
    const l = document.createElement('span'); l.textContent = c.label;
    w.append(i, l); return w;
  }
  const i = document.createElement('input');
  i.type = (c.type === 'nombre') ? 'number' : 'text';
  if (c.type === 'nombre') i.step = 'any';
  i.dataset.nom = c.nom; if (valeur !== undefined && valeur !== null) i.value = valeur;
  return i;
}

function renderListe(c, valeurs) {
  const cont = document.createElement('div'); cont.dataset.liste = c.nom;
  const titre = document.createElement('label'); titre.className='champ'; titre.textContent=c.label;
  cont.appendChild(titre);
  const items = document.createElement('div'); items.className='items'; cont.appendChild(items);
  function ajouter(val) {
    const it = document.createElement('div'); it.className='liste-item';
    const sup = document.createElement('button'); sup.className='sup'; sup.type='button'; sup.textContent='x';
    sup.onclick = () => it.remove(); it.appendChild(sup);
    (c.sous_champs||[]).forEach(sc => {
      const lab = document.createElement('div'); lab.className='mini'; lab.textContent=sc.label;
      it.appendChild(lab);
      it.appendChild(champInput(sc, val ? val[sc.nom] : undefined));
    });
    items.appendChild(it);
  }
  (valeurs && valeurs.length ? valeurs : [null]).forEach(ajouter);
  const add = document.createElement('button'); add.className='ghost'; add.type='button';
  add.textContent='+ ajouter'; add.onclick = () => ajouter(null); cont.appendChild(add);
  return cont;
}

function build() {
  const f = $('#form');
  SCHEMA.champs.forEach(c => {
    if (c.type === 'liste') { f.appendChild(renderListe(c, EXEMPLE[c.nom])); return; }
    const l = document.createElement('label'); l.className='champ'; l.textContent=c.label;
    f.appendChild(l); f.appendChild(champInput(c, EXEMPLE[c.nom]));
  });
}

function lireInput(el) {
  if (el.type === 'checkbox') return el.checked;
  if (el.type === 'number') return el.value === '' ? null : parseFloat(el.value);
  return el.value;
}

function collecte() {
  const d = {};
  SCHEMA.champs.forEach(c => {
    if (c.type === 'liste') {
      const cont = document.querySelector('[data-liste="'+c.nom+'"] .items');
      d[c.nom] = [...cont.children].map(it => {
        const o = {};
        (c.sous_champs||[]).forEach(sc => {
          const el = it.querySelector('[data-nom="'+sc.nom+'"]'); if (el) o[sc.nom] = lireInput(el);
        });
        return o;
      });
    } else {
      const el = document.querySelector('#form > [data-nom="'+c.nom+'"]');
      if (el) d[c.nom] = lireInput(el);
    }
  });
  return d;
}

function renduResultat(r) {
  if (!r.ok) return '<div class="panel"><span class="tag ko">erreur</span> ' +
    (r.erreur||r.detail||'').toString().replace(/[<>]/g,'') + '</div>';
  return '<div class="panel"><span class="tag ok">resultat</span><pre>' +
    JSON.stringify(r.resultat, null, 2).replace(/[<>]/g,'') + '</pre></div>';
}

$('#go').onclick = async () => {
  $('#go').disabled = true;
  $('#resultat').innerHTML = '<div class="panel">Calcul en cours dans le bac a sable...</div>';
  try {
    const rep = await fetch('/produits/' + encodeURIComponent(PRODUIT_ID) + '/executer', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({donnees: collecte()})
    });
    $('#resultat').innerHTML = renduResultat(await rep.json());
  } catch(e) { $('#resultat').innerHTML = '<div class="panel"><span class="tag ko">erreur</span> ' + e + '</div>'; }
  finally { $('#go').disabled = false; }
};

build();
</script>
</body>
</html>
"""


def page_app(produit_id: str, contrat: dict) -> str:
    """Genere la page web responsive d'un produit promu, pilotee par son schema."""
    description = (contrat.get("description") or "Outil genere par VIVARIUM").replace("<", "").replace(">", "")
    titre = description[:40]
    return (_TEMPLATE
            .replace("__SCHEMA__", json.dumps({"champs": contrat.get("champs", [])}, ensure_ascii=False))
            .replace("__EXEMPLE__", json.dumps(contrat.get("exemple", {}), ensure_ascii=False))
            .replace("__PRODUIT_ID__", produit_id)
            .replace("__DESCRIPTION__", description)
            .replace("__TITRE__", titre))

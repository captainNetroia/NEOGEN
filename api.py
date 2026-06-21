"""
NEOGEN - Service FastAPI : l'organisme devient exploitable

Expose le pipeline reel de production derriere une API HTTP :
  POST /fabriquer      intention -> produit gouverne, execute en conteneur
  GET  /produits       liste les produits persistes au registre
  GET  /produits/{id}  recharge le code d'un produit
  GET  /health         etat du service + disponibilite Docker

MODELE DE CONFIANCE (assume) :
  - CE service est notre code (de confiance) : il a le droit de piloter Docker
    pour creer des bacs a sable.
  - le code GENERE par l'IA (non fiable) ne touche JAMAIS au demon Docker : il
    tourne dans un conteneur durci (--network none, --cap-drop ALL, non-root,
    ressources bornees) via executeur_conteneur.
  - en conteneur, ce service monte le socket Docker (sibling containers) -> il a
    un controle root-equivalent du Docker hote. ACCEPTABLE seulement sur une
    MACHINE DEDIEE. JAMAIS sur le VPS de production (netroia.tech + n8n).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations

import hashlib as _hl
import json as _json
import os as _os
import secrets as _sec
import uuid as _uid
from datetime import datetime as _dt, timedelta as _td

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import registre
import rpa
from capacites import Capacites
from executeur_conteneur import docker_disponible
from pipeline import fabriquer_reel
from ui import PAGE

app = FastAPI(
    title="NEOGEN",
    description="Une intention parlee devient une application gouvernee, generee et executee en conteneur durci.",
    version="5.0",
)

# CORS resserre : par defaut localhost uniquement. En prod, definir NEOGEN_CORS_ORIGINS
# (liste separee par des virgules) pour autoriser les domaines qui appellent l'API.
_cors_env = _os.environ.get("NEOGEN_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or [
    "http://localhost:8000", "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _exiger_byok(ctx) -> None:
    """BYOK (Bring Your Own Key) : refuse d'utiliser la cle par defaut (credentials du
    proprietaire) pour les appels LLM. Autorise si : une cle client est fournie, OU
    provider 'local' (Ollama self-host, gratuit), OU NEOGEN_ALLOW_DEFAULT_KEY active
    (dev local du proprietaire). Sinon 402 avec message clair.
    => en distribution publique, jamais les credits du proprietaire."""
    if _os.environ.get("NEOGEN_ALLOW_DEFAULT_KEY", "").strip().lower() in ("1", "true", "yes", "on"):
        return
    if ctx is not None and (ctx.api_key or (ctx.provider or "").lower() == "local"):
        return
    raise HTTPException(status_code=402, detail=(
        "Connecte ton modele IA dans Integrations (ta cle API, ou Ollama en local) pour "
        "utiliser les agents et la creation. NEOGEN n'utilise jamais une cle par defaut."
    ))



class DemandeFabrication(BaseModel):
    intention: str = Field(min_length=3, max_length=2000,
                           description="ce que le produit doit faire, en langage naturel")
    reparer: bool = Field(default=True, description="auto-reparation sur echec d'execution")
    max_tentatives: int = Field(default=3, ge=1, le=5)
    juger: bool = Field(default=False, description="mode juge : genere 2 strategies, garde la meilleure")
    # Capacites accordees au produit (Niveau 2). Vide = produit pur (calcul en memoire).
    persistance: bool = Field(default=False, description="accorde un espace disque isole (volume dedie)")
    reseau: bool = Field(default=False, description="accorde une sortie reseau vers une liste blanche")
    domaines_autorises: list[str] = Field(default_factory=list, description="liste blanche si reseau accorde")


class ReponseFabrication(BaseModel):
    succes: bool
    verdict: str
    tentatives: int
    lignes: int
    lecons: list[str]
    produit_id: str | None = None
    capacites: str = "aucune"
    classement: list = []


@app.get("/", response_class=HTMLResponse)
def racine():
    """Page humaine de l'organisme : decrire une intention, voir le produit + le catalogue."""
    return PAGE


@app.get("/info")
def info():
    return {
        "service": "NEOGEN",
        "version": "5.0",
        "endpoints": ["/ (UI)", "/fabriquer (POST)", "/produits", "/produits/{id}", "/health", "/info"],
    }


@app.get("/health")
def health():
    ok, info = docker_disponible()
    return {
        "status": "ok",
        "docker": ok,
        "docker_info": info,
        "note": "sans Docker, l'execution du code genere retombe sur l'isolation processus (moins sure)",
    }


class DemandeProposition(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)


def _llm_client(provider=None, model=None, key=None, base=None, tier="fort"):
    """Construit le client LLM depuis les en-tetes X-LLM-* (gateway multi-provider).
    Aucune cle persistee : elle vit le temps de la requete. Provider absent => Anthropic defaut."""
    from gateway import client as _gw, contexte_depuis_headers
    ctx = contexte_depuis_headers(provider, model, key, base)
    _exiger_byok(ctx)
    return _gw(ctx, tier=tier)


@app.post("/conseil")
def conseil_endpoint(demande: DemandeProposition,
                     x_llm_provider: str | None = Header(default=None),
                     x_llm_model: str | None = Header(default=None),
                     x_llm_key: str | None = Header(default=None),
                     x_llm_base: str | None = Header(default=None)):
    """Conseiller : note de conformite (indicative) + cadrage analytique pour une intention."""
    from sanitizer import nettoyer
    from conseillers import conseiller
    try:
        cl = _llm_client(x_llm_provider, x_llm_model, x_llm_key, x_llm_base, tier="leger")
        c = conseiller(demande.intention, cl)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=nettoyer(f"echec du conseil : {e}"))
    return c.model_dump()


@app.post("/proposer")
def proposer_endpoint(demande: DemandeProposition,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
    """L'organisme juge l'intention et PROPOSE murs + capacites. L'humain validera."""
    from sanitizer import nettoyer
    from proposer import proposer
    try:
        cl = _llm_client(x_llm_provider, x_llm_model, x_llm_key, x_llm_base, tier="fort")
        p = proposer(demande.intention, cl)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=nettoyer(f"echec de la proposition : {e}"))
    return p.model_dump()


@app.post("/fabriquer", response_model=ReponseFabrication)
def fabriquer_endpoint(demande: DemandeFabrication,
                       x_llm_provider: str | None = Header(default=None),
                       x_llm_model: str | None = Header(default=None),
                       x_llm_key: str | None = Header(default=None),
                       x_llm_base: str | None = Header(default=None)):
    """Transforme une intention en produit : ADN -> code -> 3 garde-fous -> conteneur -> registre."""
    from sanitizer import nettoyer
    cap = Capacites(
        persistance=demande.persistance,
        reseau=demande.reseau,
        domaines_autorises=demande.domaines_autorises,
    )
    try:
        cl = _llm_client(x_llm_provider, x_llm_model, x_llm_key, x_llm_base, tier="fort")
        if demande.juger:
            from pipeline import fabriquer_juge_reel
            r = fabriquer_juge_reel(
                demande.intention, reparer=demande.reparer,
                max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap, client=cl,
            )
        else:
            r = fabriquer_reel(
                demande.intention, reparer=demande.reparer,
                max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap, client=cl,
            )
    except HTTPException:
        raise
    except Exception as e:  # cle API manquante, panne reseau, provider injoignable, etc.
        raise HTTPException(status_code=502, detail=nettoyer(f"echec de fabrication : {e}"))

    produit_id = None
    if r.succes:
        entrees = registre.lister()
        if entrees:
            produit_id = entrees[-1]["id"]

    return ReponseFabrication(
        succes=r.succes, verdict=r.verdict, tentatives=r.tentatives,
        lignes=r.lignes, lecons=r.lecons, produit_id=produit_id,
        capacites=cap.resume(), classement=getattr(r, "classement", []) or [],
    )


@app.get("/produits")
def lister_produits():
    """Catalogue des produits qui ont passe les garde-fous et tourne."""
    items = registre.lister()
    for item in items:
        item["promu"] = registre.est_promu(item["id"])
    return {"produits": items}


@app.get("/produits/{produit_id}/telecharger")
def telecharger_produit(produit_id: str):
    """Telecharge un pack ZIP du produit (main.py + README.md) pour migration ou archivage."""
    import io
    import zipfile
    code = registre.charger(produit_id)
    if code is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    entrees = [e for e in registre.lister() if e["id"] == produit_id]
    meta = entrees[0] if entrees else {}
    readme = (
        f"# NEOGEN — {meta.get('intention', produit_id)}\n\n"
        f"Produit ID : {produit_id}\n"
        f"Generation  : {meta.get('generation', 1)}\n"
        f"Lignes      : {meta.get('lignes', '?')}\n"
        f"Verdict     : {meta.get('verdict', '')}\n"
        f"Timestamp   : {meta.get('timestamp', '')}\n\n"
        f"## Lancement\n\n```bash\npython main.py\n```\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", code)
        zf.writestr("README.md", readme)
    buf.seek(0)
    safe_id = produit_id[:12].replace("/", "_")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="neogen-{safe_id}.zip"'},
    )


@app.get("/produits/{produit_id}")
def obtenir_produit(produit_id: str):
    code = registre.charger(produit_id)
    if code is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    return {"id": produit_id, "code": code, "promu": registre.est_promu(produit_id),
            "contrat": registre.charger_contrat(produit_id)}


# ── Genealogie (Phase 4) : arbre des generations, diff, revert, upgrade ────────

@app.get("/produits/{produit_id}/generations")
def generations_produit(produit_id: str):
    """Arbre de la lignee : toutes les generations + version active + diff vs generation precedente."""
    lignee = registre.lignee_produit(produit_id)
    if not lignee:
        raise HTTPException(status_code=404, detail="produit introuvable")
    lineage = lignee[0].get("lineage")
    actif = registre.actif_de(lineage) or lignee[-1]["id"]
    noeuds = []
    precedent = None
    for e in lignee:
        delta = None
        if precedent is not None:
            d = registre.diff_codes(precedent["id"], e["id"])
            delta = {"ajouts": d["ajouts"], "retraits": d["retraits"],
                     "lignes_delta": d["lignes_b"] - d["lignes_a"]}
        gov = None
        if precedent is not None:
            gov = registre.diff_gouvernance(precedent["id"], e["id"])
        noeuds.append({
            "id": e["id"], "generation": e.get("generation", 1),
            "parent_id": e.get("parent_id"), "timestamp": e.get("timestamp"),
            "verdict": e.get("verdict"), "lignes": e.get("lignes"),
            "murs": e.get("murs", []), "capacites": e.get("capacites", []),
            "promu": registre.est_promu(e["id"]), "actif": e["id"] == actif,
            "delta": delta, "gouvernance": gov,
        })
        precedent = e
    return {"lineage": lineage, "intention": lignee[-1].get("intention"),
            "actif": actif, "total": len(noeuds), "generations": noeuds}


@app.get("/produits/{produit_id}/diff")
def diff_produit(produit_id: str, vs: str | None = None):
    """Diff unifie entre produit_id et 'vs' (defaut : sa generation parente)."""
    lignee = registre.lignee_produit(produit_id)
    if not lignee:
        raise HTTPException(status_code=404, detail="produit introuvable")
    cible = next((e for e in lignee if e["id"] == produit_id), None)
    base = vs or (cible.get("parent_id") if cible else None)
    if not base:
        return {"ajouts": 0, "retraits": 0, "lignes_a": 0,
                "lignes_b": (cible or {}).get("lignes", 0),
                "diff": "(generation d'origine : aucune generation precedente a comparer)"}
    return registre.diff_codes(base, produit_id)


@app.post("/produits/{produit_id}/revert")
def revert_produit(produit_id: str):
    """Revenir a une ancienne generation : la marque comme version active de la lignee.
    Ne supprime rien (les generations restent tracees) ; change juste le pointeur courant."""
    lignee = registre.lignee_produit(produit_id)
    if not lignee:
        raise HTTPException(status_code=404, detail="produit introuvable")
    lineage = lignee[0].get("lineage")
    registre.definir_actif(lineage, produit_id)
    return {"ok": True, "lineage": lineage, "actif": produit_id}


class DemandeUpgrade(BaseModel):
    intention: str | None = Field(default=None, description="nouvelle intention (defaut : celle du parent)")
    reparer: bool = True
    max_tentatives: int = Field(default=3, ge=1, le=5)
    persistance: bool = False
    reseau: bool = False
    domaines_autorises: list[str] = Field(default_factory=list)


@app.post("/produits/{produit_id}/upgrade")
def upgrade_produit(produit_id: str, demande: DemandeUpgrade,
                    x_llm_provider: str | None = Header(default=None),
                    x_llm_model: str | None = Header(default=None),
                    x_llm_key: str | None = Header(default=None),
                    x_llm_base: str | None = Header(default=None)):
    """Faire EVOLUER un produit en streaming SSE : re-fabrique une nouvelle generation
    de sa lignee sous gouvernance complete. Diffuse chaque stade en temps reel."""
    import queue
    import threading
    from sanitizer import nettoyer
    from gateway import contexte_depuis_headers, resume_ctx

    base = next((e for e in registre.lister() if e["id"] == produit_id), None)
    if base is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    intention = (demande.intention or base.get("intention") or "").strip()
    if len(intention) < 3:
        raise HTTPException(status_code=400, detail="intention trop courte")

    cap = Capacites(persistance=demande.persistance, reseau=demande.reseau,
                    domaines_autorises=demande.domaines_autorises)
    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _moteur = resume_ctx(_ctx)

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def progress(evt: dict):
        safe = {}
        for k, v in evt.items():
            safe[k] = nettoyer(v) if isinstance(v, str) else v
        file_evts.put(safe)

    def travailler():
        try:
            from gateway import client as _gw
            cl = _gw(_ctx, tier="fort")
            file_evts.put({"stade": "moteur", "msg": nettoyer(_moteur)})
            r = fabriquer_reel(intention, reparer=demande.reparer,
                               max_tentatives=demande.max_tentatives, enregistrer=True,
                               cap=cap, client=cl, parent_id=produit_id, progress=progress)
            nouveau = None
            if r.succes:
                entrees = registre.lister()
                if entrees:
                    nouveau = entrees[-1]["id"]
            file_evts.put({
                "stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                "tentatives": r.tentatives, "lignes": r.lignes,
                "produit_id": nouveau, "parent_id": produit_id,
                "lecons": [nettoyer(l) for l in (r.lecons or [])],
            })
        except Exception as e:
            file_evts.put({"stade": "erreur", "message": nettoyer(str(e))})
        finally:
            file_evts.put(_SENTINEL)

    threading.Thread(target=travailler, daemon=True).start()

    def flux():
        while True:
            evt = file_evts.get()
            if evt is _SENTINEL:
                break
            yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class DemandeExecution(BaseModel):
    donnees: dict = Field(default_factory=dict, description="les vraies donnees d'entree du produit")


@app.post("/produits/{produit_id}/promouvoir")
def promouvoir_endpoint(produit_id: str):
    """Validation humaine : promeut un produit (avec contrat) en appli web utilisable."""
    contrat = registre.charger_contrat(produit_id)
    if contrat is None:
        raise HTTPException(status_code=400, detail="produit non promouvable (aucun contrat d'entree)")
    registre.promouvoir(produit_id)
    return {"promu": True, "app": f"/produits/{produit_id}/app"}


@app.post("/produits/{produit_id}/executer")
def executer_produit(produit_id: str, demande: DemandeExecution):
    """Execute un produit PROMU sur de vraies donnees, en bac a sable."""
    if not registre.est_promu(produit_id):
        raise HTTPException(status_code=403, detail="produit non promu (validation humaine requise)")
    code = registre.charger(produit_id)
    if code is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    contrat = registre.charger_contrat(produit_id)
    if contrat:
        from contrat import ContratProduit, valider_entree
        erreurs = valider_entree(ContratProduit(**contrat), demande.donnees)
        if erreurs:
            raise HTTPException(status_code=422, detail={"erreurs": erreurs})
            
    meta = next((e for e in registre.lister() if e["id"] == produit_id), {})
    caps_list = meta.get("capacites", [])
    cap = Capacites(
        persistance="persistance" in caps_list,
        reseau="reseau" in caps_list,
        bureau="bureau" in caps_list,
        domaines_autorises=meta.get("domaines_autorises", []),
    )
    volume_nom = ("viv_" + registre._slug(meta.get("intention", ""))) if cap.persistance else None
    
    from executeur_conteneur import executer_avec_entree
    return executer_avec_entree(code, demande.donnees, cap=cap, volume_nom=volume_nom)


@app.get("/produits/{produit_id}/app", response_class=HTMLResponse)
def app_produit(produit_id: str):
    """Sert l'appli web responsive d'un produit promu (formulaire -> resultat)."""
    if not registre.est_promu(produit_id):
        raise HTTPException(status_code=404, detail="produit non promu")
    contrat = registre.charger_contrat(produit_id)
    if contrat is None:
        raise HTTPException(status_code=404, detail="aucun contrat")
    from promotion import page_app
    return page_app(produit_id, contrat)


# ── Studio A→Z : composition d'ADN + forge en streaming ───────────────────────

class DemandeComposition(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)
    murs: list[str] = Field(default_factory=list, description="cles de murs retenus par l'humain")
    persistance: bool = False
    reseau: bool = False
    domaines_autorises: list[str] = Field(default_factory=list)
    juger: bool = False


@app.post("/composer")
def composer_endpoint(demande: DemandeComposition,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
    """Etape 2 du studio : recap lisible de l'ADN compose + ce que fera la 1ere generation."""
    from compositeur import REGLES_MURS
    from capacites import CATALOGUE_CAPACITES

    murs_expliques = [{"cle": m, "explication": REGLES_MURS.get(m, m)} for m in demande.murs]
    capacites = []
    if demande.persistance:
        capacites.append({"cle": "persistance", "explication": CATALOGUE_CAPACITES["persistance"]})
    if demande.reseau:
        dom = ", ".join(demande.domaines_autorises) or "(liste blanche a preciser)"
        capacites.append({"cle": "reseau", "explication": CATALOGUE_CAPACITES["reseau"] + f" Domaines : {dom}."})

    # Description de la premiere generation : un appel LLM court (tier leger).
    try:
        from sanitizer import nettoyer
        client = _llm_client(x_llm_provider, x_llm_model, x_llm_key, x_llm_base, tier="leger")
        contexte = (
            f"Intention : {demande.intention}\n"
            f"Murs retenus : {', '.join(demande.murs) or 'aucun'}\n"
            f"Capacites : {', '.join(c['cle'] for c in capacites) or 'aucune (produit pur)'}\n"
            f"Mode juge : {'oui' if demande.juger else 'non'}"
        )
        resp = client.messages.create(
            max_tokens=400,
            system=("Tu es NEOGEN. En 2 a 3 phrases simples et concretes, decris ce que fera "
                    "l'application des sa PREMIERE generation, compte tenu de l'intention, des murs "
                    "et des capacites. Pas de jargon, pas de promesse exageree. Phrase directe."),
            messages=[{"role": "user", "content": contexte}],
        )
        description = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        description = nettoyer(f"(apercu indisponible : {e})")

    return {
        "objectif": demande.intention,
        "murs": murs_expliques,
        "capacites": capacites,
        "mode_juge": demande.juger,
        "description_premiere_generation": description,
    }


@app.post("/fabriquer/stream")
def fabriquer_stream(demande: DemandeFabrication,
                     x_llm_provider: str | None = Header(default=None),
                     x_llm_model: str | None = Header(default=None),
                     x_llm_key: str | None = Header(default=None),
                     x_llm_base: str | None = Header(default=None)):
    """Etape 4 du studio : forge le produit en diffusant chaque stade en Server-Sent Events."""
    import queue
    import threading
    from sanitizer import nettoyer
    from capacites import Capacites
    from gateway import contexte_depuis_headers, resume_ctx

    cap = Capacites(
        persistance=demande.persistance,
        reseau=demande.reseau,
        domaines_autorises=demande.domaines_autorises,
    )
    # Resolution du provider/modele PAR REQUETE (cle jamais persistee ni loggee).
    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _moteur = resume_ctx(_ctx)

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def progress(evt: dict):
        # Sanitize tout champ texte avant diffusion (zero secret dans le flux).
        safe = {}
        for k, v in evt.items():
            safe[k] = nettoyer(v) if isinstance(v, str) else v
        file_evts.put(safe)

    def travailler():
        try:
            from gateway import client as _gw
            cl = _gw(_ctx, tier="fort")
            file_evts.put({"stade": "moteur", "msg": nettoyer(_moteur)})
            if demande.juger:
                from pipeline import fabriquer_juge_reel
                r = fabriquer_juge_reel(
                    demande.intention, reparer=demande.reparer,
                    max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap,
                    progress=progress, client=cl,
                )
            else:
                from pipeline import fabriquer_reel
                r = fabriquer_reel(
                    demande.intention, reparer=demande.reparer,
                    max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap,
                    progress=progress, client=cl,
                )
            produit_id = None
            if r.succes:
                entrees = registre.lister()
                if entrees:
                    produit_id = entrees[-1]["id"]
            file_evts.put({
                "stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                "tentatives": r.tentatives, "lignes": r.lignes, "produit_id": produit_id,
                "capacites": cap.resume(),
                "classement": getattr(r, "classement", []) or [],
                "lecons": [nettoyer(l) for l in (r.lecons or [])],
            })
        except Exception as e:
            file_evts.put({"stade": "erreur", "message": nettoyer(str(e))})
        finally:
            file_evts.put(_SENTINEL)

    threading.Thread(target=travailler, daemon=True).start()

    def flux():
        while True:
            evt = file_evts.get()
            if evt is _SENTINEL:
                break
            yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/orchestrer/stream")
def orchestrer_stream(demande: DemandeFabrication,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
    """Mode delegation : decompose l'intention en organes, delegue chaque organe a un
    sous-agent au tier adapte, assemble sous gouvernance. Diffuse chaque etape en SSE."""
    import queue
    import threading
    from sanitizer import nettoyer
    from capacites import Capacites
    from gateway import contexte_depuis_headers, resume_ctx

    cap = Capacites(
        persistance=demande.persistance,
        reseau=demande.reseau,
        domaines_autorises=demande.domaines_autorises,
    )
    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _moteur = resume_ctx(_ctx)

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def progress(evt: dict):
        safe = {}
        for k, v in evt.items():
            safe[k] = nettoyer(v) if isinstance(v, str) else v
        file_evts.put(safe)

    def travailler():
        try:
            from orchestrateur import orchestrer
            file_evts.put({"stade": "moteur", "msg": nettoyer(_moteur)})
            r = orchestrer(
                demande.intention, ctx=_ctx, cap=cap, reparer=demande.reparer,
                max_tentatives=demande.max_tentatives, enregistrer=True, progress=progress,
            )
            produit_id = None
            if r.succes:
                entrees = registre.lister()
                if entrees:
                    produit_id = entrees[-1]["id"]
            file_evts.put({
                "stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                "tentatives": r.tentatives, "lignes": r.lignes, "produit_id": produit_id,
                "capacites": cap.resume(),
                "plan": getattr(r, "plan", []) or [],
                "lecons": [nettoyer(l) for l in (r.lecons or [])],
            })
        except Exception as e:
            file_evts.put({"stade": "erreur", "message": nettoyer(str(e))})
        finally:
            file_evts.put(_SENTINEL)

    threading.Thread(target=travailler, daemon=True).start()

    def flux():
        while True:
            evt = file_evts.get()
            if evt is _SENTINEL:
                break
            yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Agents conversationnels (Cerveau + Forgeron + Genealogiste + Secretaire) ──

class MessageChat(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class DemandeChat(BaseModel):
    message: str
    historique: list[MessageChat] = Field(default_factory=list)


@app.get("/agents")
def lister_agents():
    """Expose les profils d'agents (titre + role) pour l'UI."""
    from agent_core import PROFILS
    return {"agents": {k: {"titre": v["titre"], "outils": v["outils"],
                           "delegue": v.get("delegue", False)} for k, v in PROFILS.items()}}


@app.post("/agent/{role}/chat/stream")
def agent_chat_stream(role: str, demande: DemandeChat,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
    """Dialogue avec un agent : il reflechit, appelle des outils, repond. Flux SSE."""
    import queue
    import threading
    from sanitizer import nettoyer
    from gateway import contexte_depuis_headers
    from agent_core import dialoguer, PROFILS

    if role not in PROFILS:
        raise HTTPException(status_code=404, detail=f"agent inconnu : {role}")

    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    hist = [{"role": m.role, "content": m.content} for m in demande.historique]

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def emit(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            dialoguer(role, demande.message, historique=hist, ctx=_ctx, emit=emit)
        except Exception as e:
            file_evts.put({"type": "erreur", "message": nettoyer(str(e))})
        finally:
            file_evts.put(_SENTINEL)

    threading.Thread(target=travailler, daemon=True).start()

    def flux():
        while True:
            evt = file_evts.get()
            if evt is _SENTINEL:
                break
            yield f"data: {_json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(flux(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Auth & Feedback ───────────────────────────────────────────────────────────

_BASE = _os.path.dirname(_os.path.abspath(__file__))
_DATA = _os.path.join(_BASE, "data")
_USERS = _os.path.join(_DATA, "users.jsonl")
_SESSIONS = _os.path.join(_DATA, "sessions.jsonl")
_FEEDBACKS = _os.path.join(_DATA, "feedbacks.jsonl")
# Admin : defini par l'exploitant de l'instance via NEOGEN_ADMIN_EMAIL.
# Vide par defaut => aucun admin pre-cable (chaque deploiement choisit le sien).
_ADMIN_EMAIL = _os.environ.get("NEOGEN_ADMIN_EMAIL", "").strip().lower()


def _est_admin(user) -> bool:
    """True seulement si un admin est configure ET correspond a l'utilisateur.
    Si NEOGEN_ADMIN_EMAIL n'est pas defini, PERSONNE n'est admin (fail-closed)."""
    if not _ADMIN_EMAIL or not user:
        return False
    return (user.get("email") or "").strip().lower() == _ADMIN_EMAIL


def _rjsonl(path: str) -> list:
    if not _os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(_json.loads(line))
                except Exception:
                    pass
    return out


def _ajsonl(path: str, obj: dict) -> None:
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(_json.dumps(obj, ensure_ascii=False) + "\n")


def _wjsonl(path: str, items: list) -> None:
    _os.makedirs(_os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(_json.dumps(it, ensure_ascii=False) + "\n")


def _hashpw(pw: str) -> str:
    salt = _sec.token_hex(16)
    k = _hl.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000)
    return f"pbkdf2:{salt}:{k.hex()}"


def _verifypw(pw: str, h: str) -> bool:
    try:
        _, salt, key = h.split(":")
        k = _hl.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000)
        return _sec.compare_digest(k.hex(), key)
    except Exception:
        return False


def _user_by_email(email: str) -> dict | None:
    for u in _rjsonl(_USERS):
        if u.get("email") == email:
            return u
    return None


def _user_by_token(token: str) -> dict | None:
    now = _dt.utcnow().isoformat()
    for s in _rjsonl(_SESSIONS):
        if s.get("token") == token and s.get("expires_at", "") > now:
            uid = s.get("user_id")
            for u in _rjsonl(_USERS):
                if u.get("id") == uid:
                    return u
    return None


def _make_session(user_id: str) -> str:
    token = _sec.token_urlsafe(32)
    exp = (_dt.utcnow() + _td(days=30)).isoformat()
    _ajsonl(_SESSIONS, {"token": token, "user_id": user_id,
                        "expires_at": exp, "created_at": _dt.utcnow().isoformat()})
    return token


def _auth(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    return _user_by_token(authorization.replace("Bearer ", "").strip())


@app.post("/auth/register")
def auth_register(data: dict):
    email = data.get("email", "").strip().lower()
    pw = data.get("password", "")
    name = data.get("name", "").strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email invalide")
    if len(pw) < 6:
        raise HTTPException(400, "Mot de passe trop court (6 caracteres minimum)")
    if _user_by_email(email):
        raise HTTPException(409, "Email deja utilise")
    uid = str(_uid.uuid4())
    user = {
        "id": uid, "email": email,
        "name": name or email.split("@")[0],
        "pw_hash": _hashpw(pw),
        "created_at": _dt.utcnow().isoformat(),
    }
    _ajsonl(_USERS, user)
    token = _make_session(uid)
    return {"token": token, "user": {"id": uid, "email": email, "name": user["name"]}}


@app.post("/auth/login")
def auth_login(data: dict):
    email = data.get("email", "").strip().lower()
    pw = data.get("password", "")
    user = _user_by_email(email)
    if not user or not _verifypw(pw, user.get("pw_hash", "")):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    token = _make_session(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/auth/me")
def auth_me(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    return {
        "id": user["id"], "email": user["email"],
        "name": user["name"], "created_at": user.get("created_at"),
        "is_admin": _est_admin(user),
    }


@app.post("/auth/logout")
def auth_logout(authorization: str = Header(None)):
    if not authorization:
        return {"ok": True}
    token = authorization.replace("Bearer ", "").strip()
    _wjsonl(_SESSIONS, [s for s in _rjsonl(_SESSIONS) if s.get("token") != token])
    return {"ok": True}


@app.post("/feedback")
def post_feedback(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    msg = data.get("message", "").strip()
    if not msg:
        raise HTTPException(400, "Message vide")
    fb = {
        "id": str(_uid.uuid4()),
        "user_id": user["id"] if user else None,
        "user_email": user["email"] if user else data.get("email", "anonyme"),
        "user_name": user["name"] if user else data.get("name", "Anonyme"),
        "message": msg,
        "rating": data.get("rating"),
        "created_at": _dt.utcnow().isoformat(),
    }
    _ajsonl(_FEEDBACKS, fb)
    return {"ok": True, "id": fb["id"]}


@app.get("/admin/feedbacks")
def admin_feedbacks(authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Acces refuse")
    items = _rjsonl(_FEEDBACKS)
    return {"feedbacks": list(reversed(items)), "total": len(items)}


# ── Don Stripe ────────────────────────────────────────────────────────────────

def _load_cred(filename: str, key: str) -> str:
    """Lit une valeur depuis credentials/{filename} si absent de l'env.
    Cherche dans /app/credentials (Docker) puis ../credentials (dev local)."""
    val = _os.environ.get(key, "")
    if val:
        return val
    from pathlib import Path
    candidates = [
        Path("/app/credentials") / filename,          # Docker (volume monté)
        Path(__file__).parent / "credentials" / filename,  # même dossier
        Path(__file__).parent.parent / "credentials" / filename,  # dev local
    ]
    for p in candidates:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    return ""


class DonBody(BaseModel):
    montant: int  # euros entiers, minimum 1


@app.post("/don/checkout")
def don_checkout(body: DonBody):
    """Cree une session Stripe Checkout pour un don libre (montant en euros)."""
    if body.montant < 1:
        raise HTTPException(status_code=400, detail="Montant minimum : 1 EUR")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    try:
        base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
        session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": body.montant * 100,
                    "product_data": {
                        "name": "Soutenir NEOGEN",
                        "description": "Don libre pour financer le calcul et le developpement",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{base_url}/#don?merci=1",
            cancel_url=f"{base_url}/#don",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


# ── OpenLegi / Legifrance ─────────────────────────────────────────────────────

@app.get("/integrations/status")
def integrations_status():
    """Detecte quelles integrations sont disponibles cote serveur (credentials montes)."""
    return {
        "openlegi": bool(_load_cred("openlegi.env", "OPENLEGI_TOKEN")),
        "stripe": bool(_load_cred("stripe.env", "STRIPE_SECRET_KEY")),
    }


@app.post("/openlegi/conformite")
async def openlegi_conformite(data: dict):
    """Recherche de textes legaux via OpenLegi (Legifrance MCP)."""
    import httpx
    query = (data.get("query") or "").strip()
    if not query:
        raise HTTPException(400, "query requis")
    token = _load_cred("openlegi.env", "OPENLEGI_TOKEN")
    if not token:
        raise HTTPException(503, "OpenLegi non configure (OPENLEGI_TOKEN manquant)")
    mcp_url = f"https://mcp.openlegi.fr/legifrance/mcp?token={token}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "tools/call",
                    "params": {"name": "rechercher_code", "arguments": {"query": query, "nombreResultats": 5}},
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            result = r.json()
    except Exception as e:
        raise HTTPException(502, f"OpenLegi inaccessible : {e}")
    content = result.get("result", result)
    return {"resultats": content, "query": query}


# ── Endpoints RPA & Apprentissage par imitation ───────────────────────────────

@app.post("/rpa/agent/ping")
def rpa_ping():
    rpa.ping_agent()
    return {"recording": rpa.is_recording()}


@app.get("/rpa/status")
def rpa_status():
    return {
        "connected": rpa.is_agent_connected(),
        "recording": rpa.is_recording(),
        "queue_len": len(rpa.RpaQueue.list_queue())
    }


@app.get("/rpa/pending")
def rpa_pending():
    act = rpa.RpaQueue.get_pending()
    if not act:
        raise HTTPException(status_code=404, detail="No pending actions")
    return act


class RpaResultBody(BaseModel):
    id: str
    status: str
    error: str | None = None


@app.post("/rpa/action/result")
def rpa_action_result(body: RpaResultBody):
    ok = rpa.RpaQueue.set_result(body.id, body.status, body.error)
    if not ok:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"ok": True}


@app.post("/rpa/clear")
def rpa_clear():
    count = rpa.RpaQueue.clear()
    return {"cleared": count}


class RpaExecuteBody(BaseModel):
    actions: list[dict]


@app.post("/rpa/execute")
def rpa_execute(body: RpaExecuteBody):
    ids = rpa.RpaQueue.push_multiple(body.actions)
    return {"ids": ids}


@app.post("/rpa/record/start")
def rpa_record_start():
    rpa.start_recording()
    return {"ok": True}


@app.post("/rpa/record/action")
def rpa_record_action(action: dict):
    rpa.add_recorded_action(action)
    return {"ok": True}


class RpaRecordStopBody(BaseModel):
    name: str


@app.post("/rpa/record/stop")
def rpa_record_stop(body: RpaRecordStopBody):
    rec = rpa.stop_recording(body.name)
    if not rec:
        raise HTTPException(status_code=400, detail="Recording not active")
    return rec


@app.get("/rpa/recordings")
def rpa_list_recordings():
    return {"recordings": rpa.list_recordings()}


@app.get("/rpa/recordings/{rec_id}")
def rpa_get_recording(rec_id: str):
    rec = rpa.get_recording(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return rec


class RpaUpdateRecordBody(BaseModel):
    actions: list[dict]


@app.post("/rpa/recordings/{rec_id}/update")
def rpa_update_recording(rec_id: str, body: RpaUpdateRecordBody):
    ok = rpa.update_recording(rec_id, body.actions)
    if not ok:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"ok": True}


@app.delete("/rpa/recordings/{rec_id}")
def rpa_delete_recording(rec_id: str):
    ok = rpa.delete_recording(rec_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"ok": True}


@app.post("/rpa/recordings/{rec_id}/replay")
def rpa_replay_recording(rec_id: str):
    ids = rpa.replay_recording(rec_id)
    if ids is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"ids": ids}


# ── Endpoint Déploiement Hostinger ───────────────────────────────────────────

class DeployBody(BaseModel):
    domain: str


@app.post("/produits/{produit_id}/deploy")
def deploy_produit(produit_id: str, body: DeployBody):
    """Prépare le pack de déploiement et crée une demande pour l'agent local / MCP."""
    if not registre.est_promu(produit_id):
        raise HTTPException(status_code=403, detail="produit non promu (validation humaine requise)")
    contrat = registre.charger_contrat(produit_id)
    if not contrat:
        raise HTTPException(status_code=400, detail="le produit n'a pas de contrat d'interface")
    
    from promotion import page_app
    html = page_app(produit_id, contrat)
    
    import tempfile
    import zipfile
    import shutil
    
    temp_dir = tempfile.mkdtemp(prefix="neogen_deploy_")
    try:
        index_path = _os.path.join(temp_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        archive_name = f"deploy_{produit_id}.zip"
        # On sauvegarde le zip dans data/tmp pour l'exposer
        tmp_folder = _os.path.join(_BASE, "data", "tmp")
        _os.makedirs(tmp_folder, exist_ok=True)
        archive_path = _os.path.join(tmp_folder, archive_name)
        
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(index_path, "index.html")
            
        # Écrit la demande de déploiement dans data/deploy_requests.jsonl
        req_id = str(_uid.uuid4())
        req = {
            "id": req_id,
            "produit_id": produit_id,
            "domain": body.domain.strip(),
            "archive_path": _os.path.abspath(archive_path),
            "timestamp": _dt.now().isoformat(timespec="seconds"),
            "status": "pending"
        }
        _ajsonl(_os.path.join(_BASE, "data", "deploy_requests.jsonl"), req)
        
        return {
            "success": True,
            "req_id": req_id,
            "archive_path": _os.path.abspath(archive_path),
            "message": "Pack de déploiement généré avec index.html.",
            "instructions": "Demandez à l'assistant d'exécuter le déploiement sur Hostinger pour ce domaine."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de préparation du déploiement : {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


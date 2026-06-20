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
from pydantic import BaseModel, Field

import registre
from capacites import Capacites
from executeur_conteneur import docker_disponible
from pipeline import fabriquer_reel
from ui import PAGE

app = FastAPI(
    title="NEOGEN",
    description="Une intention parlee devient une application gouvernee, generee et executee en conteneur durci.",
    version="5.0",
)


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
    return {"produits": registre.lister()}


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
    from executeur_conteneur import executer_avec_entree
    return executer_avec_entree(code, demande.donnees)


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


# ── Auth & Feedback ───────────────────────────────────────────────────────────

_BASE = _os.path.dirname(_os.path.abspath(__file__))
_DATA = _os.path.join(_BASE, "data")
_USERS = _os.path.join(_DATA, "users.jsonl")
_SESSIONS = _os.path.join(_DATA, "sessions.jsonl")
_FEEDBACKS = _os.path.join(_DATA, "feedbacks.jsonl")
_ADMIN_EMAIL = _os.environ.get("NEOGEN_ADMIN_EMAIL", "captain@netroia.com")


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
        "is_admin": user["email"] == _ADMIN_EMAIL,
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
    if not user or user.get("email") != _ADMIN_EMAIL:
        raise HTTPException(403, "Acces refuse")
    items = _rjsonl(_FEEDBACKS)
    return {"feedbacks": list(reversed(items)), "total": len(items)}

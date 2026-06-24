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
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import registre
import robustesse as _rob
import rpa
from capacites import Capacites
from executeur_conteneur import docker_disponible
from pipeline import fabriquer_reel
from ui import PAGE


@asynccontextmanager
async def _lifespan(app):
    """Démarrage : lance cron + Telegram + auto-amélioration + socle compétences.
    Chaque démarrage est protégé (jamais bloquant). Remplace on_event (déprécié, dette F005)."""
    import robustesse as _rob
    _rob.protege(lambda: __import__("planificateur").demarrer(), operation="start cron", source="startup")
    _rob.protege(lambda: __import__("passerelle_telegram").demarrer(), operation="start telegram", source="startup")
    _rob.protege(lambda: __import__("auto_amelioration").demarrer(), operation="start auto-amelioration", source="startup")
    _rob.protege(lambda: __import__("competences").assurer_socle(), operation="socle competences", source="startup")
    _rob.journaliser("NEOGEN demarre : services autonomes actifs", "info", source="startup")
    yield


app = FastAPI(
    title="NEOGEN",
    description="Une intention parlee devient une application gouvernee, generee et executee en conteneur durci.",
    version="5.0",
    lifespan=_lifespan,
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


@app.get("/telegram/statut")
def telegram_statut():
    import passerelle_telegram
    return passerelle_telegram.statut()


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


def _verifier_quota(authorization: str | None, type_: str):
    """Vérifie le quota freemium pour l'action. Renvoie (user, premium).
    Lève 402 si la limite gratuite est atteinte. Si l'utilisateur n'est pas connecté,
    on autorise (mode invité) mais sans comptage — l'UI invite à créer un compte."""
    import quotas
    user = _auth(authorization)
    if user is None:
        return None, False  # invité : pas de comptage (l'UI encourage la connexion)
    v = quotas.verifier(user, type_)
    if not v["autorise"]:
        raise HTTPException(status_code=402, detail=v["raison"])
    return user, v["premium"]



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


_MIME_RAPPORTS = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv":  "text/csv; charset=utf-8",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html; charset=utf-8",
}


@app.get("/fichiers/rapports/{nom}")
def telecharger_rapport(nom: str):
    """Télécharge un rapport généré par l'agent (DOCX, PDF, Excel, CSV)."""
    import pathlib, re
    if not re.fullmatch(r"rapport_[a-f0-9]{8}\.(docx|pdf|xlsx|csv|pptx|html)", nom):
        raise HTTPException(status_code=400, detail="nom invalide")
    p = pathlib.Path(_DATA) / "rapports" / nom
    if not p.exists():
        raise HTTPException(status_code=404, detail="rapport introuvable")
    ext = nom.rsplit(".", 1)[-1]
    media = _MIME_RAPPORTS.get(ext, "application/octet-stream")
    return FileResponse(str(p), filename=nom, media_type=media)


@app.get("/health")
def health():
    ok, info = docker_disponible()
    sortie = {
        "status": "ok",
        "docker": ok,
        "docker_info": info,
        "note": "sans Docker, l'execution du code genere retombe sur l'isolation processus (moins sure)",
    }
    # Observabilité : santé des composants de fond + statut cron + signaux récents.
    try:
        import robustesse as _rob
        sortie["sante"] = _rob.sante().get("composants", {})
        sortie["alertes_recentes"] = _rob.lire_journal(limite=10, niveau_min="alerte")
    except Exception:
        pass
    try:
        import planificateur as _pl
        sortie["cron"] = _pl.statut()
    except Exception:
        pass
    try:
        import passerelle_telegram as _tg
        sortie["telegram"] = _tg.statut()
    except Exception:
        pass
    try:
        import routeur_bandit as _rb
        sortie["routeur_bandit"] = _rb.etat()
    except Exception:
        pass
    return sortie


class DemandeProposition(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)


def _llm_client(provider=None, model=None, key=None, base=None, tier="fort"):
    """Construit le client LLM depuis les en-tetes X-LLM-* (gateway multi-provider).
    Aucune cle persistee : elle vit le temps de la requete. Provider absent => Anthropic defaut."""
    from gateway import client as _gw, contexte_depuis_headers
    ctx = contexte_depuis_headers(provider, model, key, base)
    _exiger_byok(ctx)
    return _gw(ctx, tier=tier)


@app.post("/llm/verifier")
def verifier_llm(x_llm_provider: str | None = Header(default=None),
                 x_llm_model: str | None = Header(default=None),
                 x_llm_key: str | None = Header(default=None),
                 x_llm_base: str | None = Header(default=None)):
    """Teste qu'un provider+modele+cle repond REELLEMENT (petit appel). Ne persiste rien.
    L'UI ne marque un modele 'actif' que si {ok:true}. Sinon : cle absente/invalide -> rouge."""
    from gateway import contexte_depuis_headers, client as _gw
    from sanitizer import nettoyer
    ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    if ctx is None or not (ctx.api_key or (ctx.provider or "").lower() == "local"):
        return {"ok": False, "erreur": "Cle API absente"}
    try:
        cl = _gw(ctx, tier="leger")
        cl.messages.create(system="Reponds simplement OK.",
                           messages=[{"role": "user", "content": "ping"}], max_tokens=5)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erreur": nettoyer(str(e))[:240]}


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
                     x_llm_base: str | None = Header(default=None),
                     authorization: str | None = Header(default=None)):
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
    # Quotas freemium : création (+ mode jugé si demandé).
    _user, _ = _verifier_quota(authorization, "creations")
    if demande.juger:
        _verifier_quota(authorization, "mode_juge")
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
                # Quota consommé seulement sur succès (modif incluse = 1 usage).
                if _user:
                    import quotas
                    quotas.incrementer(_user["id"], "creations")
                    if demande.juger:
                        quotas.incrementer(_user["id"], "mode_juge")
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
                      x_llm_base: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
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
    _user, _ = _verifier_quota(authorization, "creations")
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
                if _user:
                    import quotas
                    quotas.incrementer(_user["id"], "creations")
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
    image_b64: str | None = None
    image_mime: str = "image/png"
    fichier_b64: str | None = None
    fichier_nom: str = ""


@app.get("/agents")
def lister_agents():
    """Expose les profils d'agents (titre + role) pour l'UI."""
    from agent_core import PROFILS
    return {"agents": {k: {"titre": v["titre"], "outils": v["outils"],
                           "delegue": v.get("delegue", False)} for k, v in PROFILS.items()}}


@app.get("/skills")
def lister_skills():
    """Compétences (skills) auto-créées par l'agent — pour l'affichage dans l'UI."""
    import competences
    return {"skills": competences.lister()}


class SkillBody(BaseModel):
    nom: str
    description: str = ""
    instructions: str
    outils: list[str] = Field(default_factory=list)


@app.post("/skills")
def creer_skill(body: SkillBody):
    """Création manuelle d'une compétence (l'utilisateur peut aussi en forger)."""
    import competences
    s = competences.creer(body.nom, body.description, body.instructions, body.outils)
    return {"ok": True, "skill": s}


@app.delete("/skills/{nom}")
def supprimer_skill(nom: str):
    import competences
    return {"ok": competences.supprimer(nom)}


# Cache simple en mémoire pour le registry (1h pour ne pas surcharger GitHub).
_registry_cache: dict = {"ts": 0.0, "data": None}
_REGISTRY_TTL = 3600.0
_REGISTRY_URL = (
    "https://raw.githubusercontent.com/captainNetroia/VIVARIUM/main/registry/skills-community.json"
)
def _charger_registry_local() -> list[dict]:
    """Fallback : lit le fichier registry local (embarqué dans le repo)."""
    import pathlib
    p = pathlib.Path(__file__).parent / "registry" / "skills-community.json"
    if p.exists():
        import json as _json
        with open(p, encoding="utf-8") as f:
            return _json.load(f).get("skills", [])
    return []


@app.get("/skills/registry")
def skills_registry():
    """Proxy vers le registry communautaire NEOGEN (cache 1h). Fallback local si GitHub inaccessible."""
    import time, httpx as _hx
    now = time.time()
    if _registry_cache["data"] and (now - _registry_cache["ts"]) < _REGISTRY_TTL:
        return {"ok": True, "source": "cache", "skills": _registry_cache["data"]}
    try:
        resp = _hx.get(_REGISTRY_URL, timeout=10.0)
        resp.raise_for_status()
        skills = resp.json().get("skills", [])
        _registry_cache["ts"] = now
        _registry_cache["data"] = skills
        return {"ok": True, "source": "registry", "skills": skills}
    except Exception:
        if _registry_cache["data"]:
            return {"ok": True, "source": "cache_stale", "skills": _registry_cache["data"]}
        # Fallback : registry embarqué dans le repo (toujours disponible)
        skills = _charger_registry_local()
        if skills:
            _registry_cache["ts"] = now
            _registry_cache["data"] = skills
            return {"ok": True, "source": "local", "skills": skills}
        raise HTTPException(status_code=503, detail="registry inaccessible et aucun fallback local")


class ImportSkillBody(BaseModel):
    skills: list[dict]


@app.post("/skills/import")
def importer_skills(body: ImportSkillBody):
    """Importe un ou plusieurs skills depuis le registry ou un JSON collé manuellement."""
    import competences
    result = competences.importer_depuis_registry(body.skills)
    return {"ok": True, **result}


@app.get("/auto-amelioration")
def auto_amelioration():
    """Analyse multi-sources (registre + erreurs + membrane + skills) -> signaux + points forts."""
    import auto_amelioration as aa
    return aa.analyser_usage()


@app.get("/auto-amelioration/journal")
def auto_amelioration_journal():
    """Trace des actions automatiques prises par la boucle d'auto-amélioration."""
    import auto_amelioration as aa
    return {"actions": aa.journal_actions(limite=30)}


@app.post("/auto-amelioration/cycle")
def auto_amelioration_cycle(authorization: str = Header(None)):
    """Force un cycle d'auto-amélioration (admin). Retourne le rapport + actions prises."""
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Réservé à l'administrateur")
    import auto_amelioration as aa
    return aa.cycle(force=True)


# ── Planificateur : tâches autonomes (cron léger, modèle local) ───────────────

@app.get("/taches")
def lister_taches():
    import planificateur
    return {"taches": planificateur.lister()}


class TacheBody(BaseModel):
    nom: str
    agent: str = "cerveau"
    message: str
    intervalle_minutes: int = 60
    provider: str = "local"      # local | anthropic | openai | gemini | deepseek | mistral
    model: str | None = None


@app.post("/taches")
def creer_tache(body: TacheBody):
    import planificateur
    return {"ok": True, "tache": planificateur.creer(
        body.nom, body.agent, body.message, body.intervalle_minutes,
        provider=body.provider, model=body.model)}


class TacheToggleBody(BaseModel):
    actif: bool


@app.post("/taches/{tache_id}/toggle")
def toggle_tache(tache_id: str, body: TacheToggleBody):
    import planificateur
    return {"ok": planificateur.basculer(tache_id, body.actif)}


@app.delete("/taches/{tache_id}")
def supprimer_tache(tache_id: str):
    import planificateur
    return {"ok": planificateur.supprimer(tache_id)}


@app.get("/memoire")
def lister_memoire():
    """Souvenirs cross-session de l'agent — pour l'affichage dans l'UI."""
    import memoire_agent
    return {"memoires": memoire_agent.lister()}


class MemoireBody(BaseModel):
    contenu: str
    type: str = "fait"


@app.post("/memoire")
def creer_memoire(body: MemoireBody):
    import memoire_agent
    return {"ok": True, "memoire": memoire_agent.memoriser(body.contenu, body.type)}


@app.delete("/memoire/{mem_id}")
def supprimer_memoire(mem_id: str):
    import memoire_agent
    return {"ok": memoire_agent.supprimer(mem_id)}


class RecommanderBody(BaseModel):
    demande: str


@app.post("/llm/recommander")
def llm_recommander(body: RecommanderBody):
    """Analyse une demande et recommande le tier (modele) le plus econome adapte.
    C'est le 'modele adapte selon la demande' : tache simple -> leger, complexe -> fort."""
    import gateway
    return gateway.recommander_tier(body.demande)


@app.post("/agent/{role}/chat/stream")
def agent_chat_stream(role: str, demande: DemandeChat,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None),
                      x_llm_eco: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
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
    _eco = str(x_llm_eco or "").strip() in ("1", "true", "True", "on")
    _user = _auth(authorization)   # identifie l'utilisateur pour les quotas (création via chat)
    hist = [{"role": m.role, "content": m.content} for m in demande.historique]

    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def emit(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            msg = demande.message
            if demande.image_b64:
                emit({"type": "pensee", "texte": "Analyse de l'image en cours..."})
                try:
                    import gateway as _gw
                    desc = _gw.voir(_ctx, demande.image_b64,
                        "Décris précisément cette image : textes visibles, éléments visuels, structure, contenu.",
                        mime=demande.image_mime)
                    msg = f"[Image jointe]\n{desc}\n\n{msg}".strip() if msg.strip() else f"[Image jointe]\n{desc}"
                except Exception as _e_img:
                    msg = f"[Image jointe — analyse indisponible : {_e_img}]\n\n{msg}".strip()
            if demande.fichier_b64 and demande.fichier_nom:
                emit({"type": "pensee", "texte": f"Lecture de {demande.fichier_nom}..."})
                try:
                    import outils_fichiers as _of
                    contenu = _of.extraire_texte_b64(demande.fichier_b64, demande.fichier_nom)
                    prefix = f"[Fichier joint : {demande.fichier_nom}]\n{contenu}"
                    msg = f"{prefix}\n\n{msg}".strip() if msg.strip() else prefix
                except Exception as _e_fic:
                    msg = f"[Fichier joint : {demande.fichier_nom} — lecture échouée : {_e_fic}]\n\n{msg}".strip()
            dialoguer(role, msg, historique=hist, ctx=_ctx, emit=emit, eco=_eco, user=_user)
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


# Helpers JSONL : délèguent à robustesse (source unique — dette F004 résolue).
def _rjsonl(path: str) -> list:
    return _rob.lire_jsonl(path)

def _ajsonl(path: str, obj: dict) -> None:
    _rob.ajout_jsonl(path, obj)

def _wjsonl(path: str, items: list) -> None:
    _rob.ecrire_jsonl(path, items)


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
    import quotas as _q
    import credits as _cred
    return {
        "id": user["id"], "email": user["email"],
        "name": user["name"], "created_at": user.get("created_at"),
        "is_admin": _est_admin(user),
        "premium": bool(user.get("premium")),
        "palier": _q.palier(user),
        "solde_gen": _cred.solde(user["id"]),
    }


@app.post("/auth/logout")
def auth_logout(authorization: str = Header(None)):
    if not authorization:
        return {"ok": True}
    token = authorization.replace("Bearer ", "").strip()
    _wjsonl(_SESSIONS, [s for s in _rjsonl(_SESSIONS) if s.get("token") != token])
    return {"ok": True}


# ── Quotas freemium ───────────────────────────────────────────────────────────

@app.get("/quotas/me")
def quotas_me(authorization: str = Header(None)):
    """État des quotas de l'utilisateur (compteurs visibles dans l'UI)."""
    import quotas
    return quotas.etat(_auth(authorization))


class PremiumBody(BaseModel):
    email: str
    premium: bool = True


@app.post("/admin/premium")
def admin_premium(body: PremiumBody, authorization: str = Header(None)):
    """Active/désactive le premium d'un utilisateur. Admin uniquement.
    (Le paiement Stripe appellera ceci automatiquement plus tard.)"""
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Reserve a l'administrateur")
    cible = _user_by_email(body.email.strip().lower())
    if not cible:
        raise HTTPException(404, "Utilisateur introuvable")
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == cible["id"]:
            u["premium"] = bool(body.premium)
    _wjsonl(_USERS, users)
    return {"ok": True, "email": body.email, "premium": bool(body.premium)}


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
    """Délègue au chargeur unique (credentials_loader). Conservé comme alias (dette F003)."""
    from credentials_loader import lire_cred
    return lire_cred(filename, key)


def _set_premium(user_id: str, premium: bool, palier: str = "essential") -> bool:
    """Marque un utilisateur premium + définit son palier. Utilisé par l'admin et Stripe."""
    users = _rjsonl(_USERS)
    trouve = False
    for u in users:
        if u.get("id") == user_id:
            u["premium"] = bool(premium)
            u["palier"] = palier if premium else "gratuit"
            trouve = True
    if trouve:
        _wjsonl(_USERS, users)
    return trouve


def _marquer_essai_utilise(user_id: str) -> None:
    """Note que l'utilisateur a déjà bénéficié de l'essai premium (un seul par compte)."""
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == user_id:
            u["essai_utilise"] = True
    _wjsonl(_USERS, users)


def _lier_stripe_customer(user_id: str, customer_id: str) -> None:
    """Mémorise l'ID client Stripe sur le compte (pour révoquer le premium à l'annulation)."""
    if not customer_id:
        return
    users = _rjsonl(_USERS)
    for u in users:
        if u.get("id") == user_id:
            u["stripe_customer_id"] = customer_id
    _wjsonl(_USERS, users)


def _revoquer_premium_par_customer(customer_id: str) -> bool:
    """Retire le premium au compte lié à ce client Stripe (annulation/échec de paiement)."""
    if not customer_id:
        return False
    users = _rjsonl(_USERS)
    trouve = False
    for u in users:
        if u.get("stripe_customer_id") == customer_id:
            u["premium"] = False
            u["palier"] = "gratuit"
            trouve = True
    if trouve:
        _wjsonl(_USERS, users)
    return trouve


def _palier_depuis_price_id(price_id: str) -> str:
    """Déduit le palier depuis un price_id Stripe (via stripe.env)."""
    mapping = {
        _load_cred("stripe.env", "STRIPE_PRICE_ESSENTIAL_MENSUEL"): "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_ESSENTIAL_ANNUEL"):  "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_PRO_MENSUEL"):       "pro",
        _load_cred("stripe.env", "STRIPE_PRICE_PRO_ANNUEL"):        "pro",
        _load_cred("stripe.env", "STRIPE_PRICE_POWER_MENSUEL"):     "power",
        _load_cred("stripe.env", "STRIPE_PRICE_POWER_ANNUEL"):      "power",
        _load_cred("stripe.env", "STRIPE_PRICE_ENTERPRISE_MENSUEL"):"enterprise",
        _load_cred("stripe.env", "STRIPE_PRICE_ENTERPRISE_ANNUEL"): "enterprise",
        # Anciens IDs (rétrocompat)
        _load_cred("stripe.env", "STRIPE_PRICE_ID_MENSUEL"): "essential",
        _load_cred("stripe.env", "STRIPE_PRICE_ID_ANNUEL"):  "essential",
    }
    return mapping.get(price_id, "essential")


# ── Premium Stripe (abonnement) ───────────────────────────────────────────────

class PremiumCheckoutBody(BaseModel):
    plan: str = "mensuel"      # mensuel | annuel
    palier: str = "essential"  # essential | pro | power | enterprise


_PALIERS_VALIDES = ("essential", "pro", "power", "enterprise")

_PRICE_KEY_MAP = {
    ("essential", "mensuel"): "STRIPE_PRICE_ESSENTIAL_MENSUEL",
    ("essential", "annuel"):  "STRIPE_PRICE_ESSENTIAL_ANNUEL",
    ("pro",       "mensuel"): "STRIPE_PRICE_PRO_MENSUEL",
    ("pro",       "annuel"):  "STRIPE_PRICE_PRO_ANNUEL",
    ("power",     "mensuel"): "STRIPE_PRICE_POWER_MENSUEL",
    ("power",     "annuel"):  "STRIPE_PRICE_POWER_ANNUEL",
    ("enterprise","mensuel"): "STRIPE_PRICE_ENTERPRISE_MENSUEL",
    ("enterprise","annuel"):  "STRIPE_PRICE_ENTERPRISE_ANNUEL",
}


@app.post("/premium/checkout")
def premium_checkout(body: PremiumCheckoutBody | None = None,
                     authorization: str | None = Header(default=None)):
    """Crée une session Stripe Checkout pour passer au palier choisi (essential/pro/power/enterprise).
    Plan mensuel ou annuel (-30%). Essai 7j avec CB pour le premier abonnement."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Connecte-toi pour passer premium.")
    import quotas as _qotas
    palier_actuel = _qotas.palier(user)
    plan   = (body.plan   if body else "mensuel") or "mensuel"
    palier = (body.palier if body else "essential") or "essential"
    if palier not in _PALIERS_VALIDES:
        palier = "essential"
    if palier_actuel == palier:
        raise HTTPException(status_code=400, detail=f"Tu es deja au palier '{palier}'.")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    cle_price = _PRICE_KEY_MAP.get((palier, plan))
    price_id = (_load_cred("stripe.env", cle_price) if cle_price else "") or \
               _load_cred("stripe.env", "STRIPE_PRICE_ID_MENSUEL") or \
               _load_cred("stripe.env", "STRIPE_PRICE_ID")
    if not secret_key or not price_id:
        raise HTTPException(status_code=503, detail="Stripe premium non configure.")
    _stripe.api_key = secret_key
    base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        prix = _stripe.Price.retrieve(price_id)
        mode = "subscription" if getattr(prix, "recurring", None) else "payment"
        params = dict(
            mode=mode,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=user["id"],
            customer_email=user.get("email"),
            metadata={"palier": palier},
            success_url=f"{base_url}/#compte?premium_session={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/#compte",
        )
        if mode == "subscription" and not user.get("essai_utilise"):
            jours = int(_os.environ.get("NEOGEN_TRIAL_DAYS", "7") or 7)
            params["subscription_data"] = {"trial_period_days": jours, "metadata": {"palier": palier}}
            _marquer_essai_utilise(user["id"])
        session = _stripe.checkout.Session.create(**params)
        return {"url": session.url, "palier": palier, "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


@app.post("/premium/confirmer")
def premium_confirmer(data: dict, authorization: str | None = Header(default=None)):
    """Confirme le paiement au retour de Stripe (fonctionne sans webhook public).
    Vérifie que la session est payée ET appartient bien à l'utilisateur connecté."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifie")
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id manquant")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    try:
        sess = _stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")
    # Valide si paye OU essai actif (no_payment_required), ET rattache a CET utilisateur.
    statut_ok = sess.get("payment_status") in ("paid", "no_payment_required")
    if statut_ok and sess.get("client_reference_id") == user["id"]:
        palier_sess = (sess.get("metadata") or {}).get("palier", "essential")
        _set_premium(user["id"], True, palier_sess)
        _lier_stripe_customer(user["id"], sess.get("customer") or "")
        essai = sess.get("payment_status") == "no_payment_required"
        import credits as _cred
        _cred.recharger_mensuel(user["id"], palier_sess)
        return {"ok": True, "premium": True, "palier": palier_sess, "essai": essai}
    return {"ok": False, "premium": False, "raison": "Paiement non confirme pour ce compte."}


@app.post("/premium/webhook")
async def premium_webhook(request: Request):
    """Webhook Stripe (prod) : marque premium sur paiement reussi. Signature verifiee."""
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    wh_secret = _load_cred("stripe.env", "STRIPE_WEBHOOK_SECRET")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        if wh_secret:
            event = _stripe.Webhook.construct_event(payload, sig, wh_secret)
        else:
            event = _json.loads(payload)  # dev sans secret (moins sur)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signature invalide : {e}")
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})
    if etype == "checkout.session.completed":
        uid = obj.get("client_reference_id")
        if uid and obj.get("payment_status") in ("paid", "no_payment_required"):
            palier_evt = (obj.get("metadata") or {}).get("palier", "essential")
            _set_premium(uid, True, palier_evt)
            _lier_stripe_customer(uid, obj.get("customer") or "")
            import credits as _cred
            _cred.recharger_mensuel(uid, palier_evt)
    elif etype in ("customer.subscription.deleted",):
        # Abonnement annule/termine -> on retire le premium.
        _revoquer_premium_par_customer(obj.get("customer") or "")
    elif etype == "invoice.payment_failed":
        # Echec de paiement (apres l'essai par ex) -> on retire le premium.
        _revoquer_premium_par_customer(obj.get("customer") or "")
    return {"received": True}


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


# ── Économie Genyte (GEN) ─────────────────────────────────────────────────────

@app.get("/credits/me")
def credits_me(authorization: str = Header(None)):
    """Solde GEN + historique des 50 dernières transactions."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import credits as _cred
    import quotas as _q
    return {
        "solde": _cred.solde(user["id"]),
        "palier": _q.palier(user),
        "historique": _cred.historique(user["id"]),
        "gen_mensuel": _cred.GEN_MENSUEL.get(_q.palier(user), 0),
    }


class CreditsDepenseBody(BaseModel):
    fonction: str
    montant: int | None = None   # si None, utilise le coût par défaut du palier


@app.post("/credits/depenser")
def credits_depenser(body: CreditsDepenseBody, authorization: str = Header(None)):
    """Débite des GEN pour une fonction. 402 si solde insuffisant."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import credits as _cred
    import quotas as _q
    p = _q.palier(user)
    montant = body.montant if body.montant is not None else (_cred.cout(body.fonction, p) or 0)
    if montant is None:
        raise HTTPException(402, f"'{body.fonction}' non disponible sur le palier {p}.")
    result = _cred.debiter(user["id"], montant, body.fonction)
    if not result["ok"]:
        raise HTTPException(402, f"Solde GEN insuffisant ({result['manque']} GEN manquants).")
    return result


class CreditsRechargerBody(BaseModel):
    pack: str   # starter | pro | power | ultimate


_PACKS_GEN = {
    "starter":  {"gen": 100,   "eur": 200},
    "pro":      {"gen": 500,   "eur": 800},
    "power":    {"gen": 1500,  "eur": 2000},
    "ultimate": {"gen": 5000,  "eur": 5000},
}


@app.post("/credits/recharger")
def credits_recharger(body: CreditsRechargerBody, authorization: str = Header(None)):
    """Crée une session Stripe Checkout pour acheter un pack GEN."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    pack = _PACKS_GEN.get(body.pack)
    if not pack:
        raise HTTPException(400, f"Pack inconnu : {body.pack}. Valides : {list(_PACKS_GEN)}")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(503, "Stripe non configure")
    _stripe.api_key = secret_key
    base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": pack["eur"],
                    "product_data": {
                        "name": f"Pack GEN {body.pack.capitalize()} — {pack['gen']} Genyte",
                        "description": f"{pack['gen']} GEN crédités immédiatement sur ton compte NEOGEN",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            client_reference_id=user["id"],
            customer_email=user.get("email"),
            metadata={"type": "credits", "pack": body.pack, "gen": str(pack["gen"])},
            success_url=f"{base_url}/#compte?credits_ok={pack['gen']}",
            cancel_url=f"{base_url}/#compte",
        )
        return {"url": session.url, "pack": body.pack, "gen": pack["gen"]}
    except Exception as e:
        raise HTTPException(502, f"Stripe : {e}")


@app.post("/credits/confirmer-recharge")
def credits_confirmer_recharge(data: dict, authorization: str = Header(None)):
    """Confirme l'achat d'un pack GEN (retour Stripe). Crédite le compte."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(400, "session_id manquant")
    import stripe as _stripe
    _stripe.api_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    try:
        sess = _stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(502, f"Stripe : {e}")
    if (sess.get("payment_status") != "paid" or
            sess.get("client_reference_id") != user["id"] or
            (sess.get("metadata") or {}).get("type") != "credits"):
        return {"ok": False, "raison": "Session invalide ou non payée."}
    gen = int((sess.get("metadata") or {}).get("gen", 0))
    pack = (sess.get("metadata") or {}).get("pack", "")
    import credits as _cred
    nouveau = _cred.crediter(user["id"], gen, "purchase", f"Pack GEN {pack}")
    return {"ok": True, "gen_ajoutes": gen, "nouveau_solde": nouveau}


@app.get("/credits/boosts")
def credits_boosts(authorization: str = Header(None)):
    """Boosts Flash actifs (non expirés) de l'utilisateur."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import boosts as _boosts
    return {"boosts": _boosts.boosts_actifs(user["id"])}


class BoostActiverBody(BaseModel):
    type_boost: str   # flash_24h | flash_7j


@app.post("/credits/boosts/activer")
def credits_boosts_activer(body: BoostActiverBody, authorization: str = Header(None)):
    """Active un boost Flash en débitant les GEN."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import boosts as _boosts
    import quotas as _q
    result = _boosts.activer(user["id"], body.type_boost, _q.palier(user))
    if not result["ok"]:
        raise HTTPException(402, result["raison_refus"])
    return result


# ── Télémétrie RGPD ────────────────────────────────────────────────────────────

class TelemetrieConsentBody(BaseModel):
    niveau: str   # aucun | erreurs | usage | tout


@app.post("/telemetrie/consentement")
def telemetrie_set_consent(body: TelemetrieConsentBody, authorization: str = Header(None)):
    """Définit le niveau de consentement télémétrique de l'utilisateur."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import telemetrie as _tele
    import recompenses as _reco
    niveaux = ("aucun", "erreurs", "usage", "tout")
    if body.niveau not in niveaux:
        raise HTTPException(400, f"Niveau invalide. Valides : {niveaux}")
    _tele.set_consentement(user["id"], body.niveau)   # type: ignore[arg-type]
    result = {"ok": True, "niveau": body.niveau}
    # Bonus GEN si opt-in activé pour la première fois
    if body.niveau != "aucun":
        r = _reco.declencher(user["id"], "telemetrie_mensuelle")
        if r["ok"]:
            result["recompense"] = r["message"]
    return result


@app.get("/telemetrie/consentement")
def telemetrie_get_consent(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import telemetrie as _tele
    return {"niveau": _tele.get_consentement(user["id"])}


@app.delete("/telemetrie/me")
def telemetrie_effacer(authorization: str = Header(None)):
    """RGPD : efface TOUTES les données télémétrique liées à ce compte."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import telemetrie as _tele
    return _tele.effacer(user["id"])


@app.get("/admin/telemetrie")
def admin_telemetrie(authorization: str = Header(None)):
    """Stats télémétrie agrégées anonymes. Admin uniquement."""
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Réservé à l'administrateur")
    import telemetrie as _tele
    return _tele.stats_agregees()


# ── Récompenses Genyte ─────────────────────────────────────────────────────────

class RecompenseBody(BaseModel):
    evenement: str   # premiere_creation | premier_skill | streak_7j | ...


@app.post("/recompenses/declencher")
def recompenses_declencher(body: RecompenseBody, authorization: str = Header(None)):
    """Déclenche une récompense GEN (côté serveur, avec anti-abus cooldown)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifié")
    import recompenses as _reco
    result = _reco.declencher(user["id"], body.evenement)
    if not result["ok"] and result["raison_refus"]:
        raise HTTPException(429, result["raison_refus"])
    return result


# ── OpenLegi / Legifrance ─────────────────────────────────────────────────────

@app.get("/integrations/status")
def integrations_status():
    """Detecte quelles integrations sont disponibles cote serveur (credentials montes)."""
    return {
        "openlegi": bool(_load_cred("openlegi.env", "OPENLEGI_TOKEN")),
        "stripe": bool(_load_cred("stripe.env", "STRIPE_SECRET_KEY")),
    }


class IntegVerifBody(BaseModel):
    type: str            # url | key | oauth
    name: str = ""
    value: str = ""      # URL ou token selon le type


@app.post("/integrations/verifier")
async def integrations_verifier(body: IntegVerifBody):
    """Verifie REELLEMENT une integration tierce avant de la marquer active.
    - url  : ping HTTP de l'endpoint (doit repondre)
    - key  : appel de test (OpenLegi) avec le token fourni
    - oauth: non verifiable cote serveur -> ok:false, manuel:true (l'UI marque 'non verifie')
    Retourne {ok: bool, manuel?: bool, erreur?: str}.
    """
    import httpx
    from sanitizer import nettoyer
    t = (body.type or "").strip()
    val = (body.value or "").strip()

    if t == "oauth":
        return {"ok": False, "manuel": True, "erreur": "Verification automatique impossible (connexion via le navigateur)."}

    if t == "url":
        if not val:
            return {"ok": False, "erreur": "URL vide."}
        if not val.startswith(("http://", "https://")):
            val = "https://" + val
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                r = await client.get(val)
            if r.status_code < 500:
                return {"ok": True}
            return {"ok": False, "erreur": f"Le service repond en erreur (HTTP {r.status_code})."}
        except Exception as e:
            return {"ok": False, "erreur": nettoyer(f"Injoignable : {e}")}

    if t == "key":
        if not val:
            return {"ok": False, "erreur": "Token vide."}
        # OpenLegi : ping reel du MCP avec le token fourni.
        if body.name == "openlegi":
            try:
                async with httpx.AsyncClient(timeout=12) as client:
                    r = await client.post(
                        f"https://mcp.openlegi.fr/legifrance/mcp?token={val}",
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                        headers={"Content-Type": "application/json",
                                 "Accept": "application/json, text/event-stream"},
                    )
                if r.status_code in (401, 403):
                    return {"ok": False, "erreur": "Token refuse (401/403)."}
                if r.status_code < 500:
                    return {"ok": True}
                return {"ok": False, "erreur": f"Service en erreur (HTTP {r.status_code})."}
            except Exception as e:
                return {"ok": False, "erreur": nettoyer(f"Injoignable : {e}")}
        # Cle generique : on ne peut pas tester sans endpoint connu.
        return {"ok": False, "manuel": True, "erreur": "Pas de test automatique pour cette cle."}

    return {"ok": False, "erreur": "Type d'integration inconnu."}


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
    # L'agent capture les actions si enregistrement manuel OU apprentissage continu.
    return {"recording": rpa.is_recording() or rpa.is_continuous(),
            "continuous": rpa.is_continuous()}


class RpaContinuousBody(BaseModel):
    enabled: bool


@app.post("/rpa/continuous")
def rpa_continuous_set(body: RpaContinuousBody, authorization: str | None = Header(default=None)):
    # Apprentissage continu = fonction premium. Activation refusée en gratuit.
    if body.enabled:
        import quotas
        if not quotas.verifier(_auth(authorization), "apprentissage_continu")["autorise"]:
            raise HTTPException(status_code=402,
                                detail="L'apprentissage continu est reserve a la version premium.")
    return {"enabled": rpa.set_continuous(body.enabled)}


@app.get("/rpa/continuous")
def rpa_continuous_get():
    return rpa.continuous_status()


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


@app.post("/rpa/screenshot")
def rpa_screenshot(body: dict):
    """L'agent local envoie une capture d'écran (base64 PNG) pour la perception."""
    img = body.get("image", "")
    if not img:
        raise HTTPException(status_code=400, detail="image manquante")
    rpa.store_screenshot(img)
    return {"ok": True}


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


# ── Paramètres RPA (consentement) ────────────────────────────────────────────

_RPA_SETTINGS_PATH = Path("/app/data/rpa_settings.json")
_RPA_SETTINGS_DEFAULT: dict = {"consent_level": "sequence"}


@app.get("/rpa/settings")
def rpa_settings_get():
    try:
        if _RPA_SETTINGS_PATH.exists():
            return _json.loads(_RPA_SETTINGS_PATH.read_text())
    except Exception:
        pass
    return _RPA_SETTINGS_DEFAULT.copy()


class RpaSettingsBody(BaseModel):
    consent_level: str
    sequence_duration: int = 120  # secondes


@app.post("/rpa/settings")
def rpa_settings_post(body: RpaSettingsBody):
    if body.consent_level not in ("always", "sequence", "auto"):
        raise HTTPException(status_code=400, detail="consent_level invalide (always|sequence|auto)")
    if not (0 <= body.sequence_duration <= 86400):
        raise HTTPException(status_code=400, detail="sequence_duration invalide (0-86400s)")
    data = {"consent_level": body.consent_level, "sequence_duration": body.sequence_duration}
    _RPA_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RPA_SETTINGS_PATH.write_text(_json.dumps(data))
    return {"ok": True, **data}


# ── Endpoint Déploiement Hostinger ───────────────────────────────────────────

class DeployBody(BaseModel):
    domain: str


@app.post("/produits/{produit_id}/deploy")
def deploy_produit(produit_id: str, body: DeployBody, authorization: str | None = Header(default=None)):
    """Prépare le pack de déploiement et crée une demande pour l'agent local / MCP."""
    # Déploiement = fonction premium.
    import quotas
    _u = _auth(authorization)
    if not quotas.verifier(_u, "deploiement")["autorise"]:
        raise HTTPException(status_code=402, detail="Le deploiement est reserve a la version premium.")
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


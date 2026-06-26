from __future__ import annotations
import json as _json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field

import registre
from capacites import Capacites
from pipeline import fabriquer_reel
from .deps import _exiger_byok, _verifier_quota, _llm_client

router = APIRouter()


class DemandeFabrication(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)
    reparer: bool = Field(default=True)
    max_tentatives: int = Field(default=3, ge=1, le=5)
    juger: bool = Field(default=False)
    persistance: bool = Field(default=False)
    reseau: bool = Field(default=False)
    domaines_autorises: list[str] = Field(default_factory=list)


class ReponseFabrication(BaseModel):
    succes: bool
    verdict: str
    tentatives: int
    lignes: int
    lecons: list[str]
    produit_id: str | None = None
    capacites: str = "aucune"
    classement: list = []


class DemandeUpgrade(BaseModel):
    intention: str | None = Field(default=None)
    reparer: bool = True
    max_tentatives: int = Field(default=3, ge=1, le=5)
    persistance: bool = False
    reseau: bool = False
    domaines_autorises: list[str] = Field(default_factory=list)


class DemandeExecution(BaseModel):
    donnees: dict = Field(default_factory=dict)


class DemandeProposition(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)


class DemandeComposition(BaseModel):
    intention: str = Field(min_length=3, max_length=2000)
    murs: list[str] = Field(default_factory=list)
    persistance: bool = False
    reseau: bool = False
    domaines_autorises: list[str] = Field(default_factory=list)
    juger: bool = False


# ── LLM ────────────────────────────────────────────────────────────────────────

@router.post("/llm/verifier")
def verifier_llm(x_llm_provider: str | None = Header(default=None),
                 x_llm_model: str | None = Header(default=None),
                 x_llm_key: str | None = Header(default=None),
                 x_llm_base: str | None = Header(default=None)):
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


@router.post("/conseil")
def conseil_endpoint(demande: DemandeProposition,
                     x_llm_provider: str | None = Header(default=None),
                     x_llm_model: str | None = Header(default=None),
                     x_llm_key: str | None = Header(default=None),
                     x_llm_base: str | None = Header(default=None)):
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


@router.post("/proposer")
def proposer_endpoint(demande: DemandeProposition,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
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


# ── Fabriquer ──────────────────────────────────────────────────────────────────

@router.post("/fabriquer", response_model=ReponseFabrication)
def fabriquer_endpoint(demande: DemandeFabrication,
                       x_llm_provider: str | None = Header(default=None),
                       x_llm_model: str | None = Header(default=None),
                       x_llm_key: str | None = Header(default=None),
                       x_llm_base: str | None = Header(default=None)):
    from sanitizer import nettoyer
    cap = Capacites(persistance=demande.persistance, reseau=demande.reseau,
                    domaines_autorises=demande.domaines_autorises)
    try:
        cl = _llm_client(x_llm_provider, x_llm_model, x_llm_key, x_llm_base, tier="fort")
        if demande.juger:
            from pipeline import fabriquer_juge_reel
            r = fabriquer_juge_reel(demande.intention, reparer=demande.reparer,
                                    max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap, client=cl)
        else:
            r = fabriquer_reel(demande.intention, reparer=demande.reparer,
                               max_tentatives=demande.max_tentatives, enregistrer=True, cap=cap, client=cl)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=nettoyer(f"echec de fabrication : {e}"))
    produit_id = None
    if r.succes:
        entrees = registre.lister()
        if entrees:
            produit_id = entrees[-1]["id"]
    return ReponseFabrication(succes=r.succes, verdict=r.verdict, tentatives=r.tentatives,
                              lignes=r.lignes, lecons=r.lecons, produit_id=produit_id,
                              capacites=cap.resume(), classement=getattr(r, "classement", []) or [])


# ── Produits ───────────────────────────────────────────────────────────────────

@router.get("/produits")
def lister_produits():
    items = registre.lister()
    for item in items:
        item["promu"] = registre.est_promu(item["id"])
    return {"produits": items}


@router.get("/produits/{produit_id}/telecharger")
def telecharger_produit(produit_id: str):
    import io, zipfile
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
    from fastapi.responses import StreamingResponse as _SR
    return _SR(buf, media_type="application/zip",
               headers={"Content-Disposition": f'attachment; filename="neogen-{safe_id}.zip"'})


@router.get("/produits/{produit_id}/generations")
def generations_produit(produit_id: str):
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


@router.get("/produits/{produit_id}/diff")
def diff_produit(produit_id: str, vs: str | None = None):
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


@router.post("/produits/{produit_id}/archiver")
def archiver_produit(produit_id: str):
    """Archive un produit (masque dans le catalogue par defaut). Reversible via filtre 'Archivees'."""
    if not any(e["id"] == produit_id for e in registre.lister()):
        raise HTTPException(status_code=404, detail="produit introuvable")
    registre.archiver(produit_id)
    return {"ok": True, "id": produit_id}


@router.post("/produits/{produit_id}/revert")
def revert_produit(produit_id: str):
    lignee = registre.lignee_produit(produit_id)
    if not lignee:
        raise HTTPException(status_code=404, detail="produit introuvable")
    lineage = lignee[0].get("lineage")
    registre.definir_actif(lineage, produit_id)
    return {"ok": True, "lineage": lineage, "actif": produit_id}


@router.post("/produits/{produit_id}/upgrade")
def upgrade_produit(produit_id: str, demande: DemandeUpgrade,
                    x_llm_provider: str | None = Header(default=None),
                    x_llm_model: str | None = Header(default=None),
                    x_llm_key: str | None = Header(default=None),
                    x_llm_base: str | None = Header(default=None)):
    import queue, threading
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
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
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
            file_evts.put({"stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                           "tentatives": r.tentatives, "lignes": r.lignes,
                           "produit_id": nouveau, "parent_id": produit_id,
                           "lecons": [nettoyer(l) for l in (r.lecons or [])]})
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


@router.post("/produits/{produit_id}/promouvoir")
def promouvoir_endpoint(produit_id: str):
    contrat = registre.charger_contrat(produit_id)
    if contrat is None:
        raise HTTPException(status_code=400, detail="produit non promouvable (aucun contrat d'entree)")
    registre.promouvoir(produit_id)
    return {"promu": True, "app": f"/produits/{produit_id}/app"}


@router.post("/produits/{produit_id}/executer")
def executer_produit(produit_id: str, demande: DemandeExecution):
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
    cap = Capacites(persistance="persistance" in caps_list, reseau="reseau" in caps_list,
                    bureau="bureau" in caps_list, domaines_autorises=meta.get("domaines_autorises", []))
    volume_nom = ("viv_" + registre._slug(meta.get("intention", ""))) if cap.persistance else None
    from executeur_conteneur import executer_avec_entree
    return executer_avec_entree(code, demande.donnees, cap=cap, volume_nom=volume_nom)


@router.get("/produits/{produit_id}/app", response_class=HTMLResponse)
def app_produit(produit_id: str):
    if not registre.est_promu(produit_id):
        raise HTTPException(status_code=404, detail="produit non promu")
    contrat = registre.charger_contrat(produit_id)
    if contrat is None:
        raise HTTPException(status_code=404, detail="aucun contrat")
    from promotion import page_app
    return page_app(produit_id, contrat)


@router.get("/produits/{produit_id}")
def obtenir_produit(produit_id: str):
    code = registre.charger(produit_id)
    if code is None:
        raise HTTPException(status_code=404, detail="produit introuvable")
    return {"id": produit_id, "code": code, "promu": registre.est_promu(produit_id),
            "contrat": registre.charger_contrat(produit_id)}


# ── Studio A→Z ─────────────────────────────────────────────────────────────────

@router.post("/composer")
def composer_endpoint(demande: DemandeComposition,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None)):
    from compositeur import REGLES_MURS
    from capacites import CATALOGUE_CAPACITES
    from sanitizer import nettoyer
    murs_expliques = [{"cle": m, "explication": REGLES_MURS.get(m, m)} for m in demande.murs]
    capacites = []
    if demande.persistance:
        capacites.append({"cle": "persistance", "explication": CATALOGUE_CAPACITES["persistance"]})
    if demande.reseau:
        dom = ", ".join(demande.domaines_autorises) or "(liste blanche a preciser)"
        capacites.append({"cle": "reseau", "explication": CATALOGUE_CAPACITES["reseau"] + f" Domaines : {dom}."})
    try:
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
    return {"objectif": demande.intention, "murs": murs_expliques, "capacites": capacites,
            "mode_juge": demande.juger, "description_premiere_generation": description}


@router.post("/fabriquer/stream")
def fabriquer_stream(demande: DemandeFabrication,
                     x_llm_provider: str | None = Header(default=None),
                     x_llm_model: str | None = Header(default=None),
                     x_llm_key: str | None = Header(default=None),
                     x_llm_base: str | None = Header(default=None),
                     authorization: str | None = Header(default=None)):
    import queue, threading
    from sanitizer import nettoyer
    from gateway import contexte_depuis_headers, resume_ctx
    cap = Capacites(persistance=demande.persistance, reseau=demande.reseau,
                    domaines_autorises=demande.domaines_autorises)
    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _user, _ = _verifier_quota(authorization, "creations")
    if demande.juger:
        _verifier_quota(authorization, "mode_juge")
    _moteur = resume_ctx(_ctx)
    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def progress(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            from gateway import client as _gw
            cl = _gw(_ctx, tier="fort")
            file_evts.put({"stade": "moteur", "msg": nettoyer(_moteur)})
            if demande.juger:
                from pipeline import fabriquer_juge_reel
                r = fabriquer_juge_reel(demande.intention, reparer=demande.reparer,
                                        max_tentatives=demande.max_tentatives, enregistrer=True,
                                        cap=cap, progress=progress, client=cl)
            else:
                from pipeline import fabriquer_reel as _fr
                r = _fr(demande.intention, reparer=demande.reparer,
                        max_tentatives=demande.max_tentatives, enregistrer=True,
                        cap=cap, progress=progress, client=cl)
            produit_id = None
            if r.succes:
                entrees = registre.lister()
                if entrees:
                    produit_id = entrees[-1]["id"]
                if _user:
                    import quotas
                    quotas.incrementer(_user["id"], "creations")
                    if demande.juger:
                        quotas.incrementer(_user["id"], "mode_juge")
            file_evts.put({"stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                           "tentatives": r.tentatives, "lignes": r.lignes, "produit_id": produit_id,
                           "capacites": cap.resume(), "classement": getattr(r, "classement", []) or [],
                           "lecons": [nettoyer(l) for l in (r.lecons or [])]})
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


@router.post("/orchestrer/stream")
def orchestrer_stream(demande: DemandeFabrication,
                      x_llm_provider: str | None = Header(default=None),
                      x_llm_model: str | None = Header(default=None),
                      x_llm_key: str | None = Header(default=None),
                      x_llm_base: str | None = Header(default=None),
                      authorization: str | None = Header(default=None)):
    import queue, threading
    from sanitizer import nettoyer
    from gateway import contexte_depuis_headers, resume_ctx
    cap = Capacites(persistance=demande.persistance, reseau=demande.reseau,
                    domaines_autorises=demande.domaines_autorises)
    _ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    _exiger_byok(_ctx)
    _user, _ = _verifier_quota(authorization, "creations")
    _moteur = resume_ctx(_ctx)
    file_evts: "queue.Queue" = queue.Queue()
    _SENTINEL = object()

    def progress(evt: dict):
        safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
        file_evts.put(safe)

    def travailler():
        try:
            from orchestrateur import orchestrer
            file_evts.put({"stade": "moteur", "msg": nettoyer(_moteur)})
            r = orchestrer(demande.intention, ctx=_ctx, cap=cap, reparer=demande.reparer,
                           max_tentatives=demande.max_tentatives, enregistrer=True, progress=progress)
            produit_id = None
            if r.succes:
                entrees = registre.lister()
                if entrees:
                    produit_id = entrees[-1]["id"]
                if _user:
                    import quotas
                    quotas.incrementer(_user["id"], "creations")
            file_evts.put({"stade": "fini", "succes": r.succes, "verdict": nettoyer(r.verdict),
                           "tentatives": r.tentatives, "lignes": r.lignes, "produit_id": produit_id,
                           "capacites": cap.resume(), "plan": getattr(r, "plan", []) or [],
                           "lecons": [nettoyer(l) for l in (r.lecons or [])]})
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


# ── Cristallisation de skill (ajout wow post-production) ────────────────────

from pydantic import BaseModel, Field as _Field

class _SkillExtrait(BaseModel):
    nom: str = _Field(description="nom court en kebab-case, ex: scraper-prix")
    titre: str = _Field(description="titre lisible, ex: Scraper de prix")
    description: str = _Field(description="ce que fait ce skill, une phrase")
    instructions: str = _Field(description="comment l utiliser / le reproduire, 3-5 lignes")
    outils: list[str] = _Field(default_factory=list,
                               description="outils agent utiles pour ce skill")


@router.post("/produits/{produit_id}/cristalliser")
def cristalliser_produit(produit_id: str,
                         x_llm_provider: str | None = Header(default=None),
                         x_llm_model: str | None = Header(default=None),
                         x_llm_key: str | None = Header(default=None),
                         x_llm_base: str | None = Header(default=None)):
    from gateway import contexte_depuis_headers, client as _gw
    from sanitizer import nettoyer
    import competences

    code = registre.charger(produit_id)
    if not code:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    entrees = registre.lister()
    entree = next((e for e in entrees if e["id"] == produit_id), {})
    intention = entree.get("intention", produit_id)

    ctx = contexte_depuis_headers(x_llm_provider, x_llm_model, x_llm_key, x_llm_base)
    cl = _gw(ctx, tier="moyen")

    systeme = (
        "Tu es un expert en capitalisation de patterns logiciels. "
        "Analyse ce code Python produit par NEOGEN et extrais un SKILL REUTILISABLE : "
        "un pattern qui pourrait servir dans d autres projets similaires. "
        "Sois concis et actionnable."
    )
    messages = [{"role": "user", "content":
        f"Intention originale : {intention}\n\nCode :\n```python\n{code[:3000]}\n```\n\n"
        "Extrais le skill reutilisable (nom kebab-case, titre lisible, description courte, "
        "instructions 3-5 lignes, outils agent pertinents)."}]

    try:
        resp = cl.messages.parse(system=systeme, messages=messages,
                                 max_tokens=1500, output_format=_SkillExtrait)
        s = resp.parsed_output
        if s is None:
            raise RuntimeError("extraction vide")
    except Exception as e:
        raise HTTPException(status_code=502, detail=nettoyer(f"Extraction echouee : {e}"))

    skill = competences.creer(
        nom=s.nom, description=s.description,
        instructions=s.instructions, outils=s.outils, auto=True
    )
    skill["titre"] = nettoyer(s.titre)
    return {"ok": True, "skill": skill, "produit_id": produit_id}

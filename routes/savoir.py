from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException, Query, Response

import quotas as _quotas
import savoir as _savoir
import proposeur_hub as _proposeur

router = APIRouter(prefix="/savoir", tags=["savoir"])


def _gate_owner(authorization: str | None = Header(default=None)):
    """Route réservée au propriétaire (NEOGEN_OWNER_UNLIMITED=1 ou email owner)."""
    if _quotas._owner_unlimited():
        return
    from routes.deps import _auth
    user = _auth(authorization)
    if _quotas.palier(user) == "enterprise":
        return
    raise HTTPException(status_code=403, detail="Section réservée au propriétaire.")


@router.get("/etat")
def hub_etat(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    return _savoir.HUB.etat()


@router.get("/reseau")
def reseau_etat(authorization: str | None = Header(default=None)):
    """Etat du reseau d'intelligence distribuee : environnement + file de contribution."""
    _gate_owner(authorization)
    import reseau_savoir as _rs
    return _rs.etat()


@router.post("/reseau/contribuer")
def reseau_contribuer(authorization: str | None = Header(default=None)):
    """Declenche manuellement le cycle de contribution montante (proprietaire)."""
    _gate_owner(authorization)
    import reseau_savoir as _rs
    return _rs.cycle_contribution()


@router.post("/rafraichir")
def hub_rafraichir(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    stats = _savoir.HUB.rafraichir()
    nouvelles = _proposeur.generer()
    return {"ok": True, "grains_par_silo": stats, "nouvelles_propositions": len(nouvelles)}


@router.get("/chercher")
def hub_chercher(
    q: str = Query(..., min_length=1),
    domaine: str | None = Query(default=None),
    k: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
):
    _gate_owner(authorization)
    return _savoir.HUB.chercher(q, domaine=domaine, k=k)


@router.get("/propositions")
def hub_propositions(
    statut: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    _gate_owner(authorization)
    return _savoir.charger_propositions(statut=statut)


@router.post("/propositions/{prop_id}/approuver")
def hub_approuver(prop_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    res = _proposeur.approuver(prop_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("erreur", "erreur"))
    return res


@router.post("/propositions/{prop_id}/refuser")
def hub_refuser(prop_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    res = _proposeur.refuser(prop_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("erreur", "erreur"))
    return res


# ── La Pensee : intelligence collective autonome ────────────────────────────────

@router.get("/pensees")
def pensees_lister(
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    """Archive complete des pensees (tous scores), plus recentes d'abord."""
    _gate_owner(authorization)
    import pensee as _pensee
    return {"etat": _pensee.etat(), "pensees": _pensee.lister(limit=limit)}


@router.get("/pensees/bulles")
def pensees_bulles(authorization: str | None = Header(default=None)):
    """Pensees a haut score non lues -> bulles de notification (polling UI)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return {"bulles": _pensee.bulles_non_lues()}


@router.post("/pensees/{pensee_id}/lue")
def pensees_marquer_lue(pensee_id: str, authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    import pensee as _pensee
    res = _pensee.marquer_lue(pensee_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail="pensee introuvable")
    return res


@router.post("/pensees/{pensee_id}/archiver")
def pensees_archiver(pensee_id: str, authorization: str | None = Header(default=None)):
    """Archive une pensee (masquee par defaut, visible via filtre 'archivee' dans l'UI)."""
    _gate_owner(authorization)
    import pensee as _pensee
    res = _pensee.marquer_archive(pensee_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail="pensee introuvable")
    return res


@router.post("/pensees/archiver-anciens")
def pensees_archiver_anciens(semaines: int = 1, authorization: str | None = Header(default=None)):
    """Archive les pensees en etat actif/generee depuis plus de N semaines (1 par defaut)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee.archiver_anciens(semaines)


# Types/indices qui demandent du VRAI code (passent par la forge), pas du data-driven.
_TYPES_FORGE = {"fonction", "capacite"}
_INDICES_TECHNIQUES = ("etapes", "code", "action", "scanner", "valider", "reparer",
                       "parser", "detecter", "compiler", "indexer", "automatis")

# Indices qu'une idee concerne l'INTERFACE/experience -> forge d'interface (CSS reel).
_INDICES_INTERFACE = ("interface", "affichage", "ecran", "liste", "replier", "repliable",
                      "deroulant", "regrouper", "compact", "densite", "layout", "onglet",
                      "vue", "agrandir", "plus grand", "chat", "scroll", "bloc", "carte",
                      "lisible", "organis", "espace", "colonne", "mise en page")


def _est_interface(evo: dict | None, p: dict) -> bool:
    """Une pensee concerne l'INTERFACE si son evolution est de type esthetique/section,
    ou si son contenu evoque l'affichage/l'experience visuelle."""
    if isinstance(evo, dict) and (evo.get("type") or "").lower() in ("esthetique", "section", "interface"):
        return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_INTERFACE)


def _est_technique(evo: dict | None, p: dict) -> bool:
    """Une pensee est 'technique' (donc forgeable en code) si son evolution vise une fonction,
    ou si son payload/contenu contient des indices d'action executable."""
    if isinstance(evo, dict):
        if (evo.get("type") or "").lower() in _TYPES_FORGE:
            return True
        payload = evo.get("payload") if isinstance(evo.get("payload"), dict) else {}
        if any(k in payload for k in ("etapes", "code", "action")):
            return True
    blob = f"{p.get('titre','')} {p.get('synthese','')}".lower()
    return any(ind in blob for ind in _INDICES_TECHNIQUES)


@router.post("/pensees/{pensee_id}/donner-vie")
def pensees_donner_vie(pensee_id: str, authorization: str | None = Header(default=None)):
    """Donne vie a une pensee, en routant selon sa NATURE :
      - technique/fonctionnelle -> LA FORGE (generator -> Membrane -> sandbox), vrai code teste.
        Asynchrone : renvoie {voie:'forge', job_id} ; l'UI poll /evolution/forge/{job_id}.
      - data-driven (agent, modele, savoir, regle, loi) -> proposition evolution gouvernee.
      - idee pure -> proposition 'idee' notee (honnete : pas de fausse 'vie')."""
    _gate_owner(authorization)
    import pensee as _pensee
    import evolution_gouvernee as _evo

    toutes = _pensee.lister(limit=500)
    p = next((x for x in toutes if x.get("id") == pensee_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="pensee introuvable")

    evo = p.get("evolution") if isinstance(p.get("evolution"), dict) else None

    # VOIE 0 : interface -> forge d'interface (CSS reel). Apercu d'abord, puis confirmation.
    if _est_interface(evo, p):
        import forge_interface
        idee = f"{p.get('titre','')}. {p.get('synthese','')}".strip()
        apercu = forge_interface.generer_apercu(idee)
        if apercu.get("ok"):
            return {"ok": True, "voie": "interface", "pensee_id": pensee_id,
                    "titre": p.get("titre", ""), "css": apercu["css"],
                    "explication": apercu.get("explication", "")}
        # echec de generation -> on retombe honnetement (pas d'effet, on le dit)
        return {"ok": False, "voie": "interface", "raison": apercu.get("raison", "echec")}

    # VOIE 1 : technique -> la forge (vrai code).
    if _est_technique(evo, p):
        import forge_evolution
        besoin = f"{p.get('titre','')}. {p.get('synthese','')}".strip()
        if evo and isinstance(evo.get("payload"), dict):
            besoin += " Details : " + str(evo["payload"])[:400]
        job_id = forge_evolution.lancer_forge_async(
            besoin, titre=p.get("titre", ""), pensee_id=pensee_id)
        return {"ok": True, "voie": "forge", "job_id": job_id}

    # VOIE 2 : data-driven explicite (le LLM a propose un type non technique).
    if evo and evo.get("type") and isinstance(evo.get("payload"), dict):
        payload = dict(evo["payload"])
        payload["_pensee_id"] = pensee_id
        r = _evo.proposer(evo["type"], payload, titre=p.get("titre", ""),
                          raison=evo.get("raison", "") or p.get("synthese", ""))
        r["voie"] = "data"
        return r

    # VOIE 3 : idee pure -> notee honnetement (proposition idee).
    r = _evo.proposer(
        "idee",
        {"idee": f"{p.get('titre', '')} : {p.get('synthese', '')}".strip(),
         "_pensee_id": pensee_id},
        titre=p.get("titre", ""), raison=p.get("synthese", ""))
    r["voie"] = "note"
    try:
        _pensee.marquer_forge(pensee_id, "notee")
    except Exception:
        pass
    return r


@router.get("/pensees/config")
def pensees_config(authorization: str | None = Header(default=None)):
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee._config()


@router.post("/pensees/config")
def pensees_set_config(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Met a jour mode (eco/fort/mixte), actif (bool), intervalle_min (int)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee._set_config(
        mode=corps.get("mode"),
        actif=corps.get("actif"),
        intervalle_min=corps.get("intervalle_min"),
    )


@router.post("/pensees/cycle")
def pensees_cycle(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Provoque immediatement une session de pensee (proprietaire).
    Optionnel : {"sujet": "..."} -> discussion personnalisee sur ce theme avec les agents."""
    _gate_owner(authorization)
    import pensee as _pensee
    sujet = (corps or {}).get("sujet") if isinstance(corps, dict) else None
    return _pensee.cycle_pensee(force=True, sujet=sujet)


# ── Evolution gouvernee : la super-capacite (s'auto-modifier sans toucher au noyau) ──

def _user_courant(authorization: str | None):
    try:
        from routes.deps import _auth
        return _auth(authorization)
    except Exception:
        return None


@router.get("/evolution/etat")
def evolution_etat(authorization: str | None = Header(default=None)):
    """Noyau (ADN+murs), generation courante, stores forgeables actifs."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return _evo.etat()


@router.get("/evolution/generation")
def evolution_generation(authorization: str | None = Header(default=None)):
    """Generation NEOGEN courante (1 an) + changelog des changements de l'annee."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    return {"generation": _evo.generation_courante(), "changelog": _evo.changelog_generation()}


@router.get("/evolution/types")
def evolution_types(authorization: str | None = Header(default=None)):
    """Types forgeables (perso / systeme) et frontiere du noyau."""
    _gate_owner(authorization)
    import noyau as _noyau
    return _noyau.resume()


@router.post("/evolution/proposer")
def evolution_proposer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Soumet un changement : gardien noyau -> proposition (consentement via /propositions)."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    res = _evo.proposer(
        corps.get("type", ""), corps.get("payload", {}) or {},
        titre=corps.get("titre", ""), raison=corps.get("raison", ""),
        cible=corps.get("cible"), user=_user_courant(authorization),
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


@router.post("/evolution/appliquer")
def evolution_appliquer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Applique directement un changement (admin : le consentement est l'acte d'appel).
    Re-garde par le noyau ; un changement systeme reste refuse pour un non-admin."""
    _gate_owner(authorization)
    import evolution_gouvernee as _evo
    res = _evo.appliquer(corps or {}, user=_user_courant(authorization))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


# ── La Forge : suivi de progression + cellules de code reel generees ─────────────

@router.get("/evolution/forge/{job_id}")
def evolution_forge_statut(job_id: str, authorization: str | None = Header(default=None)):
    """Etat d'avancement d'une forge en cours (polling UI pour la bulle de progression)."""
    _gate_owner(authorization)
    import forge_evolution as _forge
    return _forge.statut_job(job_id)


@router.get("/evolution/cellules")
def evolution_cellules(authorization: str | None = Header(default=None)):
    """Liste des cellules de code reel forgees (sans le code), plus recentes d'abord."""
    _gate_owner(authorization)
    import forge_evolution as _forge
    return {"cellules": _forge.lister_cellules()}


@router.get("/evolution/cellules/{nom}")
def evolution_cellule(nom: str, authorization: str | None = Header(default=None)):
    """Une cellule forgee AVEC son code Python reel + verdict Membrane + resume du test."""
    _gate_owner(authorization)
    import forge_evolution as _forge
    c = _forge.cellule(nom)
    if not c:
        raise HTTPException(status_code=404, detail="cellule introuvable")
    return c


# ── Forge d'interface : l'override CSS reel applique a l'ecran (admin) ────────────

@router.get("/evolution/ui.css")
def evolution_ui_css():
    """Sert l'override CSS d'interface (charge par l'ecran au demarrage). Vide si aucun.
    Pas de gate : c'est du CSS d'apparence, jamais une donnee sensible."""
    import forge_interface as _fi
    return Response(content=_fi.overrides_actuels(), media_type="text/css")


@router.post("/evolution/ui/appliquer")
def evolution_ui_appliquer(
    corps: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    """Applique le CSS confirme (admin) ou le remonte en proposition (public)."""
    _gate_owner(authorization)
    import forge_interface as _fi
    res = _fi.appliquer((corps or {}).get("css", ""), user=_user_courant(authorization),
                        titre=(corps or {}).get("titre", ""))
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("raison", "refuse"))
    return res


@router.post("/evolution/ui/reset")
def evolution_ui_reset(authorization: str | None = Header(default=None)):
    """Reinitialise l'interface : retour a l'apparence d'origine (reversibilite)."""
    _gate_owner(authorization)
    import forge_interface as _fi
    return _fi.reinitialiser()

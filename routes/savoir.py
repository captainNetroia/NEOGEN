from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException, Query

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
def pensees_cycle(authorization: str | None = Header(default=None)):
    """Provoque immediatement une session de pensee (proprietaire)."""
    _gate_owner(authorization)
    import pensee as _pensee
    return _pensee.cycle_pensee(force=True)


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

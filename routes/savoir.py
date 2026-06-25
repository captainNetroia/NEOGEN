from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

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

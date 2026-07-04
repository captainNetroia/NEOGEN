from __future__ import annotations
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from .deps import _auth, _est_admin

router = APIRouter()


class TelemetrieConsentBody(BaseModel):
    niveau: str


class RecompenseBody(BaseModel):
    evenement: str


@router.post("/telemetrie/consentement")
def telemetrie_set_consent(body: TelemetrieConsentBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import telemetrie as _tele
    import recompenses as _reco
    niveaux = ("aucun", "erreurs", "usage", "tout")
    if body.niveau not in niveaux:
        raise HTTPException(400, f"Niveau invalide. Valides : {niveaux}")
    _tele.set_consentement(user["id"], body.niveau)
    result = {"ok": True, "niveau": body.niveau}
    if body.niveau != "aucun":
        r = _reco.declencher(user["id"], "telemetrie_mensuelle")
        if r["ok"]:
            result["recompense"] = r["message"]
    return result


@router.get("/telemetrie/consentement")
def telemetrie_get_consent(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import telemetrie as _tele
    return {"niveau": _tele.get_consentement(user["id"])}


@router.delete("/telemetrie/me")
def telemetrie_effacer(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import telemetrie as _tele
    return _tele.effacer(user["id"])


@router.get("/admin/telemetrie")
def admin_telemetrie(authorization: str = Header(None)):
    user = _auth(authorization)
    if not _est_admin(user):
        raise HTTPException(403, "Reserve a l'administrateur")
    import telemetrie as _tele
    return _tele.stats_agregees()


# Evenements que le client peut declencher lui-meme sans verification serveur externe
# (auto-declaratifs : premiere action, streak de connexion). skill_valide/parrainage/
# cadeau_tirage sont exclus ici car ils dependent d'un fait verifie ailleurs (validation
# communautaire d'un skill, inscription reelle d'un filleul, tirage serveur) : les
# exposer sur cet endpoint public permettrait de les declencher a volonte (farming GEN).
_EVENEMENTS_CLIENT_AUTORISES = frozenset({
    "premiere_creation", "premier_skill", "streak_7j", "telemetrie_mensuelle",
})


@router.post("/recompenses/declencher")
def recompenses_declencher(body: RecompenseBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    if body.evenement not in _EVENEMENTS_CLIENT_AUTORISES:
        raise HTTPException(403, "Cet evenement ne peut pas etre declenche directement.")
    import recompenses as _reco
    result = _reco.declencher(user["id"], body.evenement)
    if not result["ok"] and result["raison_refus"]:
        raise HTTPException(429, result["raison_refus"])
    return result

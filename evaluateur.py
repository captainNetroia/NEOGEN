"""
NEOGEN - Évaluateur : score d'un Grain sur 4 axes.

utilité (usages) · qualité (type) · unicité (cosinus vs corpus) · contexte (récence)
-> score ∈ [0.0, 1.0]

Seuils de décision :
  >= SEUIL_INTEGRATION (0.75) -> proposer intégration système
  >= SEUIL_PARTAGE     (0.55) -> proposer partage communautaire
  <  SEUIL_PARTAGE           -> garder local

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import time

import vecteurs

SEUIL_INTEGRATION = 0.75
SEUIL_PARTAGE = 0.55

_QUALITE_TYPE = {
    "competence": 0.90,
    "lecon":      0.80,
    "pattern":    0.65,
    "decision":   0.55,
    "fait":       0.45,
}


def scorer_grain(grain, tous: list) -> float:
    """Score global 0-1 pour un Grain (dataclass ou dict). Contexte = liste complète des grains."""
    def _get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    usages = int(_get(grain, "usages", 0))
    type_ = _get(grain, "type", "")
    contenu = _get(grain, "contenu", "")
    domaine = _get(grain, "domaine", "")
    ts = float(_get(grain, "ts", time.time()))
    gid = _get(grain, "id", "")

    u = _utilite(usages)
    q = _qualite(type_)
    uni = _unicite(contenu, domaine, gid, tous)
    ctx = _contexte(ts)
    return round(0.30 * u + 0.30 * q + 0.25 * uni + 0.15 * ctx, 3)


def decision(score: float) -> str:
    if score >= SEUIL_INTEGRATION:
        return "integration"
    if score >= SEUIL_PARTAGE:
        return "partage"
    return "local"


def _utilite(usages: int) -> float:
    return min(usages / 15.0, 1.0)


def _qualite(type_: str) -> float:
    return _QUALITE_TYPE.get(type_, 0.40)


def _unicite(contenu: str, domaine: str, gid: str, tous: list) -> float:
    def _get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    voisins = [
        _get(g, "contenu", "")
        for g in tous
        if _get(g, "domaine") == domaine and _get(g, "id") != gid
    ]
    if not voisins:
        return 1.0
    resultats = vecteurs.classer(contenu, voisins, limite=1)
    if not resultats:
        return 1.0
    return round(max(0.0, 1.0 - resultats[0][1]), 3)


def _contexte(ts: float) -> float:
    age_j = (time.time() - ts) / 86400.0
    return max(0.0, round(1.0 - age_j / 30.0, 3))

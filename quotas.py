"""
NEOGEN - Quotas freemium.

Version GRATUITE limitée + déblocage PREMIUM (paiement mensuel/annuel à brancher
via Stripe ensuite). Matrice validée avec Jordan :
  - 5 créations d'app (une modification compte comme 1 usage)
  - 2 usages du mode jugé
  - 3 intégrations tierces actives
  - 1 modèle IA enregistré (+ Ollama local toujours gratuit)
  - déploiement, apprentissage continu : premium uniquement

Cohérence : l'utilisateur est PRÉVENU avant de consommer (compteur visible), et
quand il atteint 0 -> message clair + invitation à passer premium, jamais
d'échec silencieux.

Comptage PAR UTILISATEUR connecté (data/quotas_usage.json). Premium = illimité.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-22.
"""

from __future__ import annotations

import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.path.join(BASE_DIR, "data", "quotas_usage.json")

_LOCK = threading.Lock()

# Limites du plan GRATUIT (None = illimité, réservé au premium).
PLAN_GRATUIT = {
    "creations": 5,
    "mode_juge": 2,
    "integrations": 3,
    "modeles": 1,
}
# Fonctions entièrement réservées au premium (booléennes).
PREMIUM_ONLY = ("deploiement", "apprentissage_continu", "delegation_complete")

LIBELLES = {
    "creations": "Créations d'app",
    "mode_juge": "Mode jugé",
    "integrations": "Intégrations tierces",
    "modeles": "Modèles IA enregistrés",
}


def _lire() -> dict:
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire(data: dict) -> None:
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def est_premium(user: dict | None) -> bool:
    return bool(user and user.get("premium"))


def usage(user_id: str) -> dict:
    return _lire().get(user_id, {})


def incrementer(user_id: str, type_: str, n: int = 1) -> int:
    """Incrémente un compteur d'usage. Renvoie la nouvelle valeur."""
    with _LOCK:
        data = _lire()
        u = data.setdefault(user_id, {})
        u[type_] = u.get(type_, 0) + n
        _ecrire(data)
        return u[type_]


def verifier(user: dict | None, type_: str) -> dict:
    """Vérifie si l'utilisateur peut consommer 'type_'.
    Retourne {autorise, premium, reste, limite, utilise, raison}."""
    premium = est_premium(user)
    if premium:
        return {"autorise": True, "premium": True, "reste": None,
                "limite": None, "utilise": 0, "raison": "premium : illimité"}
    # Premium-only : refusé en gratuit.
    if type_ in PREMIUM_ONLY:
        return {"autorise": False, "premium": False, "reste": 0, "limite": 0,
                "utilise": 0, "raison": f"'{type_}' est reservé à la version premium."}
    uid = (user or {}).get("id", "")
    limite = PLAN_GRATUIT.get(type_)
    if limite is None:
        return {"autorise": True, "premium": False, "reste": None,
                "limite": None, "utilise": 0, "raison": "non limité"}
    utilise = usage(uid).get(type_, 0) if uid else 0
    reste = max(0, limite - utilise)
    autorise = reste > 0
    return {"autorise": autorise, "premium": False, "reste": reste,
            "limite": limite, "utilise": utilise,
            "raison": "" if autorise else f"Limite gratuite atteinte ({limite}). Passe premium pour continuer."}


def etat(user: dict | None) -> dict:
    """État complet des quotas pour l'UI (compteurs visibles)."""
    premium = est_premium(user)
    uid = (user or {}).get("id", "")
    u = usage(uid)
    lignes = []
    for cle, limite in PLAN_GRATUIT.items():
        utilise = u.get(cle, 0)
        lignes.append({
            "cle": cle, "libelle": LIBELLES.get(cle, cle),
            "utilise": utilise, "limite": None if premium else limite,
            "reste": None if premium else max(0, limite - utilise),
        })
    return {"premium": premium, "connecte": bool(uid), "quotas": lignes,
            "premium_only": list(PREMIUM_ONLY)}


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - QUOTAS : auto-vérification")
    print("=" * 60)
    # Nettoyage test
    with _LOCK:
        d = _lire(); d.pop("__test__", None); _ecrire(d)
    user_free = {"id": "__test__", "email": "t@t.fr"}
    user_prem = {"id": "__test__", "email": "t@t.fr", "premium": True}
    # Gratuit : 5 créations
    for i in range(5):
        v = verifier(user_free, "creations")
        assert v["autorise"], v
        incrementer("__test__", "creations")
    v = verifier(user_free, "creations")
    assert not v["autorise"] and v["reste"] == 0, v
    # Premium : illimité
    assert verifier(user_prem, "creations")["autorise"]
    # Premium-only refusé en gratuit
    assert not verifier(user_free, "deploiement")["autorise"]
    assert verifier(user_prem, "deploiement")["autorise"]
    # Nettoyage
    with _LOCK:
        d = _lire(); d.pop("__test__", None); _ecrire(d)
    print("  limites gratuit / blocage a 0 / premium illimite / premium-only : OK")
    print("=" * 60)

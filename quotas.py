"""
NEOGEN - Quotas freemium multi-paliers.

Paliers : gratuit / essential / pro / power / enterprise
Chaque palier hérite des permissions du précédent (cumulatif).
Quotas mensuels par palier pour les fonctions comptées.
None = illimité. "premium_only" = refusé si palier insuffisant.
"""
from __future__ import annotations

import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.path.join(BASE_DIR, "data", "quotas_usage.json")

_LOCK = threading.Lock()

PALIERS_ORDONNES = ["gratuit", "essential", "pro", "power", "enterprise"]


def rang_palier(palier: str) -> int:
    try:
        return PALIERS_ORDONNES.index(palier)
    except ValueError:
        return 0


# Limites mensuelles par palier (None = illimité).
LIMITES: dict[str, dict[str, int | None]] = {
    "gratuit":    {"creations": 5,    "mode_juge": 2,    "integrations": 3, "modeles": 1},
    "essential":  {"creations": None, "mode_juge": None, "integrations": None, "modeles": 5},
    "pro":        {"creations": None, "mode_juge": None, "integrations": None, "modeles": None},
    "power":      {"creations": None, "mode_juge": None, "integrations": None, "modeles": None},
    "enterprise": {"creations": None, "mode_juge": None, "integrations": None, "modeles": None},
}

# Palier minimum requis pour certaines fonctions.
PALIER_REQUIS: dict[str, str] = {
    "deploiement":           "essential",
    "apprentissage_continu": "pro",
    "delegation_complete":   "pro",
    "vision":                "power",
    "cron_illimite":         "power",
    "telemetrie_privee":     "enterprise",
    "webhooks_api":          "enterprise",
    "gen_illimites":         "enterprise",
}

LIBELLES = {
    "creations":    "Créations d'app",
    "mode_juge":    "Mode jugé",
    "integrations": "Intégrations tierces",
    "modeles":      "Modèles IA enregistrés",
}


def palier(user: dict | None) -> str:
    """Retourne le palier effectif de l'utilisateur."""
    if not user:
        return "gratuit"
    p = user.get("palier", "")
    if p in PALIERS_ORDONNES:
        return p
    # Rétrocompat : ancien champ booléen premium
    if user.get("premium"):
        return "essential"
    return "gratuit"


def est_premium(user: dict | None) -> bool:
    return palier(user) != "gratuit"


# ── I/O ──────────────────────────────────────────────────────────────────────

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


def usage(user_id: str) -> dict:
    return _lire().get(user_id, {})


def incrementer(user_id: str, type_: str, n: int = 1) -> int:
    with _LOCK:
        data = _lire()
        u = data.setdefault(user_id, {})
        u[type_] = u.get(type_, 0) + n
        _ecrire(data)
        return u[type_]


# ── Vérification ─────────────────────────────────────────────────────────────

def verifier(user: dict | None, type_: str) -> dict:
    """
    Vérifie si l'utilisateur peut utiliser 'type_'.
    Retourne {autorise, palier, reste, limite, utilise, raison}.
    """
    p = palier(user)

    # Vérification palier minimum requis
    if type_ in PALIER_REQUIS:
        requis = PALIER_REQUIS[type_]
        if rang_palier(p) < rang_palier(requis):
            return {
                "autorise": False, "palier": p, "reste": 0, "limite": 0,
                "utilise": 0,
                "raison": f"'{type_}' requiert le palier '{requis}' ou supérieur.",
            }

    uid = (user or {}).get("id", "")
    limites_palier = LIMITES.get(p, LIMITES["gratuit"])
    limite = limites_palier.get(type_)

    if limite is None:
        return {"autorise": True, "palier": p, "reste": None,
                "limite": None, "utilise": 0, "raison": "illimité"}

    utilise = usage(uid).get(type_, 0) if uid else 0
    reste = max(0, limite - utilise)
    autorise = reste > 0
    raison = "" if autorise else (
        f"Limite {p} atteinte ({limite}). "
        + ("Passe à un palier supérieur." if p == "gratuit" else "Contacte le support.")
    )
    return {"autorise": autorise, "palier": p, "reste": reste,
            "limite": limite, "utilise": utilise, "raison": raison}


def etat(user: dict | None) -> dict:
    """État complet des quotas pour l'UI."""
    p = palier(user)
    uid = (user or {}).get("id", "")
    u = usage(uid)
    limites_palier = LIMITES.get(p, LIMITES["gratuit"])
    lignes = []
    for cle, libelle in LIBELLES.items():
        limite = limites_palier.get(cle)
        utilise = u.get(cle, 0)
        lignes.append({
            "cle": cle, "libelle": libelle,
            "utilise": utilise,
            "limite": limite,
            "reste": None if limite is None else max(0, limite - utilise),
        })
    # Fonctions débloquées selon le palier
    fonctions_dispo = [
        f for f, requis in PALIER_REQUIS.items()
        if rang_palier(p) >= rang_palier(requis)
    ]
    return {
        "palier": p, "premium": est_premium(user),
        "connecte": bool(uid), "quotas": lignes,
        "fonctions_dispo": fonctions_dispo,
        "palier_requis": PALIER_REQUIS,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - QUOTAS multi-paliers : auto-vérification")
    print("=" * 60)
    with _LOCK:
        d = _lire(); d.pop("__test__", None); _ecrire(d)

    u_free  = {"id": "__test__"}
    u_ess   = {"id": "__test__", "palier": "essential"}
    u_pro   = {"id": "__test__", "palier": "pro"}
    u_power = {"id": "__test__", "palier": "power"}
    u_ent   = {"id": "__test__", "palier": "enterprise"}

    # Gratuit : 5 créations
    for _ in range(5):
        v = verifier(u_free, "creations")
        assert v["autorise"], v
        incrementer("__test__", "creations")
    assert not verifier(u_free, "creations")["autorise"]

    # Essential : illimité créations
    assert verifier(u_ess, "creations")["autorise"]
    # Essential : peut déployer
    assert verifier(u_ess, "deploiement")["autorise"]
    # Gratuit : ne peut pas déployer
    assert not verifier(u_free, "deploiement")["autorise"]
    # Pro requis pour delegation_complete
    assert not verifier(u_ess, "delegation_complete")["autorise"]
    assert verifier(u_pro, "delegation_complete")["autorise"]
    # Power requis pour vision
    assert not verifier(u_pro, "vision")["autorise"]
    assert verifier(u_power, "vision")["autorise"]
    # Enterprise : tout
    assert verifier(u_ent, "telemetrie_privee")["autorise"]
    # Rétrocompat premium booléen → essential
    assert palier({"premium": True}) == "essential"

    with _LOCK:
        d = _lire(); d.pop("__test__", None); _ecrire(d)
    print("  Tous les tests paliers OK")
    print("=" * 60)

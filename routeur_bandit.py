"""
NEOGEN - Routeur bandit (UCB1) : apprendre le meilleur tier de modèle par type de tâche.

Avant : `gateway.recommander_tier` était une heuristique FIGÉE (mots-clés + longueur).
Ici : un bandit manchot multi-bras (Upper Confidence Bound, UCB1) APPREND, par catégorie
de tâche, quel tier (leger/moyen/fort) réussit au MOINDRE coût, à partir des résultats réels.

Maths (UCB1) : pour chaque bras a de moyenne empirique x̄_a tiré n_a fois sur N total,
  score(a) = x̄_a + c · sqrt(2 · ln(N) / n_a)
On tire le bras de score max. Un bras jamais tiré a un score infini (exploration forcée).
La récompense mêle SUCCÈS et COÛT : un tier léger qui réussit vaut mieux qu'un tier fort
qui réussit (moins de tokens = plus de valeur). Le bandit converge donc vers le tier le
plus économe QUI MARCHE pour chaque catégorie.

Persistance : data/bandit.json. Repli heuristique tant que les données sont insuffisantes.
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23.
"""
from __future__ import annotations

import json
import math
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANDIT_FILE = os.path.join(BASE_DIR, "data", "bandit.json")

_LOCK = threading.Lock()

TIERS = ("leger", "moyen", "fort")
C_EXPLORATION = 1.4          # constante UCB1 (~sqrt(2)) : + = plus d'exploration
MIN_OBS_AVANT_CONFIANCE = 8  # sous ce nb d'obs pour une catégorie, on reste sur l'heuristique
# Pénalité de coût par tier : pousse vers le moins cher À SUCCÈS ÉGAL.
PENALITE_COUT = {"leger": 0.0, "moyen": 0.10, "fort": 0.20}


def recompense(succes: bool, tier: str) -> float:
    """Récompense ∈ [0,1] : 0 si échec ; sinon 1 moins la pénalité de coût du tier."""
    if not succes:
        return 0.0
    return max(0.0, 1.0 - PENALITE_COUT.get(tier, 0.1))


def _lire() -> dict:
    if not os.path.exists(BANDIT_FILE):
        return {}
    try:
        with open(BANDIT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(BANDIT_FILE), exist_ok=True)
        with open(BANDIT_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _stats_cat(d: dict, categorie: str) -> dict:
    return d.setdefault(categorie, {t: {"n": 0, "somme": 0.0} for t in TIERS})


def choisir(categorie: str, defaut: str = "moyen") -> tuple[str, str]:
    """Choisit un tier pour cette catégorie via UCB1.
    Retourne (tier, source) où source ∈ {'bandit','exploration','heuristique'}.
    Tant que la catégorie a trop peu d'observations -> ('', 'heuristique') : l'appelant garde son heuristique."""
    with _LOCK:
        d = _lire()
        stats = _stats_cat(d, categorie)
        total = sum(stats[t]["n"] for t in TIERS)
        # Exploration forcée : un tier jamais essayé est prioritaire.
        jamais = [t for t in TIERS if stats[t]["n"] == 0]
        if jamais:
            # On n'explore que si la catégorie a déjà "démarré" (au moins 1 obs) pour ne pas
            # perturber les toutes premières requêtes -> sinon heuristique.
            if total == 0:
                return "", "heuristique"
            return jamais[0], "exploration"
        if total < MIN_OBS_AVANT_CONFIANCE:
            return "", "heuristique"
        # UCB1
        meilleur, meilleur_score = defaut, -1.0
        for t in TIERS:
            n = stats[t]["n"]
            moyenne = stats[t]["somme"] / n
            ucb = moyenne + C_EXPLORATION * math.sqrt(2 * math.log(total) / n)
            if ucb > meilleur_score:
                meilleur, meilleur_score = t, ucb
        return meilleur, "bandit"


def recompenser(categorie: str, tier: str, succes: bool) -> float:
    """Met à jour les stats du bras (categorie, tier) avec la récompense. Retourne la récompense."""
    if tier not in TIERS:
        return 0.0
    r = recompense(succes, tier)
    with _LOCK:
        d = _lire()
        stats = _stats_cat(d, categorie)
        stats[tier]["n"] += 1
        stats[tier]["somme"] += r
        _ecrire(d)
    return r


def categoriser(demande: str) -> str:
    """Catégorie grossière de la tâche (clé du bandit). Stable et bon marché."""
    t = (demande or "").lower()
    if any(m in t for m in ("clic", "ecran", "écran", "ouvre", "ferme", "navigateur", "remplis")):
        return "rpa"
    if any(m in t for m in ("analyse", "compare", "evalue", "pourquoi", "explique", "audit")):
        return "analyse"
    if any(m in t for m in ("cree", "créer", "fabrique", "genere", "application", "app ", "code")):
        return "creation"
    return "conversation"


def etat() -> dict:
    """État lisible du bandit (pour /health ou debug)."""
    d = _lire()
    out = {}
    for cat, stats in d.items():
        out[cat] = {t: {"n": s["n"], "moyenne": round(s["somme"] / s["n"], 3) if s["n"] else None}
                    for t, s in stats.items()}
    return out


if __name__ == "__main__":
    import tempfile
    print("=" * 60)
    print("NEOGEN - ROUTEUR BANDIT (UCB1) : auto-vérification")
    print("=" * 60)
    BANDIT_FILE = os.path.join(tempfile.mkdtemp(), "bandit.json")

    # Catégorisation
    assert categoriser("cree une app de notes") == "creation"
    assert categoriser("analyse ce code") == "analyse"
    assert categoriser("ferme l'onglet du navigateur") == "rpa"
    assert categoriser("bonjour ça va") == "conversation"

    # Récompense : succès léger > succès fort (coût)
    assert recompense(True, "leger") > recompense(True, "fort")
    assert recompense(False, "leger") == 0.0

    # Démarrage : pas de données -> heuristique
    tier, src = choisir("creation")
    assert src == "heuristique" and tier == ""

    # Apprentissage : on simule que 'moyen' réussit toujours, 'fort' aussi mais plus cher,
    # 'leger' échoue. Le bandit doit converger vers 'moyen' (réussit, moins cher que fort).
    for _ in range(20):
        recompenser("creation", "leger", succes=False)
        recompenser("creation", "moyen", succes=True)
        recompenser("creation", "fort", succes=True)
    choix = [choisir("creation")[0] for _ in range(20)]
    dominant = max(set(choix), key=choix.count)
    assert dominant == "moyen", f"le bandit devrait préférer 'moyen' : {dominant} ({choix})"

    e = etat()
    assert "creation" in e and e["creation"]["moyen"]["n"] >= 20
    print("  categorisation / recompense cout / heuristique->bandit / convergence : OK")
    print("=" * 60)

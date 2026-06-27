"""
NEOGEN - Memoire des echecs de forge : la forge apprend de ses ratages.

Sans memoire, la forge refait les memes erreurs : elle re-genere un code qui retombe dans
le meme piege (input(), reseau, meme SyntaxError...), brulant des tentatives (et des appels
LLM couteux). Ici, chaque echec est capitalise par MOTIF, et les conseils tires des echecs
passes sur un besoin similaire sont REINJECTES dans la consigne de generation suivante.

Effet : moins de tentatives, plus d'efficacite, et un systeme qui s'ameliore avec l'usage.

Stockage : data/forge_echecs.json = { motif: {count, exemples:[...], conseil, dernier_ts} }.
Robustesse : ne leve jamais. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-28.
"""
from __future__ import annotations

import json
import os
import re
import time

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_ECHECS = os.path.join(_DATA, "forge_echecs.json")

# Motifs d'echec reconnus -> conseil de generation cible (la lecon a retenir).
_MOTIFS = [
    (r"\binput\s*\(|stdin|raw_input",          "stdin",
     "Ne JAMAIS utiliser input()/sys.stdin : recevoir les donnees via des parametres de fonction."),
    (r"syntaxe|syntaxerror|invalid syntax|continuation", "syntaxe",
     "Soigner la syntaxe : pas de backslash de continuation, parentheses implicites, code qui compile."),
    (r"reseau|network|socket|urllib|requests|mur", "reseau",
     "Rester hors-ligne : aucun acces reseau (socket/urllib/requests). Fonction pure et locale."),
    (r"suppression|os\.remove|rmtree|delete",   "suppression",
     "Ne supprimer aucun fichier (os.remove/shutil.rmtree interdits)."),
    (r"timeout|delai|trop long",                "timeout",
     "Code rapide et borne : pas de boucle longue ni d'attente."),
]


def _charger() -> dict:
    try:
        if os.path.exists(_ECHECS):
            with open(_ECHECS, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _sauver(d: dict) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(_ECHECS, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _classer(erreur: str) -> tuple[str, str]:
    """Range une erreur dans un motif connu -> (motif, conseil). 'autre' si non reconnue."""
    bas = (erreur or "").lower()
    for motif_re, nom, conseil in _MOTIFS:
        if re.search(motif_re, bas):
            return nom, conseil
    return "autre", "Corriger precisement l'erreur signalee ; produire une fonction autonome testable."


def memoriser_echec(besoin: str, erreur: str) -> dict:
    """Capitalise un echec de forge par motif. Ne leve jamais. Renvoie {motif, count}."""
    with rob.garde("forge_memoire.memoriser_echec", source="forge_memoire"):
        motif, conseil = _classer(erreur)
        d = _charger()
        entree = d.setdefault(motif, {"count": 0, "exemples": [], "conseil": conseil})
        entree["count"] += 1
        entree["conseil"] = conseil
        entree["dernier_ts"] = time.time()
        ex = (besoin or "")[:120]
        if ex and ex not in entree["exemples"]:
            entree["exemples"] = (entree["exemples"] + [ex])[-5:]
        _sauver(d)
        rob.journaliser(f"forge : echec capitalise (motif '{motif}', {entree['count']}x)",
                        "info", source="forge_memoire")
        return {"motif": motif, "count": entree["count"]}
    return {"motif": "autre", "count": 0}


def conseils_pour(besoin: str, max_conseils: int = 3) -> str:
    """Conseils tires des echecs passes, a injecter dans la consigne de generation.
    Priorise les motifs les plus frequents. Vide si aucun historique. Ne leve jamais."""
    d = _charger()
    if not d:
        return ""
    tries = sorted(d.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)
    conseils = [v.get("conseil", "") for _, v in tries[:max_conseils] if v.get("conseil")]
    if not conseils:
        return ""
    return ("\n\nLEÇONS DES FORGES PASSÉES (évite ces erreurs déjà rencontrées) :\n"
            + "\n".join(f"- {c}" for c in conseils))


def etat() -> dict:
    """Vue des motifs d'echec memorises (pour l'UI/diagnostic)."""
    d = _charger()
    return {"motifs": {k: {"count": v.get("count", 0), "conseil": v.get("conseil", "")}
                       for k, v in sorted(d.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)},
            "total_echecs": sum(v.get("count", 0) for v in d.values())}


# ── Auto-verification offline ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - FORGE MEMOIRE : auto-verification (offline)")
    print("=" * 64)
    _DATA = tempfile.mkdtemp()
    _ECHECS = os.path.join(_DATA, "forge_echecs.json")

    # 1. Classement par motif.
    assert _classer("code contient input()")[0] == "stdin"
    assert _classer("invalid syntax (continuation)")[0] == "syntaxe"
    assert _classer("touche au reseau (mur)")[0] == "reseau"
    print("  classement des erreurs par motif OK")

    # 2. Memorisation + comptage.
    memoriser_echec("Lire une saisie clavier", "code contient input()/sys.stdin")
    memoriser_echec("Autre besoin avec saisie", "input() detecte")
    r = memoriser_echec("Recuperer une page web", "touche au reseau (mur)")
    assert _charger()["stdin"]["count"] == 2, _charger()
    assert r["motif"] == "reseau", r
    print(f"  memorisation : stdin x2, reseau x1 OK")

    # 3. Conseils injectables (priorise les plus frequents).
    c = conseils_pour("nouveau besoin")
    assert "input()" in c and "LEÇONS" in c, c
    print(f"  conseils_pour : {len(c)} car injectables dans la consigne OK")

    # 4. Etat.
    e = etat()
    assert e["total_echecs"] == 3 and "stdin" in e["motifs"], e
    print(f"  etat : {e['total_echecs']} echecs, motifs {list(e['motifs'])} OK")

    print("=" * 64)
    print("  TOUT VERT : la forge apprend de ses echecs (moins de tentatives, plus efficace).")
    print("=" * 64)

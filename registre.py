"""
NEOGEN - Registre des produits : la memoire des creations qui tiennent

Le pipeline fabrique des produits gouvernes. Sans registre, chaque produit
reussi etait oublie une fois affiche. Ici, tout produit qui PASSE les 3
garde-fous et TOURNE est persiste :
  - son code complet sur disque : data/produits/{slug}-{horodatage}.py
  - une entree d'index : data/registre_produits.jsonl (intention, chemin, meta)

Ainsi l'organisme garde la trace de ce qu'il sait deja produire, et peut le
relister / le recharger plus tard (base d'un futur catalogue exploitable).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import os
import re
import json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_PRODUITS = os.path.join(BASE, "data", "produits")
INDEX = os.path.join(BASE, "data", "registre_produits.jsonl")
PROMOTIONS = os.path.join(BASE, "data", "promotions.jsonl")
ACTIFS = os.path.join(BASE, "data", "lineage_actif.jsonl")


def _slug(texte: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")
    return (s or "produit")[:40]


def _norm(e: dict) -> dict:
    """Retro-compat : complete les entrees anterieures a la genealogie (Phase 4)."""
    e.setdefault("generation", 1)
    e.setdefault("parent_id", None)
    e.setdefault("lineage", _slug(e.get("intention", "")))
    return e


def enregistrer(intention: str, code: str, *, verdict: str, tentatives: int, lignes: int,
                contrat: dict | None = None, parent_id: str | None = None) -> dict:
    """Persiste un produit reussi et retourne son entree d'index.
    Si contrat (dict du schema d'entree) est fourni, le produit est PROMOUVABLE.
    GENEALOGIE (Phase 4) : si parent_id est donne, le produit est une nouvelle generation
    de la lignee du parent. Sinon, auto-chainage par intention : si une lignee de meme slug
    existe deja, ce produit en devient la generation suivante (parent = la plus recente)."""
    os.makedirs(DIR_PRODUITS, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%dT%H%M%S")
    nom_fichier = f"{_slug(intention)}-{horodatage}.py"
    chemin = os.path.join(DIR_PRODUITS, nom_fichier)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"# NEOGEN - produit pour : {intention}\n")
        f.write(f"# fabrique le {datetime.now().isoformat(timespec='seconds')} | {verdict}\n\n")
        f.write(code)

    produit_id = nom_fichier[:-3]
    if contrat is not None:
        with open(os.path.join(DIR_PRODUITS, produit_id + ".schema.json"), "w", encoding="utf-8") as f:
            json.dump(contrat, f, ensure_ascii=False, indent=2)

    # Resolution de la lignee + numero de generation.
    toutes = lister()
    parent = next((e for e in toutes if e["id"] == parent_id), None) if parent_id else None
    if parent:
        lineage = parent.get("lineage") or _slug(parent.get("intention", ""))
        generation = int(parent.get("generation", 1)) + 1
    else:
        lineage = _slug(intention)
        meme = [e for e in toutes if e.get("lineage") == lineage]
        if meme:
            dernier = meme[-1]
            parent_id = dernier["id"]
            generation = int(dernier.get("generation", len(meme))) + 1
        else:
            parent_id = None
            generation = 1

    entree = {
        "id": produit_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "intention": intention,
        "chemin": os.path.relpath(chemin, BASE),
        "verdict": verdict,
        "tentatives": tentatives,
        "lignes": lignes,
        "promouvable": contrat is not None,
        "lineage": lineage,
        "generation": generation,
        "parent_id": parent_id,
    }
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    with open(INDEX, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    # La derniere generation creee devient l'active de sa lignee.
    definir_actif(lineage, produit_id)
    return entree


def charger_contrat(produit_id: str) -> dict | None:
    """Recharge le schema d'entree (contrat) d'un produit, s'il en a un."""
    chemin = os.path.join(DIR_PRODUITS, produit_id + ".schema.json")
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def promouvoir(produit_id: str) -> dict:
    """Marque un produit comme promu (validation humaine) -> appli web servie."""
    from datetime import datetime as _dt
    entree = {"id": produit_id, "timestamp": _dt.now().isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(PROMOTIONS), exist_ok=True)
    with open(PROMOTIONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    return entree


def est_promu(produit_id: str) -> bool:
    if not os.path.exists(PROMOTIONS):
        return False
    with open(PROMOTIONS, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne and json.loads(ligne).get("id") == produit_id:
                return True
    return False


def lister() -> list[dict]:
    """Toutes les entrees du registre, plus recentes en dernier (normalisees genealogie)."""
    if not os.path.exists(INDEX):
        return []
    out = []
    with open(INDEX, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                out.append(_norm(json.loads(ligne)))
    return out


# ---------------------------------------------------------------------------
# GENEALOGIE (Phase 4) : lignee d'un produit, diff entre generations, version active
# ---------------------------------------------------------------------------
def lignee_produit(produit_id: str) -> list[dict]:
    """Toutes les generations de la meme lignee que produit_id, triees par generation."""
    toutes = lister()
    cible = next((e for e in toutes if e["id"] == produit_id), None)
    if not cible:
        return []
    lin = cible.get("lineage")
    membres = [e for e in toutes if e.get("lineage") == lin]
    membres.sort(key=lambda e: (int(e.get("generation", 1)), e.get("timestamp", "")))
    return membres


def diff_codes(id_a: str, id_b: str) -> dict:
    """Diff unifie entre deux generations (id_a = ancienne, id_b = nouvelle)."""
    import difflib
    a = charger(id_a) or ""
    b = charger(id_b) or ""
    al, bl = a.splitlines(), b.splitlines()
    diff = list(difflib.unified_diff(al, bl, fromfile=id_a, tofile=id_b, lineterm=""))
    ajouts = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    retraits = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return {
        "ajouts": ajouts, "retraits": retraits,
        "lignes_a": len(al), "lignes_b": len(bl),
        "diff": "\n".join(diff[:500]),  # borne pour ne pas exploser le flux
    }


def definir_actif(lineage: str, produit_id: str) -> None:
    """Marque la version active (courante) d'une lignee. Append : la derniere ligne prime."""
    os.makedirs(os.path.dirname(ACTIFS), exist_ok=True)
    with open(ACTIFS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"lineage": lineage, "id": produit_id,
                            "timestamp": datetime.now().isoformat(timespec="seconds")},
                           ensure_ascii=False) + "\n")


def actif_de(lineage: str) -> str | None:
    """Id de la version active d'une lignee (None si jamais defini)."""
    if not os.path.exists(ACTIFS):
        return None
    actif = None
    with open(ACTIFS, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                d = json.loads(ligne)
                if d.get("lineage") == lineage:
                    actif = d.get("id")
    return actif


def charger(produit_id: str) -> str | None:
    """Recharge le code d'un produit par son id (nom de fichier sans .py)."""
    chemin = os.path.join(DIR_PRODUITS, produit_id + ".py")
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    entrees = lister()
    print("=" * 60)
    print(f"NEOGEN - REGISTRE DES PRODUITS : {len(entrees)} produit(s)")
    print("=" * 60)
    for e in entrees:
        print(f"  [{e['timestamp']}] {e['intention'][:45]}")
        print(f"      {e['id']} | {e['lignes']} lignes | {e['verdict']}")
    if not entrees:
        print("  (vide - aucun produit fabrique pour l'instant)")
    print("=" * 60)

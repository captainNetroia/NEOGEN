"""
VIVARIUM - Registre des produits : la memoire des creations qui tiennent

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


def _slug(texte: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")
    return (s or "produit")[:40]


def enregistrer(intention: str, code: str, *, verdict: str, tentatives: int, lignes: int,
                contrat: dict | None = None) -> dict:
    """Persiste un produit reussi et retourne son entree d'index.
    Si contrat (dict du schema d'entree) est fourni, le produit est PROMOUVABLE."""
    os.makedirs(DIR_PRODUITS, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%dT%H%M%S")
    nom_fichier = f"{_slug(intention)}-{horodatage}.py"
    chemin = os.path.join(DIR_PRODUITS, nom_fichier)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"# VIVARIUM - produit pour : {intention}\n")
        f.write(f"# fabrique le {datetime.now().isoformat(timespec='seconds')} | {verdict}\n\n")
        f.write(code)

    produit_id = nom_fichier[:-3]
    if contrat is not None:
        with open(os.path.join(DIR_PRODUITS, produit_id + ".schema.json"), "w", encoding="utf-8") as f:
            json.dump(contrat, f, ensure_ascii=False, indent=2)

    entree = {
        "id": produit_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "intention": intention,
        "chemin": os.path.relpath(chemin, BASE),
        "verdict": verdict,
        "tentatives": tentatives,
        "lignes": lignes,
        "promouvable": contrat is not None,
    }
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    with open(INDEX, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")
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
    """Toutes les entrees du registre, plus recentes en dernier."""
    if not os.path.exists(INDEX):
        return []
    out = []
    with open(INDEX, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                out.append(json.loads(ligne))
    return out


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
    print(f"VIVARIUM - REGISTRE DES PRODUITS : {len(entrees)} produit(s)")
    print("=" * 60)
    for e in entrees:
        print(f"  [{e['timestamp']}] {e['intention'][:45]}")
        print(f"      {e['id']} | {e['lignes']} lignes | {e['verdict']}")
    if not entrees:
        print("  (vide - aucun produit fabrique pour l'instant)")
    print("=" * 60)

"""
NEOGEN - Compositeur incarne : la physique du sens forge la gouvernance

Fusion des deux fils de NEOGEN :
  - le fil profond : la PHYSIQUE DU SENS (matiere.py / incarner.py) - les mots
    portent une nature physique (cohesion, fluidite, charge, temperature...).
  - le fil pratique : le COMPOSITEUR - intention -> ADN (curseurs + murs).

Ici, au lieu de forger les curseurs/murs abstraitement, on INCARNE les concepts
cles de l'intention, on lit leur physique, et on en DERIVE la gouvernance :
  - concepts tres COHESIFS  -> il faut proteger ce qui tient ensemble (securite, auth).
  - concepts RIGIDES        -> robustesse, ne pas deformer/detruire facilement.
  - concepts de charge NEGATIVE -> defensif (pas d'exfiltration, pas de reseau).
  - concepts CHAUDS/volatils -> reactivite, vitesse.

La physique du sens devient la SOURCE de ce qui compte pour le produit.

HONNETETE : la physique des concepts vient de vrais appels Claude (incarner).
La derivation physique -> curseurs/murs est un jeu de regles que j'ai concu
(une "physiologie"), transparent et assume, pas une verite absolue.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic
from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL
from incarner import incarner
from compositeur import REGLES_MURS


class Concepts(BaseModel):
    mots: list[str] = Field(description="3 concepts cles (noms communs) au coeur de l'intention")


def extraire_concepts(intention: str, client) -> list[str]:
    resp = client.messages.parse(
        model=MODEL, max_tokens=2000, thinking={"type": "adaptive"},
        system="Extrais 3 concepts cles (noms communs simples) au coeur de l'intention de produit. "
               "Ce sont les notions dont la nature definit le produit.",
        messages=[{"role": "user", "content": f"Intention : {intention}"}],
        output_format=Concepts,
    )
    return (resp.parsed_output.mots if resp.parsed_output else [])[:3]


def deriver_gouvernance(physique_moy: dict) -> tuple[dict, list[tuple[str, str]]]:
    """Des proprietes physiques moyennes -> curseurs ponderes + murs. Regles transparentes."""
    coh = physique_moy["cohesion"]
    flu = physique_moy["fluidite"]
    tmp = physique_moy["temperature"]
    chg = physique_moy["charge"]
    den = physique_moy["densite"]

    curseurs = {
        "securite_integrite": round(coh * 100),       # cohesion -> proteger ce qui tient ensemble
        "robustesse": round((1 - flu) * 100),          # rigidite -> robustesse
        "reactivite_vitesse": round(tmp * 100),         # volatilite -> vitesse
        "fiabilite": round(den * 100),                  # densite -> fiabilite
    }

    murs = []
    if coh > 0.6:
        murs.append(("requires_auth", "concepts tres cohesifs : proteger l'acces a ce qui tient ensemble"))
        murs.append(("no_data_exfiltration", "ce qui est cohesif ne doit pas fuiter vers un tiers"))
    if chg < -0.1:
        murs.append(("no_external_network", "charge negative (defensif) : pas de reseau sortant non autorise"))
    if flu < 0.4:
        murs.append(("no_delete_without_confirmation", "concepts rigides : ne pas detruire sans confirmation"))
    if coh > 0.75:
        murs.append(("no_plaintext_secrets", "cohesion tres forte : le coeur ne doit jamais etre expose en clair"))
    # dedup en gardant l'ordre
    vus, murs_uniques = set(), []
    for rid, raison in murs:
        if rid not in vus:
            vus.add(rid); murs_uniques.append((rid, raison))
    return curseurs, murs_uniques


def composer_incarne(intention: str):
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"NEOGEN - COMPOSITEUR INCARNE : '{intention}'")
    print("=" * 72)

    print("\n[1] Extraction des concepts cles de l'intention...")
    concepts = extraire_concepts(intention, client)
    print(f"  concepts : {concepts}")

    print("\n[2] Incarnation : Claude donne une physique a chaque concept...")
    matieres = []
    for c in concepts:
        m, just = incarner(c, client)
        matieres.append(m)
        print(f"  {m}")
        print(f"     ({just[:90]}...)")

    # 3. agreger la physique des concepts
    n = len(matieres) or 1
    moy = {
        "cohesion": round(sum(m.cohesion for m in matieres) / n, 3),
        "fluidite": round(sum(m.fluidite for m in matieres) / n, 3),
        "temperature": round(sum(m.temperature for m in matieres) / n, 3),
        "charge": round(sum(m.charge for m in matieres) / n, 3),
        "densite": round(sum(m.densite for m in matieres) / n, 3),
    }
    print(f"\n[3] Physique moyenne de l'intention : {moy}")

    # 4. deriver la gouvernance de cette physique
    curseurs, murs = deriver_gouvernance(moy)
    print("\n[4] GOUVERNANCE DERIVEE DE LA PHYSIQUE (et non forgee abstraitement) :")
    print("  CURSEURS (ce qui compte, issu de la nature des concepts) :")
    for nom, poids in sorted(curseurs.items(), key=lambda x: -x[1]):
        print(f"     {nom:22s} : {poids}")
    print("  MURS (protections issues de la physique) :")
    if murs:
        for rid, raison in murs:
            print(f"     {rid:30s} <- {raison}")
    else:
        print("     (aucun mur protecteur derive : concepts plutot fluides/neutres)")

    print("\n" + "=" * 72)
    print("La physique du sens des concepts a engendre la gouvernance du produit :")
    print("ce qui est cohesif se protege, ce qui est rigide se preserve, ce qui est")
    print("volatil privilegie la vitesse. Le fil profond nourrit le fil pratique.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un gestionnaire de mots de passe"
    composer_incarne(intention)

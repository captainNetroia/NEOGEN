"""
VIVARIUM - Selection darwinienne : juger et elaguer les lois

L'organisme note chaque loi contre un CORPUS de verites (l'etalon), garde les
fortes, elague les faibles. Fondation de l'auto-jugement de la qualite.

GARDE-FOU : l'organisme mene le jugement tout seul, mais contre un etalon (le
corpus) qu'il ne peut PAS reecrire. Autonomie de la mesure, zero autonomie sur
l'etalon -> pas d'auto-complaisance (anti-Goodhart).

Qualite d'une loi = precision (se declenche-t-elle seulement ou il faut ?)
                  x utilite (sert-elle au moins une fois ?)
                  x simplicite (moins de conditions = plus robuste).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import dataclass

from matiere import Matiere
from invention import LoiSynthetisee


# ---------------------------------------------------------------------------
# L'ETALON : le corpus de verites (immuable du point de vue de l'organisme)
# Chaque cas = (label, a, b, tags attendus pour ce couple)
# ---------------------------------------------------------------------------
_eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
_eau2 = Matiere("eau2", 0.55, 0.9, 0.2, 0.6, -0.3)
_feu = Matiere("feu", 0.2, 0.7, 1.0, 0.3, -0.2)
_huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
_glace = Matiere("glace", 0.6, 0.1, 0.0, 0.8, -0.2)
_metal_a = Matiere("metal_a", 0.9, 0.2, 0.3, 0.9, 0.5)
_metal_b = Matiere("metal_b", 0.9, 0.2, 0.3, 0.9, 0.5)
_confiance = Matiere("confiance", 0.6, 0.3, 0.3, 0.85, 0.5, abstrait=True)
_doute = Matiere("doute", 0.2, 0.8, 0.2, 0.3, -0.4, abstrait=True)

CORPUS = [
    ("glace+feu", _glace, _feu, {"FONTE"}),
    ("eau+feu", _eau, _feu, {"REACTION"}),
    ("metal_a+metal_b", _metal_a, _metal_b, {"FUSION"}),
    ("confiance+doute", _confiance, _doute, {"EROSION"}),
    ("eau+huile", _eau, _huile, {"SEPARATION"}),
    ("eau+eau", _eau, _eau2, {"MELANGE"}),
]


@dataclass
class Qualite:
    fitness: float
    correct: int          # declenchements justes (tag attendu pour ce cas)
    faux: int             # declenchements a tort (tag non attendu)
    declenchements: int
    cas_corrects: frozenset
    taille: int


def qualite(loi: LoiSynthetisee) -> Qualite:
    correct, faux, decl = 0, 0, 0
    cas_corrects = set()
    for label, a, b, attendus in CORPUS:
        if not loi.se_declenche(a, b):
            continue
        decl += 1
        _, tag = loi.appliquer(a, b)
        if tag in attendus:
            correct += 1
            cas_corrects.add(label)
        else:
            faux += 1
    taille = len(loi.conditions)
    if decl == 0:
        fitness = 0.0                      # ne sert jamais -> inutile
    else:
        precision = correct / decl
        utilite = 1.0 if correct >= 1 else 0.0
        simplicite = 1.0 / (1.0 + 0.1 * taille)
        fitness = round(precision * utilite * simplicite, 3)
    return Qualite(fitness, correct, faux, decl, frozenset(cas_corrects), taille)


def selectionner(lois: list[LoiSynthetisee], seuil: float = 0.5):
    """Note, elague les faibles, puis retire les dominees. Renvoie (survivantes, elaguees)."""
    notes = [(l, qualite(l)) for l in lois]

    survivantes, elaguees = [], []
    # 1. seuil de fitness
    for l, q in notes:
        if q.fitness < seuil:
            raison = ("inutile (ne se declenche jamais)" if q.declenchements == 0
                      else f"trop imprecise (precision faible, {q.faux} declenchement(s) a tort)")
            elaguees.append((l, q, raison))
        else:
            survivantes.append((l, q))

    # 2. domination : meme tag + meme ensemble de cas corrects -> garder la meilleure fitness
    survivantes.sort(key=lambda x: x[1].fitness, reverse=True)
    gardees, vus = [], {}
    for l, q in survivantes:
        cle = (l.effet, q.cas_corrects)
        if cle in vus:
            elaguees.append((l, q, f"redondante (meme role que '{vus[cle].humain()}', mais moins simple)"))
        else:
            vus[cle] = l
            gardees.append((l, q))
    return gardees, elaguees


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("VIVARIUM - SELECTION DARWINIENNE DES LOIS")
    print("=" * 72)

    # Un patrimoine melange : une loi forte, une qui deborde, une redondante, une inutile
    patrimoine = [
        LoiSynthetisee(("ecart_temperature_eleve", "une_est_rigide"), "fluidifier la plus rigide"),   # forte, precise (FONTE)
        LoiSynthetisee(("une_est_rigide",), "fluidifier la plus rigide"),                              # deborde (fond tout ce qui est rigide)
        LoiSynthetisee(("ecart_temperature_eleve", "une_est_rigide", "une_est_chaude"), "fluidifier la plus rigide"),  # redondante (meme role, +1 condition)
        LoiSynthetisee(("charges_opposees",), "fusionner les deux"),                                   # inutile/nuisible
    ]

    print(f"\nPatrimoine de depart : {len(patrimoine)} loi(s). Jugement contre l'etalon (corpus)...\n")
    for l in patrimoine:
        q = qualite(l)
        print(f"  fitness {q.fitness:.3f} | {l.humain()}")
        print(f"     correct={q.correct} faux={q.faux} declenchements={q.declenchements} conditions={q.taille}")

    gardees, elaguees = selectionner(patrimoine)

    print("\n--- SELECTION ---")
    print(f"  SURVIVANTES ({len(gardees)}) :")
    for l, q in gardees:
        print(f"     [GARDE]  fitness {q.fitness:.3f} | {l.humain()}")
    print(f"  ELAGUEES ({len(elaguees)}) :")
    for l, q, raison in elaguees:
        print(f"     [ELAGUE] fitness {q.fitness:.3f} | {l.humain()}")
        print(f"              raison : {raison}")

    print("\n" + "=" * 72)
    print("L'organisme a juge ses lois contre un etalon qu'il ne peut pas reecrire,")
    print("garde la plus forte et la plus simple, elague le faible, le redondant, l'inutile.")
    print("Le patrimoine n'accumule plus : il evolue. C'est la selection.")
    print("=" * 72)


if __name__ == "__main__":
    main()

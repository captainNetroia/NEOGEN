"""
NEOGEN - Le monde apprend de ses limites

La physique du sens part avec des constantes par defaut. Sur certaines paires,
le comportement emergent est faux (eau+huile ne devrait pas se melanger).
Ce module donne au monde une VERITE (ce qu'il devrait observer), lui fait
mesurer ses propres limites, puis AJUSTE ses lois pour les corriger.

Regle absolue : l'apprentissage ne touche QUE la couche apprenable (les seuils).
Les MURS graves (conservation, integrite de nature) sont hors d'atteinte.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import random
from dataclasses import replace, fields

from matiere import Matiere, Physique, rencontre, classer, DEFAUT


# ---------------------------------------------------------------------------
# LA VERITE : ce que le monde DEVRAIT observer (le retour dont il apprend)
# Chaque cas : matieres + tags attendus + tags interdits
# ---------------------------------------------------------------------------
eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
feu = Matiere("feu", 0.1, 0.85, 0.98, 0.2, 0.6)
huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
confiance = Matiere("confiance", 0.6, 0.3, 0.3, 0.85, 0.5, abstrait=True)
doute = Matiere("doute", 0.2, 0.8, 0.2, 0.3, -0.4, abstrait=True)
eau2 = replace(eau, nom="eau2")

VERITE = [
    ("eau + feu",          eau, feu,        {"REACTION"},   set()),
    ("eau + huile",        eau, huile,      {"SEPARATION"}, {"MELANGE"}),
    ("eau + eau",          eau, eau2,       {"MELANGE"},    {"EROSION"}),
    ("confiance + doute",  confiance, doute, {"EROSION"},    set()),
]


def erreur(phys: Physique) -> int:
    """Nombre de comportements faux sur l'ensemble de la verite."""
    total = 0
    for _, a, b, attendu, interdit in VERITE:
        tags = classer(rencontre(a, b, phys)[0])
        total += len(attendu - tags)        # comportements attendus manquants
        total += len(interdit & tags)       # comportements interdits presents
    return total


def diagnostic(phys: Physique) -> list[str]:
    lignes = []
    for nom, a, b, attendu, interdit in VERITE:
        tags = classer(rencontre(a, b, phys)[0])
        manquants = attendu - tags
        en_trop = interdit & tags
        if manquants or en_trop:
            details = []
            if manquants: details.append("manque " + ", ".join(sorted(manquants)))
            if en_trop: details.append("en trop " + ", ".join(sorted(en_trop)))
            lignes.append(f"  [LIMITE] {nom} : {' ; '.join(details)} (observe : {sorted(tags) or 'rien'})")
        else:
            lignes.append(f"  [OK]     {nom} : {sorted(tags)}")
    return lignes


# Bornes de recherche : uniquement la couche APPRENABLE
BORNES = {
    "seuil_reaction": (0.30, 0.55),
    "seuil_fluide":   (0.45, 0.65),
    "seuil_affinite": (0.05, 0.40),
    "erosion_charge": (-0.35, -0.05),
    "erosion_temp":   (0.30, 0.50),
    "erosion_marge":  (0.0, 0.35),
}


def apprendre(depart: Physique, essais: int = 1500, graine: int = 7) -> Physique:
    """Recherche les constantes qui minimisent l'erreur. Ne touche jamais aux murs."""
    rng = random.Random(graine)
    meilleure = depart
    err_min = erreur(depart)
    for _ in range(essais):
        candidat = Physique(**{
            f.name: round(rng.uniform(*BORNES[f.name]), 3) for f in fields(Physique)
        })
        e = erreur(candidat)
        # on garde la meilleure ; a egalite, la plus proche du depart (changement minimal)
        if e < err_min:
            meilleure, err_min = candidat, e
        if err_min == 0:
            # affiner : on ne cherche plus, on a un monde coherent
            break
    return meilleure


def _montrer(phys: Physique, titre: str):
    print(f"\n{titre}")
    for f in fields(Physique):
        print(f"   {f.name:16s} = {getattr(phys, f.name)}")


def main():
    print("=" * 68)
    print("NEOGEN - LE MONDE APPREND DE SES LIMITES")
    print("=" * 68)

    print("\n--- AVANT : physique par defaut, erreur =", erreur(DEFAUT), "---")
    for l in diagnostic(DEFAUT):
        print(l)

    print("\n[APPRENTISSAGE] le monde ajuste ses lois pour coller a la verite...")
    print("                (il ne touche QU'aux seuils ; les murs graves sont intouchables)")
    apprise = apprendre(DEFAUT)

    print("\n--- APRES : physique apprise, erreur =", erreur(apprise), "---")
    for l in diagnostic(apprise):
        print(l)

    _montrer(DEFAUT, "Physique de depart :")
    _montrer(apprise, "Physique apprise :")

    print("\n--- Ce qui a change, et ce qui n'a PAS pu changer ---")
    for f in fields(Physique):
        av, ap = getattr(DEFAUT, f.name), getattr(apprise, f.name)
        if av != ap:
            print(f"   APPRIS  {f.name} : {av} -> {ap}")
    print("   GRAVE   conservation de la masse : intouchee")
    print("   GRAVE   integrite de nature (idee != matiere) : intouchee")

    print("\n" + "=" * 68)
    if erreur(apprise) == 0:
        print("Le monde a appris de ses limites. eau+huile se separe, eau+eau ne s'erode")
        print("plus, et eau+feu / confiance+doute restent justes. Sans coder une seule paire.")
    else:
        print("Le monde s'est ameliore mais reste imparfait : il faut enrichir les lois.")
    print("=" * 68)


if __name__ == "__main__":
    main()

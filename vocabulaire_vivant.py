"""
NEOGEN - Le grand vertige : l'IA propose une brique neuve

Quand le vocabulaire de briques (conditions + effets) ne suffit pas a combler
un manque, l'invention echoue. Alors on demande a Claude de proposer une BRIQUE
NEUVE - mais pas du code arbitraire : il remplit une GRAMMAIRE STRUCTUREE (quelle
cible, quelles modifications de proprietes) qu'on interprete nous-memes. Le
vocabulaire du monde grandit, sans jamais executer de code non controle.

Puis le monde reprend l'invention avec son vocabulaire elargi, et la membrane
valide la loi qui en sort.

Scenario : "sel + eau -> DISSOLUTION". Aucun effet existant ne dissout. Claude
propose l'effet 'dissoudre'. Le monde invente alors la loi tout seul.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import replace

import anthropic
from pydantic import BaseModel, Field

from matiere import Matiere
from invention import EFFETS, inventer          # EFFETS est mutable et partage
from generator import _load_api_key, MODEL


def _clamp(x, lo, hi):
    return round(max(lo, min(hi, x)), 3)


# ---------------------------------------------------------------------------
# GRAMMAIRE STRUCTUREE d'une brique-effet (ce que Claude a le droit de proposer)
# ---------------------------------------------------------------------------
SELECTEURS = {
    "plus_cohesive": lambda a, b: a if a.cohesion >= b.cohesion else b,
    "moins_cohesive": lambda a, b: a if a.cohesion <= b.cohesion else b,
    "plus_rigide":   lambda a, b: a if a.fluidite <= b.fluidite else b,
    "plus_fluide":   lambda a, b: a if a.fluidite >= b.fluidite else b,
    "plus_dense":    lambda a, b: a if a.densite >= b.densite else b,
    "plus_chaude":   lambda a, b: a if a.temperature >= b.temperature else b,
    "plus_froide":   lambda a, b: a if a.temperature <= b.temperature else b,
}


class BriqueEffet(BaseModel):
    nom: str = Field(description="nom court de l'effet, ex 'dissoudre'")
    tag: str = Field(description="etiquette du comportement, en MAJUSCULES, ex 'DISSOLUTION'")
    cible: str = Field(description="qui subit l'effet : " + " | ".join(SELECTEURS))
    d_densite: float = Field(0, ge=-1, le=1, description="variation de densite de la cible")
    d_fluidite: float = Field(0, ge=-1, le=1)
    d_temperature: float = Field(0, ge=-1, le=1)
    d_cohesion: float = Field(0, ge=-1, le=1)
    d_charge: float = Field(0, ge=-1, le=1)
    justification: str


SYSTEME = (
    "Le monde a une physique du sens : chaque matiere a densite, fluidite, temperature, "
    "cohesion (0..1) et charge (-1..1). On te demande d'inventer une BRIQUE D'EFFET neuve "
    "pour produire un comportement qui manque au monde.\n"
    "Tu choisis QUI subit l'effet (cible) parmi : " + ", ".join(SELECTEURS) + ".\n"
    "Puis tu donnes les variations (deltas) appliquees a cette cible pour incarner le "
    "comportement demande. Exemple : dissoudre = la matiere cohesive perd sa cohesion et "
    "devient fluide (d_cohesion tres negatif, d_fluidite positif).\n"
    "Reste fidele a l'intuition du comportement demande."
)


def demander_brique(comportement: str, client) -> BriqueEffet:
    resp = client.messages.parse(
        model=MODEL, max_tokens=6000, thinking={"type": "adaptive"},
        system=SYSTEME,
        messages=[{"role": "user", "content": f"Comportement manquant : {comportement}"}],
        output_format=BriqueEffet,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Claude n'a pas pu proposer de brique")
    return resp.parsed_output


def compiler_brique(brique: BriqueEffet):
    """Interprete la grammaire en une fonction d'effet. Aucun code arbitraire execute."""
    selecteur = SELECTEURS.get(brique.cible, SELECTEURS["plus_cohesive"])

    def effet(a, b):
        cible = selecteur(a, b)
        produit = replace(cible, nom=f"{cible.nom}_{brique.tag.lower()}",
                          densite=_clamp(cible.densite + brique.d_densite, 0, 1),
                          fluidite=_clamp(cible.fluidite + brique.d_fluidite, 0, 1),
                          temperature=_clamp(cible.temperature + brique.d_temperature, 0, 1),
                          cohesion=_clamp(cible.cohesion + brique.d_cohesion, 0, 1),
                          charge=_clamp(cible.charge + brique.d_charge, -1, 1))
        return produit, brique.tag
    return effet


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("NEOGEN - LE GRAND VERTIGE : l'IA propose une brique neuve")
    print("=" * 72)

    eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
    huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
    sel = Matiere("sel", 0.7, 0.05, 0.2, 0.9, 0.1)
    sucre = Matiere("sucre", 0.65, 0.05, 0.2, 0.85, 0.0)
    eau2 = replace(eau, nom="eau2")

    interdits = [(eau, huile), (eau, eau2)]   # cas connus : la loi ne doit pas les toucher

    print(f"\nVocabulaire d'effets au depart : {list(EFFETS.keys())}")
    print("Le reel impose : sel + eau -> DISSOLUTION.")

    print("\n[1] Le monde tente d'inventer avec son vocabulaire ACTUEL...")
    loi = inventer((sel, eau), "DISSOLUTION", interdits)
    if loi is None:
        print("    [ECHEC] aucun effet ne produit DISSOLUTION. Vocabulaire insuffisant.")
    else:
        print("    (trouve, pas besoin de l'IA)")
        return

    print("\n[2] Le monde demande une BRIQUE NEUVE a Claude (vrai appel " + MODEL + ")...")
    client = anthropic.Anthropic(api_key=_load_api_key())
    brique = demander_brique("dissoudre : une matiere fluide dissout une matiere cohesive, "
                             "qui perd sa cohesion et se fond dans le liquide -> tag DISSOLUTION",
                             client)
    print(f"    Claude propose la brique :")
    print(f"      nom='{brique.nom}' tag='{brique.tag}' cible='{brique.cible}'")
    print(f"      deltas: dens={brique.d_densite} flux={brique.d_fluidite} "
          f"temp={brique.d_temperature} cohe={brique.d_cohesion} charge={brique.d_charge}")
    print(f"      justification : {brique.justification}")

    # On l'interprete (pas de code arbitraire) et on l'ajoute au vocabulaire
    EFFETS[brique.nom] = compiler_brique(brique)
    print(f"\n    Vocabulaire d'effets ELARGI : {list(EFFETS.keys())}")

    print("\n[3] Le monde reprend l'invention avec son vocabulaire elargi...")
    loi = inventer((sel, eau), brique.tag, interdits)
    if loi is None:
        print("    [ECHEC] meme avec la brique, aucune loi ne tient (membrane).")
        return
    print(f"    LOI INVENTEE : {loi.humain()}")
    casse = [(x, y) for (x, y) in interdits if loi.se_declenche(x, y)]
    print(f"    [MEMBRANE] se declenche sur cas connus ? {'OUI -> refus' if casse else 'NON -> validee'}")

    print("\n[4] On l'applique, et elle generalise :")
    for nom, a, b in [("sel + eau", sel, eau), ("sucre + eau", sucre, eau)]:
        prod, tag = loi.appliquer(a, b)
        print(f"    {nom:14s} -> {tag} : {prod}")

    print("\n" + "=" * 72)
    print("Le monde a elargi son PROPRE vocabulaire : il manquait un effet, l'IA l'a")
    print("propose dans une grammaire controlee, le monde l'a integre et a invente la loi.")
    print("=" * 72)


if __name__ == "__main__":
    main()

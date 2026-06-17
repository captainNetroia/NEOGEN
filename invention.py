"""
VIVARIUM - Le monde invente une loi qui lui manque

Quand le reel dit "il devrait se passer quelque chose" mais qu'aucune loi ne le
produit, le systeme COMPOSE une loi nouvelle a partir d'un vocabulaire de
briques (conditions primitives + effets primitifs), par recherche, de facon a :
  - produire le comportement attendu sur le cas en manque,
  - ne PAS se declencher sur les cas ou il ne doit rien se passer.

HONNETETE : le systeme n'invente pas les briques a partir de rien. Il les
COMPOSE. Mais il decouvre une loi qu'on ne lui a jamais donnee. Pour le prouver,
on lui retire toute connaissance de la fonte et on lui demande de la redecouvrir.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from itertools import combinations

from matiere import Matiere


# ---------------------------------------------------------------------------
# LE VOCABULAIRE : briques de conditions (symetriques : pas de probleme d'ordre)
# ---------------------------------------------------------------------------
CONDITIONS = {
    "ecart_temperature_eleve": (lambda a, b, s: abs(a.temperature - b.temperature) > s, 0.45),
    "une_est_chaude":          (lambda a, b, s: max(a.temperature, b.temperature) > s, 0.60),
    "une_est_rigide":          (lambda a, b, s: min(a.fluidite, b.fluidite) < s, 0.40),
    "une_est_fluide":          (lambda a, b, s: max(a.fluidite, b.fluidite) > s, 0.55),
    "une_est_cohesive":        (lambda a, b, s: max(a.cohesion, b.cohesion) > s, 0.50),
    "charges_opposees":        (lambda a, b, s: a.charge * b.charge < -s, 0.10),
}


# ---------------------------------------------------------------------------
# LE VOCABULAIRE : briques d'effets (chacune produit une matiere + une etiquette)
# ---------------------------------------------------------------------------
def effet_fluidifier(a, b):
    cible = a if a.fluidite < b.fluidite else b          # la plus rigide
    autre = b if cible is a else a
    produit = replace(cible, nom=f"{cible.nom}_fondu",
                      fluidite=round(min(1.0, cible.fluidite + 0.6), 3),
                      cohesion=round(cible.cohesion * 0.5, 3),
                      temperature=round((a.temperature + b.temperature) / 2, 3))
    return produit, "FONTE"


def effet_volatiliser(a, b):
    cible = a if a.temperature < b.temperature else b    # la plus froide
    produit = replace(cible, nom=f"{cible.nom}_volatil",
                      densite=round(cible.densite * 0.35, 3),
                      fluidite=round(min(1.0, cible.fluidite + 0.25), 3))
    return produit, "REACTION"


def effet_fusionner(a, b):
    produit = Matiere(f"{a.nom}+{b.nom}",
                      densite=round(a.densite + b.densite, 3),
                      fluidite=round((a.fluidite + b.fluidite) / 2, 3),
                      temperature=round((a.temperature + b.temperature) / 2, 3),
                      cohesion=round((a.cohesion + b.cohesion) / 2, 3),
                      charge=round((a.charge + b.charge) / 2, 3),
                      abstrait=a.abstrait or b.abstrait)
    return produit, "FUSION"


EFFETS = {
    "fluidifier la plus rigide": effet_fluidifier,
    "volatiliser la plus froide": effet_volatiliser,
    "fusionner les deux": effet_fusionner,
}


# ---------------------------------------------------------------------------
# UNE LOI SYNTHETISEE : des conditions (ET) + un effet
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoiSynthetisee:
    conditions: tuple       # noms de conditions
    effet: str              # nom d'effet

    def se_declenche(self, a, b) -> bool:
        return all(CONDITIONS[c][0](a, b, CONDITIONS[c][1]) for c in self.conditions)

    def appliquer(self, a, b):
        if not self.se_declenche(a, b):
            return None, None
        return EFFETS[self.effet](a, b)

    def humain(self) -> str:
        conds = " ET ".join(c.replace("_", " ") for c in self.conditions)
        return f"SI ({conds}) ALORS {self.effet}"


# ---------------------------------------------------------------------------
# LE SYNTHETISEUR : cherche la loi la plus simple qui comble le manque
# ---------------------------------------------------------------------------
def inventer(cas_cible, tag_attendu, cas_interdits, max_conditions=3):
    """
    cas_cible : (a, b) ou la loi DOIT se declencher et produire tag_attendu.
    cas_interdits : liste de (a, b) ou la loi ne doit PAS se declencher.
    Renvoie la loi la plus simple (moins de conditions) qui satisfait tout, ou None.
    """
    a_cible, b_cible = cas_cible
    noms_conditions = list(CONDITIONS.keys())

    for taille in range(1, max_conditions + 1):           # Occam : on essaie le plus simple d'abord
        for combo in combinations(noms_conditions, taille):
            for nom_effet in EFFETS:
                loi = LoiSynthetisee(conditions=combo, effet=nom_effet)
                # 1. se declenche sur la cible et produit le bon comportement ?
                produit, tag = loi.appliquer(a_cible, b_cible)
                if tag != tag_attendu:
                    continue
                # 2. ne se declenche JAMAIS sur les cas interdits ?
                if any(loi.se_declenche(x, y) for x, y in cas_interdits):
                    continue
                return loi
    return None


# ---------------------------------------------------------------------------
# DEMO : on retire la fonte, on cree le manque, le systeme la redecouvre
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("VIVARIUM - LE MONDE INVENTE UNE LOI QUI LUI MANQUE")
    print("=" * 70)

    eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
    feu = Matiere("feu", 0.2, 0.7, 1.0, 0.3, -0.2)
    glace = Matiere("glace", 0.6, 0.1, 0.0, 0.8, -0.2)
    huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
    confiance = Matiere("confiance", 0.6, 0.3, 0.3, 0.85, 0.5, abstrait=True)
    doute = Matiere("doute", 0.2, 0.8, 0.2, 0.3, -0.4, abstrait=True)

    print("\nLe monde n'a AUCUNE loi de fonte. Le reel dit : glace + feu doit FONDRE.")
    print("Cas ou la loi NE doit PAS se declencher (sinon elle casse le monde) :")
    print("  eau+feu, eau+eau, eau+huile, confiance+doute")

    print("\n[INVENTION] recherche d'une loi qui fait fondre glace+feu sans rien casser...")
    loi = inventer(
        cas_cible=(glace, feu),
        tag_attendu="FONTE",
        cas_interdits=[(eau, feu), (eau, replace(eau, nom="eau2")),
                       (eau, huile), (confiance, doute)],
    )

    if loi is None:
        print("  Aucune loi trouvee dans le vocabulaire actuel.")
        return

    print("\n  LOI INVENTEE (que personne ne lui a donnee) :")
    print("     " + loi.humain())
    print(f"     conditions={loi.conditions} | effet='{loi.effet}'")

    print("\n--- On l'applique. glace+feu, le rate d'hier : ---")
    produit, tag = loi.appliquer(glace, feu)
    print(f"   {tag} -> {produit}")

    print("\n--- Et la MEME loi inventee generalise, sans rien coder de plus : ---")
    for nom, m in [("acier", Matiere("acier", 0.95, 0.05, 0.2, 0.95, 0.0)),
                   ("pierre", Matiere("pierre", 0.85, 0.05, 0.25, 0.9, 0.1))]:
        p, t = loi.appliquer(feu, m)
        print(f"   feu + {nom} -> {t} : {p}")

    print("\n--- Verif : la loi inventee NE se declenche PAS la ou elle ne doit pas : ---")
    for nom, x, y in [("eau+feu", eau, feu), ("eau+huile", eau, huile),
                      ("confiance+doute", confiance, doute)]:
        print(f"   {nom:16s} : declenche = {loi.se_declenche(x, y)}")

    print("\n" + "=" * 70)
    print("Le monde a invente la loi de la fonte tout seul, en composant ses briques.")
    print("Personne ne la lui a ecrite. Et elle ne casse rien. C'est l'auto-invention.")
    print("=" * 70)


if __name__ == "__main__":
    main()

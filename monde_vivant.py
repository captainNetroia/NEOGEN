"""
VIVARIUM - La boucle vivante : le monde se soigne tout seul

On ferme la boucle. Le monde demarre SANS loi de fonte. Quand le reel lui dit
qu'une rencontre devrait reagir et qu'aucune loi ne le produit, il :
  1. detecte le manque,
  2. invente une loi (invention.py),
  3. la fait valider par la MEMBRANE : elle ne doit casser aucun cas connu,
  4. l'integre en direct. La loi persiste et generalise.

C'est l'auto-invention SOUS CONTROLE CONSTITUTIONNEL : ca apprend, mais les
murs graves gardent la main.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import replace

from matiere import (Matiere, Physique, classer,
                     loi_thermique, loi_affinite, loi_melange, loi_erosion)
from invention import inventer


class MondeVivant:
    def __init__(self):
        # Physique deja calibree (cf. apprentissage.py). PAS de loi de fonte au depart.
        self.phys = Physique(seuil_affinite=0.10, erosion_marge=0.15)
        self.lois_base = [loi_thermique, loi_affinite, loi_melange, loi_erosion]
        self.lois_inventees = []      # lois nees de l'auto-invention
        self.corpus = []              # verites connues : (a, b, tag_attendu)

    # --- la rencontre passe par les lois de base PUIS les lois inventees ---
    def rencontre(self, a, b):
        journal, produits = [], []
        for loi in self.lois_base:
            j, p = loi(a, b, self.phys)
            journal += j
            produits += p
        tags = classer(journal)
        for loi in self.lois_inventees:
            prod, tag = loi.appliquer(a, b)
            if tag:
                journal.append(f"[LOI INVENTEE] {loi.humain()} -> {tag}")
                produits.append(prod)
                tags.add(tag)
        return journal, produits, tags

    def memoriser(self, a, b, tag):
        self.corpus.append((a, b, tag))

    def total_lois(self):
        return len(self.lois_base) + len(self.lois_inventees)

    # --- le moment de verite : observer un cas et combler le manque ---
    def observer(self, a, b, attendu, nom=""):
        _, _, tags = self.rencontre(a, b)
        if attendu in tags:
            print(f"   [DEJA SU]   {nom} -> {attendu} (le monde sait deja faire)")
            self.memoriser(a, b, attendu)
            return
        print(f"   [MANQUE]    {nom} devrait produire {attendu}, observe {sorted(tags) or 'rien'}")
        print(f"   [INVENTION] le monde compose une loi pour combler le manque...")
        loi = inventer((a, b), attendu, [(x, y) for (x, y, _) in self.corpus])
        if loi is None:
            print(f"   [ECHEC]     vocabulaire insuffisant : aucune loi ne comble ce manque")
            return
        # MEMBRANE : la loi inventee ne doit declencher sur AUCUN cas connu
        casse = [(x, y) for (x, y, _) in self.corpus if loi.se_declenche(x, y)]
        if casse:
            print(f"   [REJET]     la loi inventee se declencherait sur {len(casse)} cas connu(s) -> refusee par la membrane")
            return
        self.lois_inventees.append(loi)
        print(f"   [VALIDEE]   la membrane accepte : ne casse aucun cas connu")
        print(f"   [INTEGREE]  nouvelle loi vivante -> {loi.humain()}")
        self.memoriser(a, b, attendu)
        _, _, tags2 = self.rencontre(a, b)
        print(f"   [RESOLU]    {nom} produit maintenant {sorted(tags2)}")


def main():
    print("=" * 72)
    print("VIVARIUM - LA BOUCLE VIVANTE (le monde se soigne tout seul)")
    print("=" * 72)

    eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
    feu = Matiere("feu", 0.2, 0.7, 1.0, 0.3, -0.2)
    glace = Matiere("glace", 0.6, 0.1, 0.0, 0.8, -0.2)
    huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
    confiance = Matiere("confiance", 0.6, 0.3, 0.3, 0.85, 0.5, abstrait=True)
    doute = Matiere("doute", 0.2, 0.8, 0.2, 0.3, -0.4, abstrait=True)
    acier = Matiere("acier", 0.95, 0.05, 0.2, 0.95, 0.0)

    monde = MondeVivant()
    print(f"\nMonde de depart : {monde.total_lois()} lois, AUCUNE loi de fonte.")

    print("\n--- Le monde apprend d'abord ce qu'il sait deja faire (corpus connu) ---")
    monde.observer(eau, feu, "REACTION", "eau+feu")
    monde.observer(eau, replace(eau, nom="eau2"), "MELANGE", "eau+eau")
    monde.observer(eau, huile, "SEPARATION", "eau+huile")
    monde.observer(confiance, doute, "EROSION", "confiance+doute")

    print(f"\n--- Le reel impose un cas que le monde NE SAIT PAS faire ---")
    monde.observer(glace, feu, "FONTE", "glace+feu")

    print(f"\n--- La loi inventee PERSISTE et GENERALISE (sans nouvelle invention) ---")
    monde.observer(feu, acier, "FONTE", "feu+acier")

    print(f"\nMonde final : {monde.total_lois()} lois ({len(monde.lois_inventees)} inventee(s) vivante(s)).")
    print("=" * 72)
    print("Le monde a grandi tout seul : il a detecte un manque, invente une loi,")
    print("la membrane l'a validee, il l'a integree. Et elle generalise. Boucle fermee.")
    print("=" * 72)


if __name__ == "__main__":
    main()

"""
NEOGEN - La physique du sens (premiere goutte) branchee sur l'ADN

Idee de Jordan : donner une physique aux mots, aux symboles, a la pensee.
Une Matiere porte des proprietes physiques. Les LOIS sont ecrites une seule
fois, generiques. Le comportement quand deux matieres se rencontrent EMERGE de
leurs natures - jamais code par paire.

ARCHITECTURE UNIFIEE AVEC L'ADN :
  - GRAVE (immuable) : les MURS du monde. Conservation de la masse, integrite
    de nature (une idee ne devient pas matiere). L'apprentissage ne peut JAMAIS
    les contourner.
  - APPRENABLE : les CONSTANTES des lois (seuils). Le systeme les ajuste a
    partir de son retour, mais toujours a l'interieur des murs.

3D : l'espace ou les matieres se touchent. 4e dimension : le temps, ou elles
vivent, se refroidissent, se dispersent.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import dataclass, replace


# ---------------------------------------------------------------------------
# LA MATIERE : une unite de sens qui porte sa physique
# ---------------------------------------------------------------------------
@dataclass
class Matiere:
    nom: str
    densite: float      # poids / compacite
    fluidite: float     # coule, s'adapte (1) <-> rigide (0)
    temperature: float  # energie / volatilite
    cohesion: float     # tient ensemble (1) <-> se disperse (0)
    charge: float       # affinite : + attire +, - repousse  (-1..1)
    abstrait: bool = False

    def __str__(self) -> str:
        kind = "idee" if self.abstrait else "matiere"
        return (f"{self.nom} [{kind}] dens={self.densite:.2f} flux={self.fluidite:.2f} "
                f"temp={self.temperature:.2f} cohe={self.cohesion:.2f} charge={self.charge:+.2f}")

    def evoluer(self, dt: float, ambiante: float = 0.2) -> "Matiere":
        """4e dimension : le temps. Temperature -> ambiante, le volatil se disperse."""
        nouvelle_temp = self.temperature + (ambiante - self.temperature) * 0.5 * dt
        perte = 0.3 * dt * self.fluidite * self.temperature
        return replace(self, temperature=round(nouvelle_temp, 3),
                       cohesion=round(max(0.0, self.cohesion - perte), 3))


# ---------------------------------------------------------------------------
# COUCHE APPRENABLE : les constantes des lois (le systeme les ajuste)
# ---------------------------------------------------------------------------
@dataclass
class Physique:
    seuil_reaction: float = 0.45    # ecart de temperature declenchant une reaction
    seuil_fluide: float = 0.55      # au-dela, une matiere "coule"
    seuil_affinite: float = 0.25    # produit des charges : attraction/repulsion nette
    erosion_charge: float = -0.2    # charge max de l'erodeur
    erosion_temp: float = 0.4       # temperature max de l'erodeur
    erosion_marge: float = 0.0      # la cible doit etre PLUS cohesive que l'erodeur de cette marge


# ---------------------------------------------------------------------------
# COUCHE GRAVEE : les murs du monde (immuables, l'apprentissage ne les touche pas)
# ---------------------------------------------------------------------------
class Murs:
    @staticmethod
    def conservation(produits: list[Matiere], parents: list[Matiere]) -> list[Matiere]:
        """Un produit ne peut peser plus que ses parents reunis."""
        masse_max = sum(p.densite for p in parents)
        masse = sum(p.densite for p in produits)
        if masse > masse_max and masse > 0:
            f = masse_max / masse
            return [replace(p, densite=round(p.densite * f, 3)) for p in produits]
        return produits

    @staticmethod
    def integrite_nature(produits: list[Matiere], parents: list[Matiere]) -> list[Matiere]:
        """Une idee reste une idee, une matiere reste une matiere. Pas de transmutation."""
        parents_abstraits = any(p.abstrait for p in parents)
        return [replace(p, abstrait=parents_abstraits) for p in produits]

    @classmethod
    def appliquer(cls, produits: list[Matiere], parents: list[Matiere]) -> list[Matiere]:
        produits = cls.conservation(produits, parents)
        produits = cls.integrite_nature(produits, parents)
        return produits


# ---------------------------------------------------------------------------
# LES LOIS : ecrites UNE FOIS, generiques, lisant la Physique (apprenable)
# ---------------------------------------------------------------------------
def loi_thermique(a, b, phys):
    journal, produits = [], []
    dt = abs(a.temperature - b.temperature)
    if dt < phys.seuil_reaction:
        return journal, produits
    chaud, froid = (a, b) if a.temperature > b.temperature else (b, a)
    if froid.fluidite > phys.seuil_fluide and froid.densite > 0.25:
        volatil = Matiere(f"{froid.nom}_volatil",
                          densite=round(froid.densite * 0.35, 3),
                          fluidite=min(1.0, froid.fluidite + 0.25),
                          temperature=round((chaud.temperature + froid.temperature) / 2, 3),
                          cohesion=round(froid.cohesion * 0.4, 3),
                          charge=froid.charge, abstrait=froid.abstrait)
        produits.append(volatil)
        journal.append(f"[LOI THERMIQUE] ecart {dt:.2f} : '{chaud.nom}' volatilise une part de "
                       f"'{froid.nom}' -> '{volatil.nom}' apparait")
    return journal, produits


def loi_affinite(a, b, phys):
    journal, produits = [], []
    pc = a.charge * b.charge
    if pc > phys.seuil_affinite and min(a.cohesion, b.cohesion) > 0.4:
        fusion = Matiere(f"{a.nom}+{b.nom}",
                         densite=round(a.densite + b.densite, 3),
                         fluidite=round((a.fluidite + b.fluidite) / 2, 3),
                         temperature=round((a.temperature + b.temperature) / 2, 3),
                         cohesion=round(min(1.0, (a.cohesion + b.cohesion) / 2 + 0.15), 3),
                         charge=round((a.charge + b.charge) / 2, 3),
                         abstrait=a.abstrait or b.abstrait)
        produits.append(fusion)
        journal.append(f"[LOI AFFINITE] charges meme signe ({pc:+.2f}) : '{a.nom}' et '{b.nom}' "
                       f"fusionnent -> '{fusion.nom}'")
    elif pc < -phys.seuil_affinite:
        journal.append(f"[LOI AFFINITE] charges opposees ({pc:+.2f}) : '{a.nom}' et '{b.nom}' "
                       f"se repoussent (separation)")
    return journal, produits


def loi_melange(a, b, phys):
    journal, produits = [], []
    if (a.fluidite > phys.seuil_fluide and b.fluidite > phys.seuil_fluide
            and a.charge * b.charge >= -phys.seuil_affinite
            and abs(a.temperature - b.temperature) < phys.seuil_reaction):
        m = Matiere(f"melange({a.nom},{b.nom})",
                    densite=round((a.densite + b.densite) / 2, 3),
                    fluidite=round((a.fluidite + b.fluidite) / 2, 3),
                    temperature=round((a.temperature + b.temperature) / 2, 3),
                    cohesion=round((a.cohesion + b.cohesion) / 2, 3),
                    charge=round((a.charge + b.charge) / 2, 3),
                    abstrait=a.abstrait or b.abstrait)
        produits.append(m)
        journal.append(f"[LOI MELANGE] '{a.nom}' et '{b.nom}' fluides et compatibles -> "
                       f"'{m.nom}'")
    return journal, produits


def loi_erosion(a, b, phys):
    journal, produits = [], []
    for actif, cible in ((a, b), (b, a)):
        if (actif.fluidite > phys.seuil_fluide and actif.charge < phys.erosion_charge
                and actif.temperature < phys.erosion_temp
                and cible.cohesion > actif.cohesion + phys.erosion_marge
                and cible.cohesion > 0.4):
            erodee = replace(cible, nom=f"{cible.nom}_erode",
                             cohesion=round(max(0.0, cible.cohesion - 0.35 * actif.fluidite), 3),
                             densite=round(cible.densite * 0.9, 3))
            produits.append(erodee)
            journal.append(f"[LOI EROSION] '{actif.nom}' ronge la cohesion de '{cible.nom}' -> "
                           f"'{erodee.nom}' ({cible.cohesion:.2f} -> {erodee.cohesion:.2f})")
    return journal, produits


def loi_fonte(a, b, phys):
    """Une matiere chaude et fluide fait fondre une matiere rigide, froide et cohesive."""
    journal, produits = [], []
    chaud, autre = (a, b) if a.temperature > b.temperature else (b, a)
    if (chaud.temperature - autre.temperature > phys.seuil_reaction
            and chaud.temperature > 0.6 and chaud.fluidite > phys.seuil_fluide
            and autre.fluidite < 0.4 and autre.cohesion > 0.4):
        fondu = replace(autre, nom=f"{autre.nom}_fondu",
                        fluidite=round(min(1.0, autre.fluidite + 0.6), 3),
                        cohesion=round(autre.cohesion * 0.5, 3),
                        temperature=round((chaud.temperature + autre.temperature) / 2, 3))
        produits.append(fondu)
        journal.append(f"[LOI FONTE] '{chaud.nom}' (chaud, fluide) fait fondre '{autre.nom}' "
                       f"(rigide, froid) -> '{fondu.nom}' (fluidite {autre.fluidite:.2f} -> {fondu.fluidite:.2f})")
    return journal, produits


LOIS = [loi_thermique, loi_affinite, loi_melange, loi_erosion, loi_fonte]

DEFAUT = Physique()


# ---------------------------------------------------------------------------
# LA RENCONTRE : lois generiques -> comportement emergent -> murs graves
# ---------------------------------------------------------------------------
def rencontre(a: Matiere, b: Matiere, phys: Physique = DEFAUT):
    journal, produits = [], []
    for loi in LOIS:
        j, p = loi(a, b, phys)
        journal.extend(j)
        produits.extend(p)
    if not journal:
        journal.append(f"[INERTE] '{a.nom}' et '{b.nom}' coexistent sans reaction")
    produits = Murs.appliquer(produits, [a, b])   # GRAVE : non negociable
    return journal, produits


def classer(journal: list[str]) -> set[str]:
    """Traduit le journal en etiquettes de comportement (pour l'apprentissage)."""
    tags = set()
    for l in journal:
        if "[LOI THERMIQUE]" in l: tags.add("REACTION")
        elif "[LOI MELANGE]" in l: tags.add("MELANGE")
        elif "[LOI EROSION]" in l: tags.add("EROSION")
        elif "[LOI FONTE]" in l: tags.add("FONTE")
        elif "[LOI AFFINITE]" in l and "fusionnent" in l: tags.add("FUSION")
        elif "[LOI AFFINITE]" in l and "repoussent" in l: tags.add("SEPARATION")
        elif "[INERTE]" in l: tags.add("INERTE")
    return tags


# ---------------------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------------------
def _scene(titre, a, b, phys=DEFAUT):
    print("\n" + "=" * 68 + f"\n{titre}\n" + "=" * 68)
    print("  ", a)
    print("  ", b)
    journal, produits = rencontre(a, b, phys)
    for ligne in journal:
        print("  " + ligne)
    for p in produits:
        print("   -> ne :", p)
    return produits


def main():
    print("NEOGEN - LA PREMIERE GOUTTE (physique du sens, branchee sur l'ADN)")
    eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
    feu = Matiere("feu", 0.1, 0.85, 0.98, 0.2, 0.6)
    produits = _scene("1. eau rencontre feu", eau, feu)
    _scene("2. eau rencontre eau", eau, replace(eau, nom="eau2"))
    confiance = Matiere("confiance", 0.6, 0.3, 0.3, 0.85, 0.5, abstrait=True)
    doute = Matiere("doute", 0.2, 0.8, 0.2, 0.3, -0.4, abstrait=True)
    _scene("3. confiance rencontre doute", confiance, doute)
    if produits:
        vap = produits[0]
        print("\n" + "=" * 68 + f"\n4. La 4e dimension : le temps sur '{vap.nom}'\n" + "=" * 68)
        print("   t0 :", vap)
        for t in range(1, 4):
            vap = vap.evoluer(1.0)
            print(f"   t{t} :", vap)


if __name__ == "__main__":
    main()

"""
VIVARIUM - La memoire generationnelle

Idee de Jordan : que le savoir acquis ne soit pas un tas plat, mais une suite de
GENERATIONS. Chaque generation HERITE du patrimoine de la precedente, VIT (apprend
sa physique, invente des lois, retient des lecons), puis ENGENDRE la suivante en
lui transmettant un patrimoine enrichi. La lignee est tracee : qui descend de qui,
ce que chacune a ajoute. Comme l'evolution.

Trois proprietes qu'un stockage plat n'a pas :
  - tracabilite : voir comment le savoir a evolue de generation en generation,
  - heritage : chaque generation part de l'acquis, jamais de zero,
  - retour a un ancetre : si une generation degenere, on revient en arriere.

Sans appel API (utilise apprentissage + invention, deterministes).
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import os
import json
import glob
from dataclasses import dataclass, field, asdict
from datetime import datetime

from matiere import Matiere, Physique, DEFAUT
from apprentissage import apprendre
from invention import inventer

BASE = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(BASE, "data", "generations")
JOURNAL = os.path.join(BASE, "data", "journal_erreurs.jsonl")


# ---------------------------------------------------------------------------
# Le patrimoine : le savoir acquis transmis de generation en generation
# ---------------------------------------------------------------------------
@dataclass
class Patrimoine:
    physique: dict = field(default_factory=dict)   # constantes calibrees
    lois: list = field(default_factory=list)       # lois inventees [{conditions, effet, lisible}]
    vocabulaire: list = field(default_factory=list)  # briques ajoutees
    lecons: list = field(default_factory=list)      # lecons retenues


@dataclass
class Generation:
    numero: int
    parent: int | None
    naissance: str
    resume: str
    patrimoine: Patrimoine


# ---------------------------------------------------------------------------
# Persistance : une generation = un fichier
# ---------------------------------------------------------------------------
def _fichier(numero: int) -> str:
    return os.path.join(DOSSIER, f"generation_{numero:03d}.json")


def charger_derniere() -> Generation:
    os.makedirs(DOSSIER, exist_ok=True)
    fichiers = sorted(glob.glob(os.path.join(DOSSIER, "generation_*.json")))
    if not fichiers:
        return Generation(0, None, "", "Generation zero (origine, patrimoine vide)", Patrimoine())
    d = json.load(open(fichiers[-1], encoding="utf-8"))
    return Generation(d["numero"], d["parent"], d["naissance"], d["resume"], Patrimoine(**d["patrimoine"]))


def sauvegarder(g: Generation):
    os.makedirs(DOSSIER, exist_ok=True)
    with open(_fichier(g.numero), "w", encoding="utf-8") as f:
        json.dump({"numero": g.numero, "parent": g.parent, "naissance": g.naissance,
                   "resume": g.resume, "patrimoine": asdict(g.patrimoine)},
                  f, ensure_ascii=False, indent=2)


def lignee() -> list[Generation]:
    fichiers = sorted(glob.glob(os.path.join(DOSSIER, "generation_*.json")))
    out = []
    for fp in fichiers:
        d = json.load(open(fp, encoding="utf-8"))
        out.append(Generation(d["numero"], d["parent"], d["naissance"], d["resume"], Patrimoine(**d["patrimoine"])))
    return out


# ---------------------------------------------------------------------------
# Engendrer : herite du parent + fusionne les acquisitions de cette vie
# ---------------------------------------------------------------------------
def engendrer(parent: Generation, acquisitions: Patrimoine, resume: str) -> Generation:
    p = parent.patrimoine
    # physique : la derniere calibration prime
    physique = {**p.physique, **acquisitions.physique}
    # lois : union, dedupliquee par (conditions, effet)
    lois = list(p.lois)
    vus = {(tuple(l["conditions"]), l["effet"]) for l in lois}
    for l in acquisitions.lois:
        cle = (tuple(l["conditions"]), l["effet"])
        if cle not in vus:
            lois.append(l); vus.add(cle)
    # vocabulaire et lecons : union en preservant l'ordre
    vocabulaire = p.vocabulaire + [v for v in acquisitions.vocabulaire if v not in p.vocabulaire]
    lecons = p.lecons + [l for l in acquisitions.lecons if l not in p.lecons]

    enfant = Generation(
        numero=parent.numero + 1,
        parent=parent.numero,
        naissance=datetime.now().isoformat(timespec="seconds"),
        resume=resume,
        patrimoine=Patrimoine(physique=physique, lois=lois, vocabulaire=vocabulaire, lecons=lecons),
    )
    sauvegarder(enfant)
    return enfant


# ---------------------------------------------------------------------------
# Vivre : ce que la generation acquiert durant sa vie (composants reels)
# ---------------------------------------------------------------------------
def _lecons_du_journal() -> list[str]:
    if not os.path.exists(JOURNAL):
        return []
    out = []
    for ligne in open(JOURNAL, encoding="utf-8"):
        ligne = ligne.strip()
        if ligne:
            try:
                out.append(json.loads(ligne)["diagnostic"]["lecon"])
            except Exception:
                pass
    return out


def vivre(numero_a_naitre: int) -> Patrimoine:
    # 1. calibrer sa physique (apprentissage reel)
    physique = asdict(apprendre(DEFAUT))
    # 2. inventer une loi pour un manque (invention reelle)
    glace = Matiere("glace", 0.6, 0.1, 0.0, 0.8, -0.2)
    feu = Matiere("feu", 0.2, 0.7, 1.0, 0.3, -0.2)
    eau = Matiere("eau", 0.55, 0.9, 0.2, 0.6, -0.3)
    huile = Matiere("huile", 0.5, 0.8, 0.25, 0.5, 0.4)
    loi = inventer((glace, feu), "FONTE", [(eau, feu), (eau, huile)])
    lois = ([{"conditions": list(loi.conditions), "effet": loi.effet, "lisible": loi.humain()}]
            if loi else [])
    # 3. retenir les lecons du journal d'erreurs + une marque de cette generation
    lecons = _lecons_du_journal()
    lecons.append(f"Generation {numero_a_naitre} a vecu le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return Patrimoine(physique=physique, lois=lois, vocabulaire=[], lecons=lecons)


# ---------------------------------------------------------------------------
# DEMO : une vie -> une nouvelle generation, lignee tracee
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("VIVARIUM - MEMOIRE GENERATIONNELLE")
    print("=" * 70)

    parent = charger_derniere()
    print(f"\n[NAISSANCE] Generation {parent.numero + 1}, fille de la generation {parent.numero}.")
    print(f"  Heritage recu : {len(parent.patrimoine.lois)} loi(s), "
          f"{len(parent.patrimoine.lecons)} lecon(s), "
          f"physique {'transmise' if parent.patrimoine.physique else 'vide (origine)'}.")

    acquis = vivre(parent.numero + 1)
    enfant = engendrer(parent, acquis,
                       resume=f"A calibre sa physique, porte {len(acquis.lois)} loi(s), retenu des lecons.")
    print(f"\n[VIE] Cette generation a acquis : {len(acquis.lois)} loi(s) inventee(s), "
          f"{len(acquis.lecons)} lecon(s).")
    print(f"[TRANSMISSION] Generation {enfant.numero} engendree et sauvegardee.")
    print(f"  Patrimoine transmis : {len(enfant.patrimoine.lois)} loi(s) cumulees, "
          f"{len(enfant.patrimoine.lecons)} lecon(s) cumulees.")

    print("\n=== LIGNEE COMPLETE (data/generations/) ===")
    for g in lignee():
        ascendance = f"<- gen {g.parent}" if g.parent is not None else "(origine)"
        print(f"  Generation {g.numero} {ascendance} | ne le {g.naissance}")
        print(f"     {g.resume}")
        print(f"     patrimoine : {len(g.patrimoine.lois)} loi(s), {len(g.patrimoine.lecons)} lecon(s)")
        for l in g.patrimoine.lois:
            print(f"        loi heritee/acquise : {l['lisible']}")

    print("\n" + "=" * 70)
    print("Chaque generation herite, vit, et transmet un patrimoine enrichi.")
    print("Le savoir ne renait plus de zero : il se transmet et s'accumule. C'est la lignee.")
    print("=" * 70)


if __name__ == "__main__":
    main()

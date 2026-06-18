"""
VIVARIUM - Evolution a 2 vitesses : l'organisme ameliore ses lois en securite

  VITESSE RAPIDE (live)  : produit avec le GENOME DE LOIS stable (promu). Jamais perturbe.
  VITESSE LENTE (jumeau) : propose une mutation d'une loi -> l'evalue sur un JUMEAU
                           (copie) contre un ETALON IMMUABLE -> ne la PROMEUT au genome
                           que si elle est STRICTEMENT meilleure ET sans REGRESSION.
                           Sinon : rejet + journal.

Le genome complet couvre DEUX couches de lois :
  - les CONSTANTES-LOIS (les seuils de matiere.Physique), jugees contre apprentissage.VERITE,
  - les LOIS SYNTHETISEES (invention.LoiSynthetisee), jugees contre selection.CORPUS.

ANTI-GOODHART (fondation) : l'organisme mesure sa qualite TOUT SEUL, mais contre des
etalons (VERITE + CORPUS) qu'il ne peut PAS reecrire. Autonomie de la mesure, zero
autonomie sur l'etalon. Et il ne touche JAMAIS aux murs graves (conservation, integrite
de nature) : seules les couches APPRENABLES evoluent.

100% offline (recherche + evaluation, aucun appel Claude).
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import os
import json
import random
from dataclasses import asdict

from matiere import Physique, DEFAUT
import apprentissage              # erreur(phys), BORNES (couche apprenable), VERITE (etalon)
import selection                  # CORPUS (etalon immuable)
from invention import LoiSynthetisee

BASE = os.path.dirname(os.path.abspath(__file__))
GENOME_PATH = os.path.join(BASE, "data", "genome_lois.json")
LEDGER = os.path.join(BASE, "data", "evolution.jsonl")

# Vivier de lois candidates que la vitesse lente peut proposer (bonnes ET mauvaises :
# l'etalon trie). Conditions/effets issus du vocabulaire de invention.py.
VIVIER_LOIS = [
    {"conditions": ["ecart_temperature_eleve", "une_est_rigide"], "effet": "fluidifier la plus rigide"},  # bonne : FONTE precise
    {"conditions": ["une_est_cohesive"], "effet": "fusionner les deux"},        # imprecise : declenche trop large
    {"conditions": ["une_est_chaude"], "effet": "volatiliser la plus froide"},  # imprecise : casse glace+feu
    {"conditions": ["charges_opposees"], "effet": "fusionner les deux"},        # rarement utile
]


# ---------------------------------------------------------------------------
# Genome <-> objets
# ---------------------------------------------------------------------------
def _phys(genome) -> Physique:
    return Physique(**genome["physique"])


def _lois(genome) -> list[LoiSynthetisee]:
    return [LoiSynthetisee(tuple(l["conditions"]), l["effet"]) for l in genome["lois"]]


def genome_initial() -> dict:
    return {"version": 1, "physique": asdict(DEFAUT), "lois": []}


def charger_genome() -> dict:
    if os.path.exists(GENOME_PATH):
        with open(GENOME_PATH, encoding="utf-8") as f:
            return json.load(f)
    return genome_initial()


def sauver_genome(genome: dict) -> None:
    os.makedirs(os.path.dirname(GENOME_PATH), exist_ok=True)
    with open(GENOME_PATH, "w", encoding="utf-8") as f:
        json.dump(genome, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Evaluation contre les ETALONS IMMUABLES
# ---------------------------------------------------------------------------
def _eval_lois(lois: list[LoiSynthetisee]):
    """Couverture du CORPUS par les lois, penalisee par les declenchements faux."""
    corrects, faux = set(), 0
    for label, a, b, attendus in selection.CORPUS:
        for loi in lois:
            if loi.se_declenche(a, b):
                _, tag = loi.appliquer(a, b)
                if tag in attendus:
                    corrects.add(label)
                else:
                    faux += 1
    couverture = len(corrects) / len(selection.CORPUS)
    score = round(couverture - 0.10 * faux, 3)
    return score, corrects, faux


def fitness(genome: dict) -> dict:
    err = apprentissage.erreur(_phys(genome))          # 0 = physique parfaite
    score_phys = round(1.0 / (1.0 + err), 3)
    score_lois, corrects, faux = _eval_lois(_lois(genome))
    return {
        "global": round(score_phys + score_lois, 3),
        "phys": score_phys, "err_phys": err,
        "lois": score_lois, "corrects": sorted(corrects), "faux": faux,
    }


def _regression(f_courant: dict, f_cand: dict) -> bool:
    """Une regression = physique qui empire OU un cas de l'etalon perdu."""
    if f_cand["err_phys"] > f_courant["err_phys"]:
        return True
    if not set(f_courant["corrects"]).issubset(set(f_cand["corrects"])):
        return True
    return False


# ---------------------------------------------------------------------------
# Mutation (sur un JUMEAU) : couche apprenable uniquement
# ---------------------------------------------------------------------------
def muter(genome: dict, rng: random.Random):
    jumeau = json.loads(json.dumps(genome))   # copie profonde : on ne touche pas au live
    if rng.random() < 0.5:
        cle = rng.choice(list(apprentissage.BORNES))
        lo, hi = apprentissage.BORNES[cle]
        jumeau["physique"][cle] = round(rng.uniform(lo, hi), 3)
        return jumeau, f"physique:{cle}"
    cand = rng.choice(VIVIER_LOIS)
    if cand not in jumeau["lois"]:
        jumeau["lois"].append(cand)
        return jumeau, f"loi:+({' ET '.join(cand['conditions'])})->{cand['effet']}"
    return jumeau, "loi:doublon (ignore)"


def _ledger(entree: dict):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# VITESSE LENTE : experimente sur le jumeau, promeut au genome si gagnant
# ---------------------------------------------------------------------------
def cycle_lent(genome: dict, essais: int = 60, graine: int = 7):
    from datetime import datetime
    rng = random.Random(graine)
    courant = json.loads(json.dumps(genome))
    f_cur = fitness(courant)
    promotions = []
    for i in range(essais):
        cand, quoi = muter(courant, rng)
        f_cand = fitness(cand)
        reg = _regression(f_cur, f_cand)
        meilleur = f_cand["global"] > f_cur["global"]
        promu = meilleur and not reg
        if promu:
            cand["version"] = courant["version"] + 1
            courant, f_cur = cand, f_cand
            promotions.append({"version": courant["version"], "mutation": quoi,
                               "fitness": f_cand["global"]})
        _ledger({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "essai": i + 1, "mutation": quoi,
            "fitness_candidat": f_cand["global"], "fitness_courant": f_cur["global"],
            "regression": reg, "promu": promu,
        })
    return courant, f_cur, promotions


# ---------------------------------------------------------------------------
# VITESSE RAPIDE : lit le genome stable (jamais perturbe pendant l'experimentation)
# ---------------------------------------------------------------------------
def cycle_rapide(genome: dict):
    """Le live : retourne les lois promues (physique + lois), pretes a produire."""
    return _phys(genome), _lois(genome)


def main():
    print("=" * 72)
    print("VIVARIUM - EVOLUTION A 2 VITESSES (jumeau + etalon immuable)")
    print("=" * 72)

    genome = charger_genome()
    f0 = fitness(genome)
    print(f"\nGENOME DE DEPART v{genome['version']} : fitness global = {f0['global']}")
    print(f"  physique : score {f0['phys']} (erreur {f0['err_phys']}) | lois : score {f0['lois']} "
          f"(couvre {f0['corrects']}, {f0['faux']} faux)")

    print("\n[VITESSE LENTE] le jumeau experimente des mutations contre l'etalon immuable...")
    print("                (promotion SEULEMENT si strictement meilleur ET zero regression)")
    promu, f1, promotions = cycle_lent(genome)

    print(f"\n{len(promotions)} promotion(s) retenue(s) :")
    for p in promotions:
        print(f"   v{p['version']:<2} fitness {p['fitness']:<6} <- {p['mutation']}")
    print(f"\nGENOME PROMU v{promu['version']} : fitness global = {f1['global']}")
    print(f"  physique : score {f1['phys']} (erreur {f1['err_phys']}) | lois : score {f1['lois']} "
          f"(couvre {f1['corrects']}, {f1['faux']} faux)")

    print("\n[VITESSE RAPIDE] le live lit le genome STABLE (inchange pendant l'experimentation) :")
    phys, lois = cycle_rapide(promu)
    print(f"   {len(lois)} loi(s) promue(s) active(s) ; physique a erreur {apprentissage.erreur(phys)}")

    sauver_genome(promu)
    print(f"\n[PERSISTANCE] genome v{promu['version']} sauve. Ledger : data/evolution.jsonl")

    print("\n" + "=" * 72)
    print("L'organisme a ameliore ses lois SANS jamais risquer le live : il experimente sur")
    print("un jumeau, juge contre un etalon qu'il ne peut pas reecrire, et ne promeut que le")
    print("strictement meilleur sans regression. Les murs graves restent intouches.")
    print("=" * 72)


if __name__ == "__main__":
    main()

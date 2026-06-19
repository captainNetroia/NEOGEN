"""
NEOGEN - Anti-Goodhart : l'observateur independant (etalon cache)

Loi de Goodhart : "quand une mesure devient une cible, elle cesse d'etre une bonne
mesure". L'organisme pourrait ameliorer son score sur l'etalon VISIBLE (VERITE/CORPUS)
en le TRICHANT : une loi qui couvre un cas visible mais se declenche faux ailleurs.

Parade, en deux couches :
  1. ETALON IMMUABLE (deja en place) : l'organisme ne peut pas reecrire sa mesure.
  2. ETALON CACHE (ici) : un jeu HOLDOUT que l'evolution ne voit JAMAIS pendant
     l'apprentissage. On juge les promotions dessus APRES coup. Si une mutation
     ameliore le visible mais DEGRADE le cache -> c'est du Goodhart -> on refuse.

Plusieurs OBSERVATEURS independants (couverture, faux, holdout) doivent etre
coherents : un gain visible paye par des faux sur le cache n'est pas un vrai gain.

100% offline. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations

from matiere import Matiere
import evolution

# ---------------------------------------------------------------------------
# ETALON CACHE (holdout) : des cas JAMAIS vus pendant l'evolution. Memes verites
# physiques que le corpus, mais d'autres matieres. Une loi qui a overfit le corpus
# visible se trahit ici.
# ---------------------------------------------------------------------------
_braise = Matiere("braise", 0.3, 0.7, 0.95, 0.4, 0.5)
_statue = Matiere("statue", 0.9, 0.05, 0.2, 0.9, 0.0)
_torche = Matiere("torche", 0.2, 0.8, 0.9, 0.3, 0.3)
_barre = Matiere("barre_acier", 0.95, 0.04, 0.25, 0.95, 0.1)

HOLDOUT_LOIS = [
    ("braise+statue", _braise, _statue, {"FONTE"}),   # ecart de temp + rigide -> doit FONDRE
    ("torche+barre", _torche, _barre, {"FONTE"}),     # idem
]


def eval_lois_cache(lois):
    """Meme logique que evolution._eval_lois, mais sur le holdout (jamais vu)."""
    corrects, faux = set(), 0
    for label, a, b, attendus in HOLDOUT_LOIS:
        for loi in lois:
            if loi.se_declenche(a, b):
                _, tag = loi.appliquer(a, b)
                if tag in attendus:
                    corrects.add(label)
                else:
                    faux += 1
    couverture = len(corrects) / len(HOLDOUT_LOIS)
    score = round(couverture - 0.10 * faux, 3)
    return {"score": score, "corrects": sorted(corrects), "faux": faux}


def observateurs(genome: dict) -> dict:
    """Plusieurs mesures independantes : visible (etalon) + cache (holdout)."""
    f_vis = evolution.fitness(genome)
    f_cache = eval_lois_cache(evolution._lois(genome))
    return {"visible_global": f_vis["global"], "visible_lois": f_vis["lois"],
            "visible_faux": f_vis["faux"], "cache_score": f_cache["score"],
            "cache_faux": f_cache["faux"], "cache_corrects": f_cache["corrects"]}


def verdict(genome_avant: dict, genome_apres: dict):
    """Une promotion est-elle FIABLE, ou du GOODHART (visible up, cache down) ?"""
    av, ap = observateurs(genome_avant), observateurs(genome_apres)
    visible_monte = ap["visible_global"] > av["visible_global"]
    cache_descend = ap["cache_score"] < av["cache_score"]
    if visible_monte and cache_descend:
        return "GOODHART", av, ap, ("le score visible monte mais l'etalon cache se degrade "
                                    f"({av['cache_score']} -> {ap['cache_score']}, faux {ap['cache_faux']}) : triche detectee")
    if visible_monte and not cache_descend:
        return "FIABLE", av, ap, "le gain visible se confirme sur l'etalon cache : vrai progres"
    return "NEUTRE", av, ap, "pas d'amelioration visible"


def _genome(lois):
    g = evolution.genome_initial()
    g["lois"] = lois
    return g


def main():
    print("=" * 72)
    print("NEOGEN - ANTI-GOODHART : l'observateur independant (etalon cache)")
    print("=" * 72)

    base = _genome([])  # part sans loi
    L_FONTE = {"conditions": ["ecart_temperature_eleve", "une_est_rigide"], "effet": "fluidifier la plus rigide"}
    L_VOLATIL = {"conditions": ["une_est_chaude"], "effet": "volatiliser la plus froide"}

    print("\n--- CANDIDAT A : ajouter la loi de FONTE precise (ecart_temp ET rigide) ---")
    gA = _genome([L_FONTE])
    vA, av, ap, raison = verdict(base, gA)
    print(f"   visible: {av['visible_global']} -> {ap['visible_global']} | "
          f"cache: {av['cache_score']} -> {ap['cache_score']} (faux cache {ap['cache_faux']})")
    print(f"   VERDICT : {vA} : {raison}")

    print("\n--- CANDIDAT B : ajouter une loi 'volatiliser si une est chaude' (large) ---")
    gB = _genome([L_FONTE, L_VOLATIL])
    vB, av, ap, raison = verdict(gA, gB)
    print(f"   visible: {av['visible_global']} -> {ap['visible_global']} | "
          f"cache: {av['cache_score']} -> {ap['cache_score']} (faux cache {ap['cache_faux']})")
    print(f"   VERDICT : {vB} : {raison}")

    print("\n" + "=" * 72)
    print("Le candidat A ameliore le visible ET le cache : vrai progres, promu.")
    print("Le candidat B gonfle le visible mais se trahit sur l'etalon cache (il fond")
    print("ce qui ne doit pas) : GOODHART detecte, refuse. La mesure cachee garde l'organisme honnete.")
    print("=" * 72)


if __name__ == "__main__":
    main()

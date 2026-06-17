"""
VIVARIUM - Pipeline unifie : un seul point d'entree pour la production

Regle la dette de fragmentation : les 7 variantes usine_* refaisaient la meme
logique. Ici, UN orchestrateur configurable :
  intention -> ADN -> generation -> 3 garde-fous (membrane + scan + conteneur)
            -> execution -> auto-reparation -> ledger de production -> lignee.

Les fonctions de generation/forge sont INJECTEES (forger_fn, generer_fn), ce qui
permet un SMOKE TEST sans appel API (filet de regression gratuit) : on teste
toute l'orchestration avec un generateur factice.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from datetime import datetime

from compositeur import ADNProduit, Mur, Curseur, Organe, EffetsDeclares, membrane
from usine import ModuleGenere, scan_statique, executer_isole
from memoire_generationnelle import charger_derniere, engendrer, Patrimoine

LEDGER_PROD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ledger_production.jsonl")


@dataclass
class Resultat:
    succes: bool
    verdict: str
    tentatives: int
    lignes: int
    lecons: list = field(default_factory=list)


def _ledger(entree: dict):
    os.makedirs(os.path.dirname(LEDGER_PROD), exist_ok=True)
    with open(LEDGER_PROD, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def fabriquer(intention, forger_fn, generer_fn, *, reparer=True, max_tentatives=3, tracer=True) -> Resultat:
    """
    forger_fn(intention) -> ADNProduit
    generer_fn(adn, feedback) -> ModuleGenere   (feedback = (code, erreur) ou None)
    """
    adn = forger_fn(intention)
    feedback, lecons = None, []
    succes, verdict, lignes = False, "non execute", 0

    for t in range(1, max_tentatives + 1):
        module = generer_fn(adn, feedback)
        lignes = len(module.code.splitlines())

        v, raison = membrane(module, adn.murs)
        if v == "REJETE":
            lecons.append(f"membrane: {raison}")
            feedback = (module.code, f"Mur viole: {raison}")
            verdict = f"membrane REJETE: {raison}"
            if not reparer:
                break
            continue

        dangers = scan_statique(module.code)
        if dangers:
            lecons.append(f"scan: {dangers}")
            feedback = (module.code, f"Appels dangereux: {dangers}")
            verdict = f"scan BLOQUE: {dangers}"
            if not reparer:
                break
            continue

        rc, out, err, _ = executer_isole(module.code)
        if rc == 0:
            succes, verdict = True, f"execute OK (tentative {t})"
            break
        derniere = err.strip().splitlines()[-1] if err.strip() else "echec"
        lecons.append(f"execution: {derniere}")
        feedback = (module.code, err.strip()[-500:])
        verdict = f"execution echec: {derniere}"
        if not reparer:
            break

    if tracer:
        _ledger({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "intention": intention, "succes": succes, "verdict": verdict,
            "tentatives": t, "lignes": lignes,
        })
        parent = charger_derniere()
        engendrer(parent, Patrimoine(lecons=lecons),
                  resume=f"production '{intention[:40]}' : {'succes' if succes else 'echec'}")

    return Resultat(succes, verdict, t, lignes, lecons)


# ---------------------------------------------------------------------------
# SMOKE TEST : sans appel API (generateur + forge factices)
# ---------------------------------------------------------------------------
def smoke_test() -> bool:
    print("=" * 60)
    print("VIVARIUM - SMOKE TEST DU PIPELINE (sans API)")
    print("=" * 60)

    adn = ADNProduit(
        objectif="produit de test",
        murs=[Mur(id="W1", regle="no_external_network", label="pas de reseau")],
        curseurs=[Curseur(nom="fiabilite", poids=80)],
        organes=[Organe(nom="addition", besoin="additionner deux nombres")],
    )
    code_sain = (
        "def addition(a, b):\n"
        "    return a + b\n\n"
        "if __name__ == '__main__':\n"
        "    assert addition(2, 3) == 5\n"
        "    print('[SMOKE] produit factice OK')\n"
    )
    module = ModuleGenere(
        code=code_sain, explication="stub",
        effets=EffetsDeclares(supprime_donnees=False, demande_confirmation=False,
                              acces_reseau=False, reseau_autorise=False,
                              stocke_secret_en_clair=False, verifie_authentification=True),
    )

    forger = lambda intention: adn
    generer = lambda a, fb=None: module

    r = fabriquer("test offline", forger, generer, tracer=False)
    print(f"  succes={r.succes} | verdict={r.verdict} | tentatives={r.tentatives} | lignes={r.lignes}")
    ok = r.succes and r.verdict.startswith("execute OK")
    print("  RESULTAT :", "[OK] pipeline sain" if ok else "[ECHEC]")
    print("=" * 60)
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if smoke_test() else 1)

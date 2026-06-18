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
    code: str = ""
    classement: list = field(default_factory=list)


def _ledger(entree: dict):
    os.makedirs(os.path.dirname(LEDGER_PROD), exist_ok=True)
    with open(LEDGER_PROD, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def fabriquer(intention, forger_fn, generer_fn, *, reparer=True, max_tentatives=3, tracer=True,
              cap=None, volume_nom=None) -> Resultat:
    """
    forger_fn(intention) -> ADNProduit
    generer_fn(adn, feedback) -> ModuleGenere   (feedback = (code, erreur) ou None)
    cap (Capacites) + volume_nom : capacites accordees au produit (persistance...) qui
    configurent le bac a sable. None = produit pur (calcul en memoire, isolation max).
    """
    adn = forger_fn(intention)
    feedback, lecons = None, []
    succes, verdict, lignes, code_final = False, "non execute", 0, ""

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

        dangers = scan_statique(module.code, cap=cap)
        if dangers:
            lecons.append(f"scan: {dangers}")
            feedback = (module.code, f"Appels dangereux: {dangers}")
            verdict = f"scan BLOQUE: {dangers}"
            if not reparer:
                break
            continue

        rc, out, err, _ = executer_isole(module.code, cap=cap, volume_nom=volume_nom)
        if rc == 0:
            succes, verdict, code_final = True, f"execute OK (tentative {t})", module.code
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

    return Resultat(succes, verdict, t, lignes, lecons, code_final)


# ---------------------------------------------------------------------------
# PRODUCTION REELLE : branche le vrai generateur Claude sur le pipeline.
# Remplace les 7 variantes usine_* : un seul chemin, un seul orchestrateur.
# ---------------------------------------------------------------------------
_CLIENT = None


def _client():
    """Client anthropic paresseux : cree une seule fois, au premier besoin reel."""
    global _CLIENT
    if _CLIENT is None:
        import anthropic
        from generator import _load_api_key
        _CLIENT = anthropic.Anthropic(api_key=_load_api_key())
    return _CLIENT


def fabriquer_reel(intention, *, reparer=True, max_tentatives=3, enregistrer=True, cap=None) -> Resultat:
    """
    Vrai chemin de production : intention -> ADN (Claude) -> code (Claude)
    -> 3 garde-fous -> execution (bac a sable selon capacites) -> auto-reparation
    -> ledger + lignee. Un produit qui TOURNE est persiste au registre.
    cap (Capacites) : capacites accordees au produit (persistance, reseau). None = pur.
    """
    from compositeur import forger_adn
    from usine_autoreparation import generer as generer_reel
    import registre as _reg

    client = _client()
    volume_nom = None
    if cap is not None and getattr(cap, "persistance", False):
        volume_nom = "viv_" + _reg._slug(intention)

    forger = lambda intention: forger_adn(intention, client)
    generer = lambda adn, feedback=None: generer_reel(adn, client, feedback, cap=cap)

    r = fabriquer(intention, forger, generer,
                  reparer=reparer, max_tentatives=max_tentatives, tracer=True,
                  cap=cap, volume_nom=volume_nom)

    if enregistrer and r.succes and r.code:
        import registre
        entree = registre.enregistrer(intention, r.code,
                                      verdict=r.verdict, tentatives=r.tentatives, lignes=r.lignes)
        print(f"  [REGISTRE] produit enregistre : {entree['id']}")

    return r


def fabriquer_outil(intention, contrat, *, reparer=True, max_tentatives=3, cap=None) -> Resultat:
    """
    Fabrique un PRODUIT PROMOUVABLE : un module qui expose `executer(donnees)` conforme au
    contrat (schema d'entree), au lieu de donnees en dur. Enregistre le code + le schema,
    ce qui rend le produit promouvable en appli web (promotion.py).
    contrat : une instance de contrat.ContratProduit.
    """
    from compositeur import forger_adn
    from usine_autoreparation import generer as generer_reel
    import registre as _reg

    client = _client()
    volume_nom = "viv_" + _reg._slug(intention) if (cap and getattr(cap, "persistance", False)) else None
    forger = lambda i: forger_adn(i, client)
    generer = lambda adn, feedback=None: generer_reel(adn, client, feedback, cap=cap, contrat=contrat)

    r = fabriquer(intention, forger, generer,
                  reparer=reparer, max_tentatives=max_tentatives, tracer=True,
                  cap=cap, volume_nom=volume_nom)

    if r.succes and r.code:
        entree = _reg.enregistrer(intention, r.code, verdict=r.verdict, tentatives=r.tentatives,
                                  lignes=r.lignes, contrat=contrat.model_dump())
        print(f"  [REGISTRE] outil promouvable enregistre : {entree['id']}")
    return r


def fabriquer_juge_reel(intention, *, reparer=True, max_tentatives=3, enregistrer=True, cap=None) -> Resultat:
    """
    Chemin JUGE : l'organisme genere PLUSIEURS strategies, les note selon les curseurs
    de l'ADN, garde la MEILLEURE, puis la passe par les garde-fous + execution + reparation.
    La reparation regenere la strategie gagnante avec le feedback d'erreur.
    """
    from compositeur import forger_adn
    from production_jugee import produire_le_mieux_reel, generer_candidat
    import registre as _reg

    client = _client()
    adn = forger_adn(intention, client)
    volume_nom = "viv_" + _reg._slug(intention) if (cap and getattr(cap, "persistance", False)) else None

    etat = {"classement": None, "consigne": None}

    def generer(_adn, feedback=None):
        if feedback is None:
            module, consigne, classement = produire_le_mieux_reel(_adn, client, cap=cap)
            etat["classement"], etat["consigne"] = classement, consigne
            return module
        return generer_candidat(_adn, client, etat["consigne"], feedback=feedback, cap=cap)

    r = fabriquer(intention, lambda i: adn, generer,
                  reparer=reparer, max_tentatives=max_tentatives, tracer=True,
                  cap=cap, volume_nom=volume_nom)
    r.classement = etat["classement"]

    if enregistrer and r.succes and r.code:
        entree = _reg.enregistrer(intention, r.code,
                                  verdict=r.verdict, tentatives=r.tentatives, lignes=r.lignes)
        print(f"  [REGISTRE] produit enregistre : {entree['id']}")
    return r


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
    if len(sys.argv) > 1:
        intention = " ".join(sys.argv[1:])
        print("=" * 60)
        print(f"VIVARIUM - PRODUCTION REELLE : '{intention}'")
        print("=" * 60)
        r = fabriquer_reel(intention)
        print(f"\n  succes={r.succes} | {r.verdict} | {r.tentatives} tentative(s) | {r.lignes} lignes")
        if r.lecons:
            print("  lecons :", " | ".join(r.lecons))
        sys.exit(0 if r.succes else 1)
    else:
        sys.exit(0 if smoke_test() else 1)

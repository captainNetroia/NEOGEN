"""
NEOGEN - L'Usine unifiee : fabriquer en heritant, apprendre en fabriquant

Jusqu'ici, la memoire generationnelle accumulait des lecons, mais l'Usine ne les
consultait jamais. Ce module unit les deux fils en UN organisme :

  1. Avant de fabriquer, l'Usine HERITE des lecons de toutes les generations
     passees et les respecte dans la generation du code.
  2. Quand elle apprend une nouvelle lecon en produisant (erreur diagnostiquee),
     cette lecon REJOINT la lignee : une nouvelle generation est engendree.

La memoire devient fonctionnelle : il fabrique mieux parce qu'il se souvient,
et il se souvient mieux parce qu'il fabrique. Boucle complete.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic

from generator import _load_api_key
from compositeur import forger_adn, membrane
from usine import scan_statique, executer_isole
from usine_autoreparation import generer
from usine_reflexive import reflechir
from memoire_generationnelle import charger_derniere, engendrer, Patrimoine


def fabriquer_avec_heritage(intention: str, max_tentatives: int = 4, faute_injectee: bool = False):
    client = anthropic.Anthropic(api_key=_load_api_key())

    print("=" * 72)
    print(f"NEOGEN - L'USINE UNIFIEE : '{intention}'")
    print("=" * 72)

    # --- HERITAGE : on charge les lecons de la lignee ---
    parent = charger_derniere()
    lecons_heritees = parent.patrimoine.lecons
    print(f"\n[HERITAGE] Generation {parent.numero + 1}, heritiere de la generation {parent.numero}.")
    if lecons_heritees:
        print(f"  {len(lecons_heritees)} lecon(s) heritee(s) des ancetres. Les plus recentes :")
        for l in lecons_heritees[-4:]:
            print(f"     - {l}")
    else:
        print("  Aucune lecon heritee (lignee jeune).")

    print("\n[ADN] Claude forge l'ADN du produit...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")

    # les lecons heritees entrent dans le contexte de generation
    feedback = None
    if lecons_heritees:
        feedback = ("(heritage des generations passees - pas de code precedent)",
                    "LECONS HERITEES DE TES ANCETRES, a respecter imperativement : "
                    + " | ".join(lecons_heritees[-8:]))

    nouvelles_lecons = []
    succes = False
    for t in range(1, max_tentatives + 1):
        print(f"\n----- TENTATIVE {t}/{max_tentatives} -----")
        module = generer(adn, client, feedback)
        print(f"  code genere : {len(module.code.splitlines())} lignes "
              + ("(en tenant compte des lecons heritees)" if (feedback and t == 1 and lecons_heritees) else ""))

        verdict, raison = membrane(module, adn.murs)
        if verdict == "REJETE":
            diag = reflechir(intention, adn, t, module.code, f"Membrane: {raison}", client)
            nouvelles_lecons.append(diag.lecon)
            feedback = (module.code, f"DIAGNOSTIC: {diag.cause_racine} | CORRECTION: {diag.correction}")
            continue
        dangers = scan_statique(module.code)
        if dangers:
            diag = reflechir(intention, adn, t, module.code, f"Scan: {dangers}", client)
            nouvelles_lecons.append(diag.lecon)
            feedback = (module.code, f"DIAGNOSTIC: {diag.cause_racine} | CORRECTION: {diag.correction}")
            continue

        code = module.code
        if faute_injectee and t == 1:
            code += ("\n\n# === FAUTE INJECTEE (pour qu'une lecon naisse en production) ===\n"
                     "config = {}\n"
                     "_ = config['cle_absente']  # KeyError : acces a une cle de config inexistante\n")
            print("  [TEST] faute injectee : acces a une cle de config absente (KeyError)")

        rc, out, err, chemin = executer_isole(code)
        if rc == 0:
            print(f"  [EXECUTION] SUCCES a la tentative {t}")
            for ligne in out.strip().splitlines()[:6]:
                print("    " + ligne)
            succes = True
            break
        err_court = err.strip().splitlines()[-1] if err.strip() else "echec"
        print(f"  [EXECUTION] ECHEC : {err_court}")
        print("  [REMISE EN QUESTION] diagnostic en cours...")
        diag = reflechir(intention, adn, t, code, err.strip()[-700:], client)
        print(f"     lecon apprise : {diag.lecon}")
        nouvelles_lecons.append(diag.lecon)
        feedback = (code, f"DIAGNOSTIC: {diag.cause_racine}\nCORRECTION: {diag.correction}")

    # --- TRANSMISSION : les lecons apprises en produisant rejoignent la lignee ---
    print("\n[TRANSMISSION] Les lecons apprises en fabriquant rejoignent la lignee...")
    acquis = Patrimoine(physique={}, lois=[], vocabulaire=[], lecons=nouvelles_lecons)
    enfant = engendrer(parent, acquis,
                       resume=f"A fabrique '{intention}' ({'succes' if succes else 'echec'}), "
                              f"appris {len(nouvelles_lecons)} lecon(s) en produisant.")
    print(f"  Generation {parent.numero} : {len(parent.patrimoine.lecons)} lecon(s)")
    print(f"  Generation {enfant.numero} : {len(enfant.patrimoine.lecons)} lecon(s)  "
          f"(+{len(enfant.patrimoine.lecons) - len(parent.patrimoine.lecons)} nee(s) de cette fabrication)")

    print("\n" + "=" * 72)
    if succes:
        print("Produit fabrique en heritant des lecons passees, et la lignee a grandi de")
        print("ce qu'il a appris en le fabriquant. La memoire sert enfin a produire. Boucle bouclee.")
    else:
        print("Echec de fabrication, mais les lecons apprises sont transmises a la lignee :")
        print("la prochaine generation partira plus avisee. Meme l'echec nourrit la memoire.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un mini lecteur de fichiers de configuration (cle=valeur)"
    fabriquer_avec_heritage(intention, faute_injectee=True)

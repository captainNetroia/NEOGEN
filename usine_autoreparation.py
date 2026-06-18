"""
VIVARIUM - L'Usine auto-reparatrice

L'Usine generait du code et l'executait une fois. Ici, si l'execution echoue,
le systeme renvoie l'erreur a Claude et REGENERE un code corrige, en boucle,
jusqu'a ce que ca tourne ou qu'il abandonne proprement.

C'est un vrai organisme : il ne se contente pas d'ecrire, il SE CORRIGE quand
ca casse. Les memes 3 couches de securite s'appliquent a chaque tentative.

DEMO : on injecte volontairement une panne dans la 1re tentative (clairement
labellisee) pour DECLENCHER et MONTRER la reparation. Ce n'est pas un faux
succes : c'est un test honnete du mecanisme de recuperation.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic

from generator import _load_api_key, MODEL
from compositeur import forger_adn, membrane
from usine import ModuleGenere, scan_statique, executer_isole


def generer(adn, client, feedback=None, cap=None, contrat=None) -> ModuleGenere:
    from capacites import Capacites, contraintes_generation
    cap = cap or Capacites()
    murs = "\n".join(f"  - {m.id} : {m.label}" for m in adn.murs)
    organes = "\n".join(f"  - {o.nom} : {o.besoin}" for o in adn.organes)
    bloc_contrat = ""
    if contrat is not None:
        from contrat import consigne_contrat
        bloc_contrat = "\n\n" + consigne_contrat(contrat)
    base = (
        f"Tu generes un PRODUIT complet en Python. Objectif : {adn.objectif}\n\n"
        f"MURS ABSOLUS :\n{murs}\n\nORGANES :\n{organes}\n\n"
        f"CAPACITES ET CONTRAINTES (utilise UNIQUEMENT ce qui t'est accorde) :\n{contraintes_generation(cap)}"
        f"{bloc_contrat}\n\n"
        "Un seul module autonome, termine par "
        "`if __name__ == \"__main__\":` avec une demo + des assert prouvant que ca marche, "
        "et un message de succes clair. Declare honnetement tes effets."
    )
    if feedback:
        code_prec, erreur = feedback
        base += (
            "\n\n--- TENTATIVE PRECEDENTE ECHOUEE ---\n"
            "Voici le code que tu as produit et l'erreur a l'execution. "
            "CORRIGE le probleme et renvoie le module complet corrige.\n\n"
            f"ERREUR :\n{erreur}\n\nCODE PRECEDENT :\n{code_prec}"
        )
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, thinking={"type": "adaptive"},
        system=base,
        messages=[{"role": "user", "content": "Genere (ou corrige) le module complet."}],
        output_format=ModuleGenere,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Generation echouee")
    return resp.parsed_output


def reparer(intention: str, max_tentatives: int = 4, faute_injectee: bool = False):
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"VIVARIUM - L'USINE AUTO-REPARATRICE : '{intention}'")
    print("=" * 72)

    print("\n[ADN] Claude forge l'ADN...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")

    feedback = None
    for t in range(1, max_tentatives + 1):
        print(f"\n----- TENTATIVE {t}/{max_tentatives} " + ("(correction d'apres l'erreur precedente)" if feedback else "(premiere generation)") + " -----")
        module = generer(adn, client, feedback)
        print(f"  code genere : {len(module.code.splitlines())} lignes")

        verdict, raison = membrane(module, adn.murs)
        if verdict == "REJETE":
            print(f"  [MEMBRANE] REJETE : {raison} -> on renvoie a Claude pour correction")
            feedback = (module.code, f"La membrane a rejete : {raison}")
            continue
        dangers = scan_statique(module.code)
        if dangers:
            print(f"  [SCAN] BLOQUE : {dangers} -> on renvoie a Claude pour correction")
            feedback = (module.code, f"Scan statique : appels dangereux {dangers}")
            continue

        code = module.code
        if faute_injectee and t == 1:
            code += ("\n\n# === FAUTE INJECTEE (test du mecanisme de reparation) ===\n"
                     "raise RuntimeError('panne simulee : etat invalide au demarrage')\n")
            print("  [TEST] faute injectee dans cette tentative pour declencher la reparation")

        rc, out, err, chemin = executer_isole(code)
        if rc == 0:
            print(f"  [EXECUTION] code retour 0 -> SUCCES a la tentative {t}")
            print("  --- SORTIE ---")
            for ligne in out.strip().splitlines()[:12]:
                print("    " + ligne)
            print("\n" + "=" * 72)
            print(f"REPARE ET FONCTIONNEL en {t} tentative(s).")
            if t > 1:
                print("Le systeme a detecte la panne, renvoye l'erreur a Claude, et obtenu")
                print("un code corrige qui tourne. Il s'est soigne tout seul.")
            print("=" * 72)
            return
        # echec : on capture l'erreur et on boucle
        err_court = (err.strip().splitlines()[-1] if err.strip() else "echec sans message")
        print(f"  [EXECUTION] code retour {rc} -> ECHEC : {err_court}")
        print("  -> on renvoie l'erreur a Claude pour qu'il repare")
        feedback = (code, err.strip()[-600:])

    print("\n" + "=" * 72)
    print(f"ABANDON propre apres {max_tentatives} tentatives. Le systeme n'a pas su reparer.")
    print("Honnete : l'auto-reparation a une limite, et elle s'arrete proprement.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un convertisseur de temperature celsius vers fahrenheit"
    reparer(intention, faute_injectee=True)

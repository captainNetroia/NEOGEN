"""
NEOGEN - L'Usine reflexive : comprendre l'erreur, pas juste la corriger

Idee de Jordan : un historique des erreurs ET de leur resolution, pour
COMPRENDRE pourquoi une erreur survient a cet instant, dans cet environnement.
Une remise en question.

Sur chaque echec, le systeme ne se contente pas de renvoyer l'erreur a Claude.
Il DIAGNOSTIQUE d'abord :
  - cause racine,
  - pourquoi a cet instant,
  - facteur environnemental,
  - lecon generalisable.
Tout est journalise (data/journal_erreurs.jsonl, persistant) avec le contexte.
Aux runs suivants, les lecons passees sont relues pour ne pas repeter l'erreur.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import os
import json
import sys
from datetime import datetime

import anthropic
from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL
from compositeur import forger_adn, membrane
from usine import scan_statique, executer_isole
from usine_autoreparation import generer

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "journal_erreurs.jsonl")


# ---------------------------------------------------------------------------
# La remise en question : un diagnostic structure de l'erreur
# ---------------------------------------------------------------------------
class Diagnostic(BaseModel):
    cause_racine: str = Field(description="la vraie cause technique de l'erreur")
    pourquoi_a_cet_instant: str = Field(description="pourquoi elle survient maintenant, dans ce contexte precis")
    facteur_environnemental: str = Field(description="ce qui, dans l'environnement (objectif, murs, donnees, etape), a contribue")
    lecon: str = Field(description="lecon generalisable a retenir pour ne pas refaire ce type d'erreur")
    correction: str = Field(description="la correction concrete a appliquer")


def charger_lecons() -> list[str]:
    if not os.path.exists(JOURNAL):
        return []
    lecons = []
    for ligne in open(JOURNAL, encoding="utf-8"):
        ligne = ligne.strip()
        if ligne:
            try:
                lecons.append(json.loads(ligne)["diagnostic"]["lecon"])
            except Exception:
                pass
    return lecons


def enregistrer(entree: dict):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def reflechir(intention, adn, tentative, code, erreur, client) -> Diagnostic:
    environnement = (
        f"Intention du produit : {intention}\n"
        f"Objectif (ADN) : {adn.objectif}\n"
        f"Murs en vigueur : {', '.join(m.id + '=' + m.regle for m in adn.murs)}\n"
        f"Tentative : {tentative}\n"
        f"Etape : execution du code genere"
    )
    systeme = (
        "Tu es la fonction de remise en question de NEOGEN. Une erreur vient de survenir "
        "pendant la fabrication d'un produit. Avant toute correction, tu dois COMPRENDRE "
        "l'erreur : sa cause racine, pourquoi elle survient a cet instant precis, quel "
        "facteur de l'environnement y a contribue, et quelle lecon generale en tirer. "
        "Sois precis et honnete."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=6000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content":
                   f"=== ENVIRONNEMENT ===\n{environnement}\n\n=== ERREUR ===\n{erreur}\n\n"
                   f"=== CODE (extrait) ===\n{code[:2000]}"}],
        output_format=Diagnostic,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Diagnostic impossible")
    return resp.parsed_output


def reparer_reflexif(intention: str, max_tentatives: int = 4, faute_injectee: bool = False):
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"NEOGEN - L'USINE REFLEXIVE : '{intention}'")
    print("=" * 72)

    lecons_passees = charger_lecons()
    if lecons_passees:
        print(f"\n[MEMOIRE] {len(lecons_passees)} lecon(s) d'erreurs passees relue(s) :")
        for l in lecons_passees[-3:]:
            print(f"   - {l}")

    print("\n[ADN] Claude forge l'ADN...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")

    journal_session = []
    feedback = None
    if lecons_passees:
        feedback = ("(aucun code precedent - premiere generation)",
                    "Respecte ces lecons tirees d'erreurs passees : " + " | ".join(lecons_passees[-5:]))

    for t in range(1, max_tentatives + 1):
        print(f"\n----- TENTATIVE {t}/{max_tentatives} -----")
        module = generer(adn, client, feedback)
        print(f"  code genere : {len(module.code.splitlines())} lignes")

        verdict, raison = membrane(module, adn.murs)
        if verdict == "REJETE":
            diag = reflechir(intention, adn, t, module.code, f"Membrane: {raison}", client)
            _logger(intention, t, adn, f"Membrane: {raison}", diag, journal_session)
            feedback = (module.code, f"DIAGNOSTIC: {diag.cause_racine} | CORRECTION: {diag.correction}")
            continue
        dangers = scan_statique(module.code)
        if dangers:
            diag = reflechir(intention, adn, t, module.code, f"Scan: {dangers}", client)
            _logger(intention, t, adn, f"Scan: {dangers}", diag, journal_session)
            feedback = (module.code, f"DIAGNOSTIC: {diag.cause_racine} | CORRECTION: {diag.correction}")
            continue

        code = module.code
        if faute_injectee and t == 1:
            code += ("\n\n# === FAUTE INJECTEE (test du journal reflexif) ===\n"
                     "def _moyenne(valeurs):\n    return sum(valeurs) / len(valeurs)\n"
                     "_moyenne([])  # liste vide -> ZeroDivisionError\n")
            print("  [TEST] faute injectee : moyenne d'une liste vide (ZeroDivisionError)")

        rc, out, err, chemin = executer_isole(code)
        if rc == 0:
            print(f"  [EXECUTION] SUCCES a la tentative {t}")
            for ligne in out.strip().splitlines()[:8]:
                print("    " + ligne)
            _afficher_journal(journal_session)
            print("\n" + "=" * 72)
            print(f"FONCTIONNEL en {t} tentative(s). Chaque erreur a ete COMPRISE avant d'etre corrigee,")
            print("et journalisee avec son environnement. Le systeme apprend de ses erreurs.")
            print("=" * 72)
            return

        err_court = err.strip().splitlines()[-1] if err.strip() else "echec"
        print(f"  [EXECUTION] ECHEC : {err_court}")
        print("  [REMISE EN QUESTION] le systeme analyse POURQUOI...")
        diag = reflechir(intention, adn, t, code, err.strip()[-800:], client)
        print(f"    cause racine        : {diag.cause_racine}")
        print(f"    pourquoi maintenant : {diag.pourquoi_a_cet_instant}")
        print(f"    facteur environnem. : {diag.facteur_environnemental}")
        print(f"    lecon               : {diag.lecon}")
        _logger(intention, t, adn, err_court, diag, journal_session)
        feedback = (code, f"DIAGNOSTIC: {diag.cause_racine}\nPOURQUOI: {diag.pourquoi_a_cet_instant}\nCORRECTION: {diag.correction}")

    _afficher_journal(journal_session)
    print("\nABANDON propre apres", max_tentatives, "tentatives. Les diagnostics restent au journal.")


def _logger(intention, tentative, adn, erreur, diag: Diagnostic, journal_session):
    entree = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "intention": intention,
        "tentative": tentative,
        "environnement": {"objectif": adn.objectif, "murs": [m.id for m in adn.murs], "etape": "execution"},
        "erreur": erreur,
        "diagnostic": diag.model_dump(),
    }
    enregistrer(entree)
    journal_session.append(entree)


def _afficher_journal(journal_session):
    if not journal_session:
        return
    print("\n=== JOURNAL DES ERREURS DE CETTE SESSION (persiste dans data/journal_erreurs.jsonl) ===")
    for e in journal_session:
        print(f"  [tentative {e['tentative']}] {e['erreur']}")
        print(f"     cause   : {e['diagnostic']['cause_racine']}")
        print(f"     lecon   : {e['diagnostic']['lecon']}")
        print(f"     environ : objectif='{e['environnement']['objectif'][:50]}...' murs={e['environnement']['murs']}")


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "une calculatrice de statistiques (moyenne, mediane, ecart-type)"
    reparer_reflexif(intention, faute_injectee=True)

"""
VIVARIUM - Production jugee : l'organisme choisit la MEILLEURE facon de produire

Le jugement (selection.py) notait les lois. Ici on l'eleve au niveau PRODUCTION :
pour une meme intention, l'organisme genere PLUSIEURS strategies, les NOTE selon
les curseurs de l'ADN (ce qui compte pour ce produit), et CHOISIT la meilleure.

C'est la phrase de Jordan realisee : l'organisme decide de la meilleure maniere
de produire, en fonction de ce qui compte (les curseurs ponderes = son ex. banque).

GARDE-FOU : le critere (curseurs + murs) vient de l'ADN, pas auto-defini pour se
flatter. Les murs sont des contraintes dures (disqualifiantes) ; les curseurs
ponderent les preferences. Autonomie du choix, pas du critere.

HONNETETE : la qualite d'un produit se mesure ici par des PROXIES (effets declares,
longueur du code, respect des murs), pas par sa vraie qualite a l'execution.
Certaines dimensions (vitesse...) sont des estimations neutres, assumees.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic

from generator import _load_api_key, MODEL
from compositeur import forger_adn, membrane
from usine import ModuleGenere


VARIANTES = [
    ("simplicite", "Privilegie la SIMPLICITE et la concision : le code le plus court et direct possible."),
    ("securite", "Privilegie la ROBUSTESSE et la SECURITE maximale : validation, authentification, aucune fuite."),
]


def generer_candidat(adn, client, consigne: str, feedback=None, cap=None) -> ModuleGenere:
    from capacites import Capacites, contraintes_generation
    cap = cap or Capacites()
    murs = "\n".join(f"  - {m.id} : {m.label}" for m in adn.murs)
    organes = "\n".join(f"  - {o.nom} : {o.besoin}" for o in adn.organes)
    systeme = (
        f"Tu generes un PRODUIT complet en Python. Objectif : {adn.objectif}\n\n"
        f"MURS ABSOLUS :\n{murs}\n\nORGANES :\n{organes}\n\n"
        f"ORIENTATION DE CETTE VERSION : {consigne}\n\n"
        f"CAPACITES ET CONTRAINTES (utilise UNIQUEMENT ce qui t'est accorde) :\n{contraintes_generation(cap)}\n\n"
        "Un module autonome avec un bloc main de demonstration. Declare honnetement tes effets."
    )
    if feedback:
        code_prec, erreur = feedback
        systeme += ("\n\n--- TENTATIVE PRECEDENTE ECHOUEE ---\nCORRIGE le probleme et renvoie le "
                    f"module complet corrige.\nERREUR :\n{erreur}\n\nCODE PRECEDENT :\n{code_prec}")
    resp = client.messages.parse(
        model=MODEL, max_tokens=12000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": "Genere (ou corrige) le module complet."}],
        output_format=ModuleGenere,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Generation candidat echouee")
    return resp.parsed_output


def produire_le_mieux_reel(adn, client, cap=None):
    """Genere les VARIANTES, les note selon les curseurs de l'ADN, retourne la meilleure.
    Renvoie (module_gagnant, consigne_gagnante, classement) sans l'executer."""
    candidats = []
    for nom, consigne in VARIANTES:
        module = generer_candidat(adn, client, consigne, cap=cap)
        score, detail = qualite_production(module, adn)
        candidats.append((nom, consigne, module, score))
    candidats.sort(key=lambda x: x[3], reverse=True)
    gagnant = candidats[0]
    classement = [(nom, score) for nom, _, _, score in candidats]
    return gagnant[2], gagnant[1], classement


def composante(nom_curseur: str, module: ModuleGenere, adn) -> float:
    """Mesure (proxy) d'une dimension de qualite, 0..1, selon le nom du curseur."""
    e = module.effets
    n = nom_curseur.lower()
    if "secur" in n or "sûr" in n or "sur" in n:
        s = 0.0
        s += 0.4 if e.verifie_authentification else 0.1
        s += 0.4 if not e.stocke_secret_en_clair else 0.0
        s += 0.2 if (not e.acces_reseau or e.reseau_autorise) else 0.0
        return round(s, 3)
    if "simpl" in n or "concis" in n:
        lignes = len(module.code.splitlines())
        return round(max(0.0, 1.0 - lignes / 250.0), 3)
    if "fiab" in n or "robust" in n:
        return 1.0 if membrane(module, adn.murs)[0] != "REJETE" else 0.0
    # dimensions non mesurables statiquement (vitesse, lisibilite, portabilite...) : estimation neutre assumee
    return 0.7


def qualite_production(module: ModuleGenere, adn) -> tuple[float, dict]:
    # MUR : un produit qui viole un mur est disqualifie (qualite 0)
    verdict, _ = membrane(module, adn.murs)
    if verdict == "REJETE":
        return 0.0, {"_disqualifie": "mur viole"}
    total_poids = sum(c.poids for c in adn.curseurs) or 1
    detail = {}
    score = 0.0
    for c in adn.curseurs:
        comp = composante(c.nom, module, adn)
        detail[c.nom] = (comp, c.poids)
        score += comp * c.poids
    return round(score / total_poids, 3), detail


def produire_le_mieux(intention: str):
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"VIVARIUM - PRODUCTION JUGEE : '{intention}'")
    print("=" * 72)

    print("\n[ADN] Claude forge l'ADN (objectif + murs + curseurs)...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")
    print("  CURSEURS (ce qui compte, pondere) :", ", ".join(f"{c.nom} {c.poids}" for c in adn.curseurs))

    print(f"\n[STRATEGIES] L'organisme genere {len(VARIANTES)} facons de produire, puis les juge...")
    candidats = []
    for nom, consigne in VARIANTES:
        module = generer_candidat(adn, client, consigne)
        score, detail = qualite_production(module, adn)
        candidats.append((nom, module, score, detail))
        print(f"\n  Strategie '{nom}' : {len(module.code.splitlines())} lignes | qualite ponderee = {score}")
        for dim, (comp, poids) in detail.items():
            if dim != "_disqualifie":
                print(f"     {dim:14s} : {comp}  (poids {poids})")

    # CHOIX : la strategie de plus haute qualite ponderee
    candidats.sort(key=lambda x: x[2], reverse=True)
    gagnant = candidats[0]
    print("\n--- CHOIX DE L'ORGANISME ---")
    print(f"  Strategie retenue : '{gagnant[0]}' (qualite {gagnant[2]})")
    for nom, _, score, _ in candidats[1:]:
        print(f"  Ecartee : '{nom}' (qualite {score})")

    print("\n" + "=" * 72)
    print("L'organisme a genere plusieurs facons de produire, les a jugees selon ce qui")
    print("compte (les curseurs de l'ADN), et a choisi la meilleure. Il decide COMMENT produire.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un gestionnaire de mots de passe"
    produire_le_mieux(intention)

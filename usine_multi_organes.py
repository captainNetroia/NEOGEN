"""
VIVARIUM - Usine multi-organes : recoller des pieces independantes

Jusqu'ici l'Usine generait UN module coherent d'un coup. Ici on construit une
appli a partir de plusieurs ORGANES generes SEPAREMENT, puis recolles.

Le verrou est l'interface : des pieces generees independamment doivent s'emboiter.
La cle : un CONTRAT D'INTERFACE defini AVANT.
  1. L'architecte (Claude) conçoit le contrat : pour chaque organe, une signature
     de fonction EXACTE, + le code d'assemblage qui orchestre ces fonctions.
  2. Chaque organe est genere SEPAREMENT, implementant sa fonction a sa signature,
     en connaissant tout le contrat (donc en sachant ce qui existe autour).
  3. On recolle : organes + assemblage -> un module, qu'on execute (conteneur).

HONNETETE : meme avec un contrat, recoller des pieces d'IA peut laisser des bugs
d'integration. L'auto-reparation pourra se brancher dessus ensuite. v1 : un
assemblage + une execution, rapport honnete.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic
from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL
from compositeur import forger_adn
from usine import scan_statique, executer_isole


class ContratOrgane(BaseModel):
    nom_fonction: str = Field(description="nom de la fonction, snake_case")
    signature: str = Field(description="la ligne def complete, ex: def calculer(x: float) -> float:")
    role: str = Field(description="ce que fait cet organe, une phrase")


class Contrat(BaseModel):
    organes: list[ContratOrgane] = Field(description="3 a 4 organes aux signatures coherentes entre elles")
    code_assemblage: str = Field(description="le code qui orchestre ces fonctions + un bloc "
                                             "if __name__=='__main__' avec une demo et des assert")


class ImplOrgane(BaseModel):
    code: str = Field(description="le code complet de la fonction demandee, rien d'autre")


def generer_contrat(adn, client) -> Contrat:
    organes = "\n".join(f"  - {o.nom} : {o.besoin}" for o in adn.organes)
    systeme = (
        f"Tu es l'ARCHITECTE d'un produit Python. Objectif : {adn.objectif}\n"
        f"Organes pressentis :\n{organes}\n\n"
        "Conçois le CONTRAT D'INTERFACE : pour 3 a 4 organes, donne une signature de "
        "fonction EXACTE (ligne def avec types), coherentes entre elles (les sorties des "
        "uns alimentent les entrees des autres). Puis ecris le CODE D'ASSEMBLAGE : "
        "l'orchestration qui appelle ces fonctions dans le bon ordre, plus un bloc "
        "if __name__=='__main__' avec une demo et des assert prouvant que tout marche. "
        "Les organes seront implementes SEPAREMENT : les signatures doivent suffire a les "
        "ecrire independamment. Python pur, stdlib, aucune I/O fichier ni reseau."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=8000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": "Conçois le contrat et l'assemblage."}],
        output_format=Contrat,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Contrat non produit")
    return resp.parsed_output


def generer_organe(contrat: Contrat, organe: ContratOrgane, client) -> ImplOrgane:
    toutes = "\n".join(f"  {o.signature}   # {o.role}" for o in contrat.organes)
    systeme = (
        "Tu implementes UN organe d'un produit Python. Voici le contrat complet "
        f"(toutes les fonctions existent) :\n{toutes}\n\n"
        f"Implemente UNIQUEMENT cette fonction, avec EXACTEMENT cette signature :\n"
        f"  {organe.signature}\n  role : {organe.role}\n\n"
        "Tu peux appeler les autres fonctions du contrat (elles existent). Renvoie le code "
        "complet de CETTE fonction seulement. Python pur, stdlib, aucune I/O fichier ni reseau."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=4000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": f"Implemente {organe.nom_fonction}."}],
        output_format=ImplOrgane,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Organe {organe.nom_fonction} non implemente")
    return resp.parsed_output


def assembler(impls: list[str], code_assemblage: str) -> str:
    entete = "# Produit assemble par VIVARIUM a partir d'organes generes separement\n"
    return entete + "\n\n".join(impls) + "\n\n# --- assemblage / orchestration ---\n" + code_assemblage


def fabriquer_multi(intention: str):
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"VIVARIUM - USINE MULTI-ORGANES : '{intention}'")
    print("=" * 72)

    print("\n[ADN] Claude forge l'ADN...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")

    print("\n[CONTRAT] L'architecte conçoit l'interface (signatures + assemblage)...")
    contrat = generer_contrat(adn, client)
    print(f"  {len(contrat.organes)} organes au contrat :")
    for o in contrat.organes:
        print(f"     {o.signature}")
        print(f"        -> {o.role}")

    print(f"\n[ORGANES] Generation SEPAREE de chaque organe a sa signature...")
    impls = []
    for o in contrat.organes:
        impl = generer_organe(contrat, o, client)
        impls.append(impl.code)
        print(f"  organe '{o.nom_fonction}' implemente ({len(impl.code.splitlines())} lignes)")

    code = assembler(impls, contrat.code_assemblage)
    print(f"\n[RECOLLAGE] Produit assemble : {len(code.splitlines())} lignes au total.")

    dangers = scan_statique(code)
    if dangers:
        print(f"  [SCAN] appels dangereux : {dangers} -> execution refusee")
        return
    print("  [SCAN] propre.")

    print("\n[EXECUTION] le produit recolle tourne-t-il ?")
    rc, out, err, chemin = executer_isole(code)
    print(f"  code retour : {rc}")
    if out.strip():
        print("  --- SORTIE ---")
        for l in out.strip().splitlines()[:12]:
            print("    " + l)
    if rc != 0 and err.strip():
        print("  --- ERREUR ---")
        for l in err.strip().splitlines()[-8:]:
            print("    " + l)

    print("\n" + "=" * 72)
    if rc == 0:
        print("Des organes generes SEPAREMENT, recolles via un contrat d'interface, forment")
        print("une appli qui TOURNE. La piece a plusieurs pieces tient. Multi-organes valide.")
    else:
        print("Le recollage a produit un bug d'integration (honnete : c'est le point dur).")
        print("Prochain cran : brancher l'auto-reparation sur l'assemblage multi-organes.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "une calculatrice de pourboire qui repartit l'addition entre convives"
    fabriquer_multi(intention)

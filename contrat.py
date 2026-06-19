"""
NEOGEN - Contrat de produit : l'entree externe au lieu de donnees en dur

Un produit "jouet" a ses donnees en dur dans son __main__. Un produit PROMU doit
prendre de VRAIES donnees. Le contrat declare :
  - un SCHEMA d'entree (les champs que l'appli web demandera a l'utilisateur),
  - un EXEMPLE d'entree (pour l'auto-test en sandbox),
  - l'engagement que le produit expose `def executer(donnees: dict) -> dict`.

Le generateur recoit ce contrat en consigne ; la promotion (promotion.py) derive le
formulaire web du schema ; l'executeur appelle executer(donnees) avec les vraies donnees.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
from pydantic import BaseModel, Field

# types de champ supportes par le formulaire web genere
TYPES = ("texte", "nombre", "booleen", "liste")


class SousChamp(BaseModel):
    nom: str = Field(description="cle technique, snake_case")
    type: str = Field(description="texte | nombre | booleen")
    label: str = Field(description="libelle affiche a l'utilisateur")


class Champ(BaseModel):
    nom: str = Field(description="cle technique, snake_case")
    type: str = Field(description="texte | nombre | booleen | liste")
    label: str = Field(description="libelle affiche a l'utilisateur")
    sous_champs: list[SousChamp] = Field(default_factory=list,
                                         description="si type=liste : les champs d'un element de la liste")


class ContratProduit(BaseModel):
    description: str = Field(description="ce que fait l'outil, une phrase")
    champs: list[Champ] = Field(description="les champs d'entree (ce que l'appli demandera)")
    exemple: dict = Field(description="un exemple d'entree complet conforme au schema")


def consigne_contrat(contrat: ContratProduit) -> str:
    """Fragment de prompt : impose au produit d'exposer executer(donnees) selon le schema."""
    lignes = []
    for c in contrat.champs:
        if c.type == "liste" and c.sous_champs:
            sous = ", ".join(f"{s.nom} ({s.type})" for s in c.sous_champs)
            lignes.append(f"  - {c.nom} : liste d'objets [{sous}] ({c.label})")
        else:
            lignes.append(f"  - {c.nom} : {c.type} ({c.label})")
    schema = "\n".join(lignes)
    import json
    return (
        "CONTRAT D'INTERFACE (OBLIGATOIRE) : expose une fonction\n"
        "    def executer(donnees: dict) -> dict\n"
        "qui prend en entree un dict avec EXACTEMENT ces champs :\n"
        f"{schema}\n"
        "Elle renvoie un dict JSON-serialisable (le resultat structure, lisible).\n"
        "Ne mets PAS les donnees en dur dans executer : lis-les depuis 'donnees'.\n"
        "Ajoute un bloc `if __name__ == \"__main__\":` qui appelle executer avec cet EXEMPLE "
        f"et fait des assert prouvant que ca marche :\n{json.dumps(contrat.exemple, ensure_ascii=False)}\n"
        "Le module doit aussi imprimer un message de succes clair dans ce bloc."
    )


def valider_entree(contrat: ContratProduit, donnees: dict) -> list[str]:
    """Verification legere : champs presents et type plausible. Renvoie la liste des erreurs."""
    erreurs = []
    for c in contrat.champs:
        if c.nom not in donnees:
            erreurs.append(f"champ manquant : {c.nom}")
            continue
        v = donnees[c.nom]
        if c.type == "nombre" and not isinstance(v, (int, float)):
            erreurs.append(f"{c.nom} doit etre un nombre")
        elif c.type == "booleen" and not isinstance(v, bool):
            erreurs.append(f"{c.nom} doit etre un booleen")
        elif c.type == "liste" and not isinstance(v, list):
            erreurs.append(f"{c.nom} doit etre une liste")
    return erreurs

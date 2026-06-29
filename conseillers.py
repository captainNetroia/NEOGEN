"""
NEOGEN - Conseillers : raisonnement juridique + cadrage analytique (Phase C)

Dans le flux Analyser, l'organisme ne se contente pas de proposer un ADN : il CONSEILLE.
Deux conseillers, en UN appel structure :
  - CONFORMITE : note juridique/RGPD INDICATIVE (risques, obligations) pour un produit.
  - CADRAGE    : questions analytiques a poser, donnees a collecter, sources a chercher,
                 pieges. Rend l'analyse plus pro et plus fine.

HONNETETE : ces notes sont generees par l'IA (connaissance du modele), PAS par une requete
live a Legifrance ou NotebookLM. La conformite est INDICATIVE, a confirmer par un juriste.
La connexion live des comptes (OpenLegi, NotebookLM, reseaux...) est la Phase E (le client
connecte SES comptes). Ici on apporte le raisonnement, sans surpromettre une source live.

Vrais appels Claude (parse_resilient). Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import sys

from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL_SCAN, parse_resilient


class NoteConformite(BaseModel):
    niveau_risque: str = Field(description="faible | moyen | eleve")
    points: list[str] = Field(description="rappels juridiques/RGPD/obligations pertinents pour ce produit")
    avertissement: str = Field(default="Note indicative generee par IA, a confirmer par un juriste.")


class Cadrage(BaseModel):
    questions_cles: list[str] = Field(description="questions analytiques a poser au client avant de produire")
    donnees_a_collecter: list[str] = Field(description="donnees/chiffres a recueillir pour un bon diagnostic")
    sources_a_chercher: list[str] = Field(description="types de sources/docs a rechercher pour cadrer")
    pieges: list[str] = Field(description="pieges ou angles morts a surveiller")


class Conseil(BaseModel):
    conformite: NoteConformite
    cadrage: Cadrage


def conseiller(intention: str, client, contexte: str = "") -> Conseil:
    systeme = (
        "Tu es le CONSEILLER de NEOGEN. Pour une intention de produit/besoin, tu produis "
        "DEUX choses, concretes et professionnelles :\n"
        "1) CONFORMITE : une note juridique/RGPD INDICATIVE (risques, obligations, donnees "
        "personnelles, retention...) adaptee a CE produit. Niveau de risque honnete. "
        "Rappelle que c'est indicatif, a confirmer par un juriste.\n"
        "2) CADRAGE analytique : les questions cles a poser au client, les donnees a collecter, "
        "les types de sources a chercher, et les pieges. Sois precis, pas generique."
    )
    contenu = f"Intention/besoin : {intention}"
    if contexte:
        contenu += f"\n\nContexte connu sur l'utilisateur/ses projets (pour personnaliser) :\n{contexte}"
    resp = parse_resilient(
        client, model=MODEL_SCAN, max_tokens=3500,
        system=systeme,
        messages=[{"role": "user", "content": contenu}],
        output_format=Conseil,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Le conseiller n'a rien produit")
    return resp.parsed_output


if __name__ == "__main__":
    import anthropic
    intention = " ".join(sys.argv[1:]) or "un coffre-fort de documents medicaux pour un cabinet"
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"NEOGEN - CONSEILLER : '{intention}'")
    print("=" * 72)
    c = conseiller(intention, client)
    print(f"\n[CONFORMITE] risque {c.conformite.niveau_risque}")
    for p in c.conformite.points:
        print(f"   - {p}")
    print(f"   ({c.conformite.avertissement})")
    print("\n[CADRAGE] questions cles :")
    for q in c.cadrage.questions_cles:
        print(f"   - {q}")
    print("  donnees a collecter :", "; ".join(c.cadrage.donnees_a_collecter))
    print("  sources a chercher :", "; ".join(c.cadrage.sources_a_chercher))
    print("  pieges :", "; ".join(c.cadrage.pieges))
    print("=" * 72)

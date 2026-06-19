"""
NEOGEN - Le discernement amont : quel probleme merite qu'on s'y attaque ?

Avant de generer quoi que ce soit, l'organisme JUGE l'intention :
  - merite-t-elle qu'on s'y attaque (valeur, clarte, faisabilite) ?
  - sinon, pourquoi, et comment la RECADRER ?
  - est-elle decomposable en sous-problemes ?

C'est le pendant amont de la production jugee (selection.py / production_jugee.py
jugent ce qui merite d'etre garde APRES). Ici on juge ce qui merite d'etre TENTE.

HONNETETE : la faisabilite est jugee contre les VRAIES capacites de l'organisme
(Python pur, bibliotheque standard, AUCUN reseau, AUCUNE ecriture fichier). Un
produit qui exigerait une base de donnees, une API tierce ou un disque sera juge
peu faisable EN L'ETAT, ce qui est la verite, pas un echec.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL

CAPACITES = (
    "Capacites de l'organisme : il genere du Python pur (stdlib) execute dans un conteneur "
    "isole. Les capacites ne sont PAS figees : elles sont ACCORDEES par produit. "
    "Disponibles : (1) calcul/logique/transformations en memoire = toujours faisable ; "
    "(2) PERSISTANCE = lecture/ecriture dans un espace disque isole et persistant (volume dedie), "
    "ce qui rend faisables coffre, base locale, sauvegarde, journal ; (3) RESEAU sortant vers une "
    "liste blanche de domaines (enforcement en cours de finalisation). "
    "Donc juge la faisabilite en supposant qu'on peut ACCORDER persistance et/ou reseau si le "
    "produit le justifie. Restent peu faisables en l'etat : UI graphique riche, services multi-machines, "
    "materiel specialise."
)

SEUIL_MERITE = 50  # en dessous, on recadre plutot que generer


class JugementOpportunite(BaseModel):
    merite_attaque: bool = Field(description="vrai si l'intention merite qu'on genere un produit maintenant")
    valeur: int = Field(ge=0, le=100, description="utilite/interet du produit vise")
    faisabilite: int = Field(ge=0, le=100, description="faisabilite dans les capacites reelles (Python pur, sans reseau/fichier)")
    clarte: int = Field(ge=0, le=100, description="clarte de l'intention : sait-on quoi produire ?")
    raison: str = Field(description="une a deux phrases expliquant le verdict")
    reformulation: str = Field(default="", description="si l'intention gagnerait a etre recadree, propose-la ; sinon vide")
    sous_problemes: list[str] = Field(default_factory=list, description="si decomposable, les sous-problemes (sinon liste vide)")


def juger_opportunite(intention: str, client) -> JugementOpportunite:
    systeme = (
        "Tu es la faculte de DISCERNEMENT de NEOGEN. On te donne une intention de produit. "
        "Avant toute generation, tu juges si elle merite qu'on s'y attaque MAINTENANT.\n\n"
        + CAPACITES +
        "\n\nNote valeur, faisabilite, clarte (0-100). 'merite_attaque' est vrai si, globalement, "
        "ca vaut le coup de generer un produit en l'etat (en pratique : moyenne raisonnable et "
        "faisabilite pas trop basse). Si l'intention est floue, trop large ou peu faisable en "
        "l'etat, mets merite_attaque a faux, explique pourquoi, et PROPOSE une reformulation "
        "concrete et faisable. Si l'intention contient plusieurs problemes, liste les sous-problemes."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=3000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": f"Intention : {intention}"}],
        output_format=JugementOpportunite,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Le discernement n'a pas pu juger l'intention")
    return resp.parsed_output


if __name__ == "__main__":
    import anthropic
    intention = " ".join(sys.argv[1:]) or "une application qui gere tout pour mon entreprise"
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"NEOGEN - DISCERNEMENT : '{intention}'")
    print("=" * 72)
    j = juger_opportunite(intention, client)
    print(f"\n  MERITE QU'ON S'Y ATTAQUE : {'OUI' if j.merite_attaque else 'NON'}")
    print(f"  valeur={j.valeur}  faisabilite={j.faisabilite}  clarte={j.clarte}")
    print(f"  raison : {j.raison}")
    if j.reformulation:
        print(f"  reformulation proposee : {j.reformulation}")
    if j.sous_problemes:
        print("  sous-problemes :")
        for sp in j.sous_problemes:
            print(f"     - {sp}")
    print("=" * 72)

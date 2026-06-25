"""
NEOGEN - Proposition d'ADN : l'organisme propose les murs/capacites d'un produit

Coeur du flux co-construit (idee Jordan, 2026-06-17) : un produit part de ZERO,
sans mur. Ici l'organisme JUGE l'intention (discernement) PUIS PROPOSE :
  - les capacites dont le produit a vraiment besoin (persistance, reseau + domaines),
  - les murs de gouvernance pertinents (auth, pas d'exfiltration...),
  - une reformulation si utile.

Ce n'est qu'une PROPOSITION. L'humain ajuste et valide (il garde le dernier mot),
ce qui forge l'ADN neuf, puis on fabrique. L'organisme ne s'auto-accorde rien.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import sys

from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL, parse_resilient
from jugement import JugementOpportunite, CAPACITES
from compositeur import REGLES_MURS


class MurPropose(BaseModel):
    cle: str = Field(description="une cle de mur parmi le vocabulaire fourni")
    label: str = Field(description="libelle court et lisible du mur")
    criticite: str = Field(description="indispensable | important : a quel point ce mur est requis pour CE projet")


class PropositionADN(BaseModel):
    discernement: JugementOpportunite = Field(description="le jugement d'opportunite de l'intention")
    persistance: bool = Field(description="le produit a-t-il besoin de persistance (disque) ?")
    justification_persistance: str = Field(default="", description="pourquoi (ou pourquoi pas)")
    reseau: bool = Field(description="le produit a-t-il besoin d'une sortie reseau ?")
    domaines_proposes: list[str] = Field(default_factory=list, description="liste blanche proposee si reseau")
    justification_reseau: str = Field(default="", description="pourquoi (ou pourquoi pas)")
    murs_proposes: list[str] = Field(default_factory=list,
                                     description="cles de murs de gouvernance parmi le vocabulaire fourni")
    murs_classes: list[MurPropose] = Field(default_factory=list,
                                           description="memes murs que murs_proposes, mais classes par criticite (indispensable/important)")
    resume: str = Field(description="une phrase resumant l'ADN propose")


def _savoir_pour_creation(intention: str, k: int = 5) -> str:
    """Tire du Hub du savoir les skills/lecons/patterns pertinents pour CETTE intention.
    Nourrit la proposition d'ADN avec l'experience accumulee. Tolerant : ne leve jamais."""
    if not intention or not intention.strip():
        return ""
    try:
        import savoir
        resultats = savoir.HUB.chercher(intention, k=k)
    except Exception:
        return ""
    lignes = []
    for r in resultats:
        g = r.get("grain", {})
        contenu = (g.get("contenu", "") or "").strip()
        if contenu:
            lignes.append(f"- [{g.get('domaine', '?')}] {contenu[:200]}")
    if not lignes:
        return ""
    return ("\n\nSAVOIR NEOGEN PERTINENT (skills, lecons et patterns deja accumules sur des "
            "projets proches ; appuie-toi dessus pour proposer un ADN plus juste, ne le repete pas tel quel) :\n"
            + "\n".join(lignes))


def proposer(intention: str, client, contexte: str = "") -> PropositionADN:
    vocab_murs = "; ".join(f"{k} ({v})" for k, v in REGLES_MURS.items())
    systeme = (
        "Tu es la faculte de PROPOSITION de NEOGEN. Un produit part de ZERO, sans mur. "
        "Pour l'intention donnee, tu fais DEUX choses :\n"
        "1) DISCERNEMENT : juge si ca merite qu'on s'y attaque (valeur, faisabilite, clarte), "
        "et propose une reformulation si l'intention est floue ou peu faisable.\n"
        "2) PROPOSITION d'ADN : propose les CAPACITES dont le produit a vraiment besoin et les "
        "MURS de gouvernance pertinents.\n\n"
        + CAPACITES + "\n\n"
        "Accorde la PERSISTANCE seulement si le produit doit conserver des donnees entre deux "
        "executions (coffre, journal, base, sauvegarde). Accorde le RESEAU seulement si le produit "
        "doit joindre un service externe, et alors propose une LISTE BLANCHE de domaines precis "
        "(ex: api.stripe.com). Sinon, laisse-les a faux : un produit pur est plus sur.\n\n"
        f"Murs de gouvernance disponibles (propose ceux qui sont pertinents) : {vocab_murs}.\n\n"
        "Pour les murs : remplis 'murs_proposes' (les cles) ET 'murs_classes' (les MEMES murs, "
        "chacun avec un 'label' lisible et une 'criticite' = 'indispensable' (le produit serait "
        "dangereux ou inutile sans) ou 'important' (fortement recommande mais le produit reste "
        "viable sans). Sois discriminant : tout n'est pas indispensable.\n\n"
        "Rappelle-toi : ce n'est qu'une PROPOSITION, l'humain validera. Sois honnete et sobre : "
        "ne propose pas une capacite 'au cas ou'."
    )
    contenu = f"Intention : {intention}"
    if contexte:
        contenu += f"\n\nContexte connu sur l'utilisateur/ses projets (pour personnaliser, sans l'imposer) :\n{contexte}"
    contenu += _savoir_pour_creation(intention, k=5)
    resp = parse_resilient(
        client, model=MODEL, max_tokens=4000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": contenu}],
        output_format=PropositionADN,
    )
    if resp.parsed_output is None:
        raise RuntimeError("La proposition d'ADN a echoue")
    return resp.parsed_output


if __name__ == "__main__":
    import anthropic
    intention = " ".join(sys.argv[1:]) or "un coffre-fort de mots de passe"
    client = anthropic.Anthropic(api_key=_load_api_key())
    print("=" * 72)
    print(f"NEOGEN - PROPOSITION D'ADN : '{intention}'")
    print("=" * 72)
    p = proposer(intention, client)
    d = p.discernement
    print(f"\n  DISCERNEMENT : {'merite' if d.merite_attaque else 'a recadrer'} "
          f"(valeur={d.valeur} faisabilite={d.faisabilite} clarte={d.clarte})")
    print(f"  raison : {d.raison}")
    if d.reformulation:
        print(f"  reformulation : {d.reformulation}")
    print(f"\n  CAPACITES PROPOSEES :")
    print(f"    persistance : {p.persistance}  ({p.justification_persistance})")
    print(f"    reseau      : {p.reseau}  domaines={p.domaines_proposes}  ({p.justification_reseau})")
    print(f"  MURS PROPOSES : {p.murs_proposes}")
    print(f"\n  RESUME : {p.resume}")
    print("=" * 72)
